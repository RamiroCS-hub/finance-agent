from __future__ import annotations

import ast
import calendar
import inspect
import logging
import operator
from collections import Counter
from dataclasses import dataclass

from app.models.agent import ToolDefinition
from app.models.expense import ParsedExpense
from app.services.timezones import infer_timezone_for_phone, local_now_for_phone

logger = logging.getLogger(__name__)

_CATEGORY_EMOJIS = {
    "Comida": "🍔",
    "Transporte": "🚗",
    "Salud": "💊",
    "Supermercado": "🛒",
    "Entretenimiento": "🎮",
    "Ropa": "👕",
    "Educación": "📚",
    "Hogar": "🏠",
    "Otros": "📦",
    "General": "📦",
}

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp):
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Operador no soportado: {type(node.op).__name__}")
        return op(_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        op = _SAFE_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"Operador no soportado: {type(node.op).__name__}")
        return op(_eval_node(node.operand))
    raise ValueError(f"Expresión no permitida: {ast.dump(node)}")


def safe_calc(expression: str) -> float:
    tree = ast.parse(expression.strip(), mode="eval")
    return _eval_node(tree.body)


@dataclass
class ToolExecutionContext:
    expense_store: object | None
    phone: str
    chat_type: str
    group_id: str | None
    group_expense_service: object
    liability_service: object
    budget_service: object
    alert_service: object
    insights_service: object
    projection_service: object
    education_service: object


class BaseSkill:
    def __init__(self, ctx: ToolExecutionContext) -> None:
        self.ctx = ctx


class ExpenseSkill(BaseSkill):
    async def _register_expense(
        self,
        amount: float,
        description: str,
        category: str = "General",
        currency: str | None = None,
        shop: str | None = None,
        original_amount: float | None = None,
        original_currency: str | None = None,
    ) -> dict:
        from app.config import settings
        from app.db.database import async_session_maker
        from app.services.goals import update_goal_progress

        expense = ParsedExpense(
            amount=float(amount),
            description=description,
            category=category,
            currency=currency or settings.DEFAULT_CURRENCY,
            raw_message=f"{amount} {description}",
            shop=shop,
            spent_at=local_now_for_phone(self.ctx.phone),
            source_timezone=infer_timezone_for_phone(self.ctx.phone),
            source="agent",
            original_amount=original_amount,
            original_currency=original_currency,
        )
        stored_expense = self.ctx.expense_store.append_expense(self.ctx.phone, expense)
        if inspect.isawaitable(stored_expense):
            stored_expense = await stored_expense
        if not stored_expense:
            return {"success": False, "error": "No se pudo guardar el gasto en la base de datos"}

        result = {
            "success": True,
            "expense_id": stored_expense.id,
            "amount": expense.amount,
            "shop": expense.shop,
            "description": expense.description,
            "category": expense.category,
            "currency": expense.currency,
        }

        try:
            async with async_session_maker() as session:
                goal_update = await update_goal_progress(
                    session,
                    user_id=stored_expense.user_id,
                    group_id=None,
                    amount=expense.amount,
                )
                if goal_update:
                    result["goal_status"] = goal_update["status"]
                    result["goal_message"] = goal_update["message"]
        except Exception as exc:
            logger.error("Error actualizando meta para %s: %s", self.ctx.phone, exc)

        try:
            alerts = await self.ctx.alert_service.evaluate_expense_alerts(
                self.ctx.phone,
                amount=expense.amount,
                category=expense.category,
                spent_at=stored_expense.spent_at,
            )
            if alerts:
                result["alerts"] = alerts
        except Exception as exc:
            logger.error("Error evaluando alertas para %s: %s", self.ctx.phone, exc)

        return result

    async def _get_monthly_summary(
        self,
        month: int | None = None,
        year: int | None = None,
    ) -> dict:
        now = local_now_for_phone(self.ctx.phone)
        if month is None:
            if now.day < 15:
                month = now.month - 1 if now.month > 1 else 12
                year = now.year if now.month > 1 else now.year - 1
            else:
                month = now.month
                year = now.year
        else:
            month = int(month)
            year = int(year) if year else now.year

        total = self.ctx.expense_store.get_monthly_total(self.ctx.phone, month, year)
        categories = self.ctx.expense_store.get_category_totals(self.ctx.phone, month, year)
        if inspect.isawaitable(total):
            total = await total
        if inspect.isawaitable(categories):
            categories = await categories
        monthly_commitment = 0.0
        total_with_commitments = total
        try:
            commitment_payload = await self.ctx.liability_service.get_monthly_commitment(
                self.ctx.phone
            )
            monthly_commitment = float(commitment_payload.get("total_monthly_commitment", 0.0))
            total_with_commitments = round(float(total) + monthly_commitment, 2)
        except Exception as exc:
            logger.error("Error consultando compromisos mensuales para %s: %s", self.ctx.phone, exc)

        expense_rows = []
        try:
            month_last_day = calendar.monthrange(year, month)[1]
            expense_rows = self.ctx.expense_store.search_expenses(
                self.ctx.phone,
                date_from=f"{year:04d}-{month:02d}-01",
                date_to=f"{year:04d}-{month:02d}-{month_last_day:02d}",
            )
            if inspect.isawaitable(expense_rows):
                expense_rows = await expense_rows
        except Exception as exc:
            logger.error("Error construyendo detalle mensual para %s: %s", self.ctx.phone, exc)
            expense_rows = []

        category_details = self._build_category_details(categories, expense_rows)
        formatted_summary = self._format_monthly_summary(
            month=month,
            year=year,
            total=float(total),
            monthly_commitment=monthly_commitment,
            total_with_commitments=float(total_with_commitments),
            category_details=category_details,
        )

        return {
            "month": month,
            "year": year,
            "total": total,
            "categories": categories,
            "monthly_commitment": monthly_commitment,
            "total_with_commitments": total_with_commitments,
            "category_details": category_details,
            "formatted_summary": formatted_summary,
        }

    def _build_category_details(
        self,
        categories: dict[str, float],
        expense_rows: list[dict],
    ) -> list[dict]:
        details: list[dict] = []
        sorted_categories = sorted(
            categories.items(),
            key=lambda item: (-float(item[1]), item[0].lower()),
        )
        for category, total in sorted_categories:
            rows = [
                row
                for row in expense_rows
                if (row.get("categoria") or "").lower() == category.lower()
            ]
            details.append(
                {
                    "category": category,
                    "emoji": _CATEGORY_EMOJIS.get(category, "📦"),
                    "total": round(float(total), 2),
                    "movement_count": len(rows),
                    "observation": self._build_category_observation(rows),
                }
            )
        return details

    def _build_category_observation(self, rows: list[dict]) -> str:
        if not rows:
            return "Sin observaciones relevantes."

        normalized_names = [
            (row.get("shop") or row.get("descripcion") or "").strip()
            for row in rows
            if (row.get("shop") or row.get("descripcion"))
        ]
        name_counts = Counter(normalized_names)
        most_common_name, most_common_count = ("", 0)
        if name_counts:
            most_common_name, most_common_count = name_counts.most_common(1)[0]

        top_expense = max(rows, key=lambda row: float(row.get("monto", 0.0)))
        top_name = (top_expense.get("shop") or top_expense.get("descripcion") or "sin detalle").strip()
        top_amount = self._format_currency(float(top_expense.get("monto", 0.0)))

        if len(rows) == 1:
            return f"1 mov. • mayor: {top_name} ${top_amount}"
        if most_common_name and most_common_count > 1:
            return f"{len(rows)} mov. • frecuente: {most_common_name} ({most_common_count})"
        return f"{len(rows)} mov. • mayor: {top_name} ${top_amount}"

    def _format_monthly_summary(
        self,
        *,
        month: int,
        year: int,
        total: float,
        monthly_commitment: float,
        total_with_commitments: float,
        category_details: list[dict],
    ) -> str:
        month_name = calendar.month_name[month].capitalize()
        lines = [
            f"RESUMEN {month_name} {year}",
            f"*Total gastado:* ${self._format_currency(total)}",
        ]
        if monthly_commitment > 0:
            lines.append(f"*Compromisos:* ${self._format_currency(monthly_commitment)}")
            lines.append(f"*Total + compromisos:* ${self._format_currency(total_with_commitments)}")

        if not category_details:
            lines.append("")
            lines.append("Sin gastos registrados en ese período.")
            return "\n".join(lines)

        lines.extend(["", "POR CATEGORÍA"])
        for detail in category_details:
            lines.append(
                f"{detail['emoji']} {detail['category']} *${self._format_currency(detail['total'])}*"
            )
            if detail["observation"]:
                lines.append(f"_Obs:_ {detail['observation']}")
        return "\n".join(lines)

    def _format_currency(self, value: float) -> str:
        formatted = f"{value:,.2f}"
        if formatted.endswith(".00"):
            formatted = formatted[:-3]
        return formatted.replace(",", "X").replace(".", ",").replace("X", ".")

    async def _get_category_breakdown(
        self,
        month: int | None = None,
        year: int | None = None,
        category: str | None = None,
    ) -> dict:
        now = local_now_for_phone(self.ctx.phone)
        if month is None:
            if now.day < 15:
                month = now.month - 1 if now.month > 1 else 12
                year = now.year if now.month > 1 else now.year - 1
            else:
                month = now.month
                year = now.year
        else:
            month = int(month)
            year = int(year) if year else now.year
        month_last_day = calendar.monthrange(year, month)[1]
        expense_rows = self.ctx.expense_store.search_expenses(
            self.ctx.phone,
            date_from=f"{year:04d}-{month:02d}-01",
            date_to=f"{year:04d}-{month:02d}-{month_last_day:02d}",
        )
        if inspect.isawaitable(expense_rows):
            expense_rows = await expense_rows
        categories = self.ctx.expense_store.get_category_totals(self.ctx.phone, month, year)
        if inspect.isawaitable(categories):
            categories = await categories
        if category:
            filtered = {k: v for k, v in categories.items() if k.lower() == category.lower()}
            category_name = next(iter(filtered.keys()), category)
            entries = [
                {
                    "expense_id": row.get("expense_id"),
                    "fecha": row.get("fecha"),
                    "hora": row.get("hora"),
                    "monto": row.get("monto"),
                    "moneda": row.get("moneda"),
                    "shop": row.get("shop"),
                    "descripcion": row.get("descripcion"),
                }
                for row in expense_rows
                if (row.get("categoria") or "").lower() == category.lower()
            ]
            return {
                "month": month,
                "year": year,
                "category": category_name,
                "breakdown": filtered,
                "entries": entries,
                "formatted_breakdown": self._format_category_breakdown(
                    category_name,
                    float(filtered.get(category_name, 0.0)),
                    entries,
                ),
            }
        return {"month": month, "year": year, "breakdown": categories}

    def _format_category_breakdown(
        self,
        category: str,
        total: float,
        entries: list[dict],
    ) -> str:
        emoji = _CATEGORY_EMOJIS.get(category, "📦")
        lines = [f"{emoji} {category} *${self._format_currency(total)}*"]
        if not entries:
            lines.append("_Sin compras registradas en esa categoría._")
            return "\n".join(lines)

        for entry in entries[:8]:
            detail = (entry.get("shop") or entry.get("descripcion") or "sin detalle").strip()
            lines.append(
                f"• {entry.get('fecha')} {entry.get('hora')} · ${self._format_currency(float(entry.get('monto', 0.0)))} · {detail}"
            )
        if len(entries) > 8:
            lines.append(f"_Y {len(entries) - 8} compra(s) más._")
        return "\n".join(lines)

    async def _get_recent_expenses(self, limit: int = 5) -> dict:
        expenses = self.ctx.expense_store.get_recent_expenses(self.ctx.phone, n=int(limit))
        if inspect.isawaitable(expenses):
            expenses = await expenses
        return {"expenses": expenses, "count": len(expenses)}

    async def _delete_last_expense(self) -> dict:
        deleted = self.ctx.expense_store.delete_last_expense(self.ctx.phone)
        if inspect.isawaitable(deleted):
            deleted = await deleted
        if not deleted:
            return {"success": False, "error": "No hay gastos registrados para eliminar"}
        return {"success": True, "deleted": deleted}

    async def _search_expenses(
        self,
        query: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict:
        results = self.ctx.expense_store.search_expenses(
            self.ctx.phone,
            query=query,
            date_from=date_from,
            date_to=date_to,
        )
        if inspect.isawaitable(results):
            results = await results
        return {"expenses": results, "count": len(results)}

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="register_expense",
                description=(
                    "Registra un gasto del usuario en la base de datos. "
                    "Llamar siempre que el usuario mencione un monto y una descripción. "
                    "Si el resultado contiene 'goal_status' = 'completed', se ha alcanzado la meta de ahorro "
                    "y debes felicitar al usuario e incluir el 'goal_message' en tu respuesta final."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number", "description": "Monto del gasto (número positivo)"},
                        "description": {
                            "type": "string",
                            "description": "Descripción breve del gasto (ej: farmacia, uber, almuerzo)",
                        },
                        "category": {
                            "type": "string",
                            "description": (
                                "Categoría del gasto. Usar una de: "
                                "Comida, Transporte, Salud, Supermercado, Entretenimiento, "
                                "Ropa, Educación, Hogar, Otros. Default: Otros."
                            ),
                        },
                        "currency": {
                            "type": "string",
                            "description": "Moneda (ARS, USD, EUR). Default: moneda configurada.",
                        },
                        "shop": {
                            "type": "string",
                            "description": "Comercio o negocio donde se hizo el pago.",
                        },
                        "original_amount": {
                            "type": "number",
                            "description": "Monto original antes de conversión (si fue convertido desde otra moneda)",
                        },
                        "original_currency": {
                            "type": "string",
                            "description": "Moneda original antes de conversión (si fue convertido)",
                        },
                    },
                    "required": ["amount", "description"],
                },
                fn=self._register_expense,
            ),
            ToolDefinition(
                name="get_monthly_summary",
                description=(
                    "Obtiene el total de gastos y el desglose por categoría de un mes. "
                    "Si no se especifica mes, usa el mes anterior si estamos antes del día 15, "
                    "o el mes actual si estamos después del día 15. "
                    "Usar cuando el usuario pide 'resumen', 'cuánto gasté', 'total del mes'."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "month": {"type": "integer", "description": "Mes (1-12). Default: inteligente según día del mes."},
                        "year": {"type": "integer", "description": "Año. Default: año actual."},
                    },
                },
                fn=self._get_monthly_summary,
            ),
            ToolDefinition(
                name="get_category_breakdown",
                description=(
                    "Obtiene el desglose detallado por categoría. "
                    "Si no se especifica mes, usa el mes anterior si estamos antes del día 15, "
                    "o el mes actual si estamos después del día 15. "
                    "Usar cuando el usuario pide 'por categoría', 'desglose', o una categoría específica."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "month": {"type": "integer", "description": "Mes (1-12). Default: inteligente según día del mes."},
                        "year": {"type": "integer", "description": "Año. Default: año actual."},
                        "category": {
                            "type": "string",
                            "description": "Categoría específica a consultar (opcional).",
                        },
                    },
                },
                fn=self._get_category_breakdown,
            ),
            ToolDefinition(
                name="get_recent_expenses",
                description="Obtiene los últimos gastos registrados. Usar cuando el usuario pide 'últimos gastos', 'historial', 'recientes'.",
                parameters={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Cantidad de gastos a mostrar (default: 5, max: 20).",
                        }
                    },
                },
                fn=self._get_recent_expenses,
            ),
            ToolDefinition(
                name="delete_last_expense",
                description="Elimina el último gasto registrado. Usar cuando el usuario pide 'borrar', 'eliminar', 'cancelar el último gasto'.",
                parameters={"type": "object", "properties": {}},
                fn=self._delete_last_expense,
            ),
            ToolDefinition(
                name="search_expenses",
                description="Busca gastos por texto en la descripción y/o rango de fechas. Usar cuando el usuario pregunta por gastos específicos.",
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Texto a buscar en la descripción (case-insensitive)."},
                        "date_from": {"type": "string", "description": "Fecha inicio en formato YYYY-MM-DD (inclusive)."},
                        "date_to": {"type": "string", "description": "Fecha fin en formato YYYY-MM-DD (inclusive)."},
                    },
                },
                fn=self._search_expenses,
            ),
        ]


class BudgetSkill(BaseSkill):
    async def _save_budget(self, category: str, limit_amount: float, period: str = "monthly") -> dict:
        payload = await self.ctx.budget_service.save_budget(
            self.ctx.phone,
            category=category,
            limit_amount=float(limit_amount),
            period=period,
        )
        return {"success": True, **payload}

    async def _list_budgets(self) -> dict:
        budgets = await self.ctx.budget_service.list_budgets(self.ctx.phone)
        return {"count": len(budgets), "budgets": budgets}

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="save_budget",
                description="Guarda o actualiza un presupuesto por categoría para el usuario actual. Usar cuando el usuario dice cosas como 'mi presupuesto para comida es 200000'.",
                parameters={
                    "type": "object",
                    "properties": {
                        "category": {"type": "string", "description": "Categoría del presupuesto"},
                        "limit_amount": {"type": "number", "description": "Monto límite"},
                        "period": {
                            "type": "string",
                            "description": "Período del presupuesto. Default: monthly.",
                            "default": "monthly",
                        },
                    },
                    "required": ["category", "limit_amount"],
                },
                fn=self._save_budget,
            ),
            ToolDefinition(
                name="list_budgets",
                description="Lista los presupuestos activos del usuario. Usar cuando pregunta por sus límites o presupuestos configurados.",
                parameters={"type": "object", "properties": {}},
                fn=self._list_budgets,
            ),
        ]


class InsightSkill(BaseSkill):
    async def _get_spending_comparison(self, period: str = "monthly", group_by: str = "category") -> dict:
        return await self.ctx.insights_service.compare_spending_periods(
            self.ctx.phone,
            period=period,
            group_by=group_by,
        )

    async def _get_spending_insights(self) -> dict:
        return await self.ctx.insights_service.detect_spending_leaks(self.ctx.phone)

    async def _project_savings(
        self,
        amount: float | None = None,
        frequency: str | None = None,
        horizon_months: int = 6,
        category: str | None = None,
        reduction_percent: float | None = None,
    ) -> dict:
        return await self.ctx.projection_service.project_savings(
            self.ctx.phone,
            amount=amount,
            frequency=frequency,
            horizon_months=horizon_months,
            category=category,
            reduction_percent=reduction_percent,
        )

    async def _get_financial_education(self) -> dict:
        return await self.ctx.education_service.evaluate_financial_education(self.ctx.phone)

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="get_spending_comparison",
                description="Compara gasto entre períodos recientes por categoría o merchant. Usar cuando el usuario pide comparativas semanales o mensuales, subas/bajas por rubro o cómo cambió su gasto.",
                parameters={
                    "type": "object",
                    "properties": {
                        "period": {
                            "type": "string",
                            "description": "Periodo a comparar: monthly o weekly. Default: monthly.",
                            "default": "monthly",
                        },
                        "group_by": {
                            "type": "string",
                            "description": "Agrupación: category o merchant. Default: category.",
                            "default": "category",
                        },
                    },
                },
                fn=self._get_spending_comparison,
            ),
            ToolDefinition(
                name="get_spending_insights",
                description="Detecta posibles fugas, gastos repetidos y hallazgos accionables sobre el histórico. Usar cuando el usuario pregunta dónde se le va la plata, qué podría recortar o qué patrones repetidos ve en sus gastos.",
                parameters={"type": "object", "properties": {}},
                fn=self._get_spending_insights,
            ),
            ToolDefinition(
                name="project_savings",
                description="Proyecta cuánto podría ahorrar el usuario en distintos escenarios. Usar cuando pregunta cuánto ahorraría si reduce una categoría, si ahorra X por semana/mes o cómo impactaría eso en una meta.",
                parameters={
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number", "description": "Monto de ahorro manual por período."},
                        "frequency": {"type": "string", "description": "Frecuencia del ahorro: weekly o monthly."},
                        "horizon_months": {
                            "type": "integer",
                            "description": "Horizonte en meses para proyectar. Default: 6.",
                            "default": 6,
                        },
                        "category": {"type": "string", "description": "Categoría a recortar usando histórico real."},
                        "reduction_percent": {
                            "type": "number",
                            "description": "Porcentaje de reducción sobre la categoría histórica.",
                        },
                    },
                },
                fn=self._project_savings,
            ),
            ToolDefinition(
                name="get_financial_education",
                description="Genera una lectura educativa basada en el historial: benchmark 50/30/20, fondo de emergencia, comparativa nominal o real y tips accionables.",
                parameters={"type": "object", "properties": {}},
                fn=self._get_financial_education,
            ),
        ]


class LiabilitySkill(BaseSkill):
    async def _create_liability(
        self,
        kind: str,
        description: str,
        monthly_amount: float,
        remaining_periods: int,
        currency: str | None = None,
    ) -> dict:
        return await self.ctx.liability_service.create_liability(
            self.ctx.phone,
            kind=kind,
            description=description,
            monthly_amount=float(monthly_amount),
            remaining_periods=int(remaining_periods),
            currency=currency or "ARS",
        )

    async def _get_monthly_commitment(self) -> dict:
        return await self.ctx.liability_service.get_monthly_commitment(self.ctx.phone)

    async def _close_liability(self, liability_id: int) -> dict:
        return await self.ctx.liability_service.close_liability(
            self.ctx.phone,
            liability_id=int(liability_id),
        )

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="create_liability",
                description="Registra una deuda simple o una compra en cuotas como obligación futura. Usar cuando el usuario menciona cuotas, deuda pendiente o compromiso mensual.",
                parameters={
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "description": "Tipo de obligación: installment o debt."},
                        "description": {"type": "string", "description": "Descripción de la obligación."},
                        "monthly_amount": {"type": "number", "description": "Monto mensual comprometido."},
                        "remaining_periods": {"type": "integer", "description": "Cantidad de meses o cuotas restantes."},
                        "currency": {"type": "string", "description": "Moneda de la obligación. Default: ARS."},
                    },
                    "required": ["kind", "description", "monthly_amount", "remaining_periods"],
                },
                fn=self._create_liability,
            ),
            ToolDefinition(
                name="get_monthly_commitment",
                description="Devuelve cuánto tiene comprometido el usuario por cuotas o deudas activas. Usar cuando pregunta por compromisos futuros o cuánto ya tiene tomado del mes.",
                parameters={"type": "object", "properties": {}},
                fn=self._get_monthly_commitment,
            ),
            ToolDefinition(
                name="close_liability",
                description="Cierra una deuda o plan de cuotas para que deje de contar como compromiso futuro.",
                parameters={
                    "type": "object",
                    "properties": {
                        "liability_id": {"type": "integer", "description": "ID de la obligación a cerrar."}
                    },
                    "required": ["liability_id"],
                },
                fn=self._close_liability,
            ),
        ]


class GroupSkill(BaseSkill):
    async def _get_user_groups_info(self) -> dict:
        from app.db.database import async_session_maker
        from app.db.models import Goal, GroupMember, User
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload

        try:
            async with async_session_maker() as session:
                query = select(User).where(User.whatsapp_number == self.ctx.phone).options(
                    selectinload(User.group_memberships).selectinload(GroupMember.group)
                )
                result = await session.execute(query)
                user = result.scalar_one_or_none()
                if not user:
                    return {"success": False, "error": "Usuario no encontrado"}

                groups_info = []
                for membership in user.group_memberships:
                    group = membership.group
                    goal_query = select(Goal).where(Goal.group_id == group.id, Goal.status == "active")
                    goal_res = await session.execute(goal_query)
                    goals = goal_res.scalars().all()
                    groups_info.append(
                        {
                            "name": group.name,
                            "whatsapp_group_id": group.whatsapp_group_id,
                            "active_goals": [
                                {"target_amount": g.target_amount, "current_amount": g.current_amount}
                                for g in goals
                            ],
                        }
                    )
                return {"success": True, "groups": groups_info}
        except Exception as exc:
            logger.error("Error en _get_user_groups_info: %s", exc)
            return {"success": False, "error": str(exc)}

    async def _register_group_expense(
        self,
        amount: float,
        description: str,
        category: str = "General",
        currency: str | None = None,
        shop: str | None = None,
        split_member_phones: list[str] | None = None,
    ) -> dict:
        from app.config import settings
        from app.db.database import async_session_maker
        from app.db.models import Group
        from app.services.goals import update_goal_progress
        from sqlalchemy import select

        if self.ctx.chat_type != "group" or not self.ctx.group_id:
            return {"success": False, "error": "Esta herramienta solo se puede usar dentro de un grupo"}

        result = await self.ctx.group_expense_service.register_group_expense(
            whatsapp_group_id=self.ctx.group_id,
            payer_phone=self.ctx.phone,
            amount=float(amount),
            description=description,
            category=category,
            currency=currency or settings.DEFAULT_CURRENCY,
            shop=shop,
            spent_at=local_now_for_phone(self.ctx.phone),
            source_timezone=infer_timezone_for_phone(self.ctx.phone),
            split_member_phones=split_member_phones,
        )

        try:
            async with async_session_maker() as session:
                group_result = await session.execute(
                    select(Group).where(Group.whatsapp_group_id == self.ctx.group_id)
                )
                group = group_result.scalar_one_or_none()
                if group:
                    goal_update = await update_goal_progress(
                        session,
                        user_id=None,
                        group_id=group.id,
                        amount=float(amount),
                    )
                    if goal_update:
                        result["goal_status"] = goal_update["status"]
                        result["goal_message"] = goal_update["message"]
        except Exception as exc:
            logger.error("Error actualizando meta grupal para %s: %s", self.ctx.group_id, exc)

        return result

    async def _get_group_balance(self) -> dict:
        if self.ctx.chat_type != "group" or not self.ctx.group_id:
            return {"success": False, "error": "Esta herramienta solo se puede usar dentro de un grupo"}
        return await self.ctx.group_expense_service.get_group_balance(self.ctx.group_id, self.ctx.phone)

    async def _settle_group_balances(self) -> dict:
        if self.ctx.chat_type != "group" or not self.ctx.group_id:
            return {"success": False, "error": "Esta herramienta solo se puede usar dentro de un grupo"}
        return await self.ctx.group_expense_service.settle_group(self.ctx.group_id, self.ctx.phone)

    async def _create_group_goal(self, target_amount: float) -> dict:
        from app.db.database import async_session_maker
        from app.db.models import Group
        from app.services.goals import create_or_update_goal
        from sqlalchemy import select

        if self.ctx.chat_type != "group" or not self.ctx.group_id:
            return {"success": False, "error": "Esta herramienta solo se puede usar dentro de un grupo"}

        try:
            async with async_session_maker() as session:
                group_result = await session.execute(
                    select(Group).where(Group.whatsapp_group_id == self.ctx.group_id)
                )
                group = group_result.scalar_one_or_none()
                if not group:
                    return {"success": False, "error": "Grupo no encontrado"}
                goal_payload = await create_or_update_goal(
                    session,
                    target_amount=float(target_amount),
                    group_id=group.id,
                )
                return {"success": True, **goal_payload}
        except Exception as exc:
            logger.error("Error creando meta grupal para %s: %s", self.ctx.group_id, exc)
            return {"success": False, "error": str(exc)}

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="get_user_groups_info",
                description="Consulta en la base de datos a qué grupos de WhatsApp pertenece el usuario y devuelve la información de esos grupos junto con sus metas activas y el progreso de las mismas. Usar cuando el usuario pregunta por 'mis grupos', 'estado de mis grupos', 'metas de mis grupos', o cómo va el ahorro en los grupos en los que participa.",
                parameters={"type": "object", "properties": {}},
                fn=self._get_user_groups_info,
            ),
            ToolDefinition(
                name="register_group_expense",
                description="Registra un gasto compartido dentro del grupo actual. Usar cuando un miembro menciona al bot en un grupo para anotar un gasto grupal. Si no se aclaran participantes, reparte el gasto en partes iguales entre los miembros conocidos.",
                parameters={
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number", "description": "Monto total del gasto"},
                        "description": {"type": "string", "description": "Descripción breve del gasto"},
                        "category": {"type": "string", "description": "Categoría del gasto"},
                        "currency": {"type": "string", "description": "Moneda del gasto"},
                        "shop": {"type": "string", "description": "Negocio o comercio donde se hizo el pago grupal."},
                        "split_member_phones": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Teléfonos a repartir. Si se omite, reparte entre todos los miembros conocidos.",
                        },
                    },
                    "required": ["amount", "description"],
                },
                fn=self._register_group_expense,
            ),
            ToolDefinition(
                name="get_group_balance",
                description="Devuelve cuánto puso cada integrante del grupo, cuánto debería haber puesto y su saldo neto. Usar cuando piden balance, quién debe o cómo van las cuentas del grupo.",
                parameters={"type": "object", "properties": {}},
                fn=self._get_group_balance,
            ),
            ToolDefinition(
                name="settle_group_balances",
                description="Calcula las transferencias mínimas sugeridas para saldar el balance del grupo. Usar cuando piden liquidación, cerrar cuentas o quién le tiene que pagar a quién.",
                parameters={"type": "object", "properties": {}},
                fn=self._settle_group_balances,
            ),
            ToolDefinition(
                name="create_group_goal",
                description="Crea o actualiza la meta compartida activa del grupo actual. Usar cuando el grupo quiere fijar una meta de ahorro o actualizar su objetivo.",
                parameters={
                    "type": "object",
                    "properties": {
                        "target_amount": {"type": "number", "description": "Monto objetivo de la meta grupal"}
                    },
                    "required": ["target_amount"],
                },
                fn=self._create_group_goal,
            ),
        ]


class ReportSkill(BaseSkill):
    async def _generate_expense_report(
        self,
        month: int | None = None,
        year: int | None = None,
    ) -> dict:
        """Genera un PDF con gráficos y tabla de gastos y lo envía por WhatsApp."""
        import asyncio
        from app.config import settings
        from app.services import report_pdf, whatsapp

        now = local_now_for_phone(self.ctx.phone)
        if month is None:
            if now.day < 15:
                month = now.month - 1 if now.month > 1 else 12
                year_val = now.year if now.month > 1 else now.year - 1
            else:
                month = now.month
                year_val = now.year
        else:
            month = int(month)
            year_val = int(year) if year else now.year

        # Datos del mes
        total = self.ctx.expense_store.get_monthly_total(self.ctx.phone, month, year_val)
        if inspect.isawaitable(total):
            total = await total

        categories = self.ctx.expense_store.get_category_totals(self.ctx.phone, month, year_val)
        if inspect.isawaitable(categories):
            categories = await categories

        days_in_month = calendar.monthrange(year_val, month)[1]
        expenses = self.ctx.expense_store.search_expenses(
            self.ctx.phone,
            date_from=f"{year_val:04d}-{month:02d}-01",
            date_to=f"{year_val:04d}-{month:02d}-{days_in_month:02d}",
        )
        if inspect.isawaitable(expenses):
            expenses = await expenses

        if not expenses:
            return {
                "success": False,
                "error": "No hay gastos registrados en ese período para generar un reporte.",
                "formatted_confirmation": "No encontré gastos en ese período para armar el reporte.",
            }

        # Generar PDF en executor (CPU-bound: matplotlib + fpdf2)
        loop = asyncio.get_running_loop()
        pdf_bytes = await loop.run_in_executor(
            None,
            report_pdf.generate_expense_report,
            month, year_val, float(total or 0), settings.DEFAULT_CURRENCY,
            dict(categories or {}), list(expenses),
        )

        month_names_es = [
            "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
            "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
        ]
        month_name = month_names_es[month]
        filename = f"Reporte_Gastos_{month_name}_{year_val}.pdf"

        media_id = await whatsapp.upload_media(pdf_bytes, "application/pdf", filename)
        if not media_id:
            return {
                "success": False,
                "error": "No se pudo subir el PDF a WhatsApp.",
                "formatted_confirmation": "Hubo un error al preparar el reporte. Intentá de nuevo.",
            }

        wamid = await whatsapp.send_document(
            self.ctx.phone,
            media_id,
            filename,
            caption=f"📊 Reporte de gastos — {month_name} {year_val}",
        )
        if not wamid:
            return {
                "success": False,
                "error": "No se pudo enviar el documento.",
                "formatted_confirmation": "El reporte se generó pero no se pudo enviar. Intentá de nuevo.",
            }

        return {
            "success": True,
            "formatted_confirmation": f"📊 Te envié el reporte de {month_name} {year_val} como PDF.",
            "filename": filename,
        }

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="generate_expense_report",
                description=(
                    "Genera un reporte PDF con gráfico de torta por categoría, gráfico de barras "
                    "por día y tabla detallada de todos los gastos del mes, y lo envía como "
                    "documento de WhatsApp. "
                    "Usar cuando el usuario pide 'reporte', 'pdf', 'gráfico de gastos', "
                    "'reporte mensual', 'exportar gastos', o quiere ver sus gastos en formato visual."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "month": {
                            "type": "integer",
                            "description": "Mes (1-12). Si se omite, usa el mes más reciente con actividad.",
                        },
                        "year": {
                            "type": "integer",
                            "description": "Año. Si se omite, usa el año actual.",
                        },
                    },
                },
                fn=self._generate_expense_report,
            ),
        ]


class UtilitySkill(BaseSkill):
    def _get_sheet_url(self) -> dict:
        return {
            "available": False,
            "message": "La app ya no usa una planilla operativa para guardar gastos.",
        }

    def _calculate(self, expression: str) -> dict:
        try:
            result = safe_calc(expression)
            return {"expression": expression, "result": round(result, 2)}
        except Exception as exc:
            return {"error": f"No se pudo evaluar '{expression}': {exc}"}

    def _convert_currency(self, amount: float, from_currency: str, to_currency: str = "ARS") -> dict:
        from app.services import currency

        amount_destiny, rate = currency.convert_to_another_currency(amount, from_currency, to_currency)
        return {
            "original_amount": amount,
            "original_currency": from_currency.upper(),
            "converted_amount": round(amount_destiny, 2),
            "target_currency": to_currency.upper(),
            "exchange_rate": rate,
        }

    def _send_cat_pic(self) -> dict:
        import httpx
        from app.services import whatsapp

        cat_api_url = "https://api.thecatapi.com/v1/images/search?mime_types=jpg,png"
        try:
            with httpx.Client() as client:
                response = client.get(cat_api_url, timeout=10.0)
                response.raise_for_status()
                data = response.json()
                pic_url = data[0]["url"]
        except Exception as exc:
            logger.error("Error obteniendo foto de TheCatAPI: %s", exc)
            return {"success": False, "error": f"No se pudo obtener la foto: {exc}"}

        wamid = whatsapp.send_image_sync(self.ctx.phone, pic_url)
        if wamid:
            return {"success": True, "pic_url": pic_url, "wamid": wamid}
        return {"success": False, "error": "No se pudo enviar la foto por WhatsApp"}

    async def _save_personality(self, prompt: str) -> dict:
        from app.db.database import async_session_maker
        from app.services.personality import save_custom_prompt

        try:
            async with async_session_maker() as session:
                is_group = self.ctx.chat_type == "group" and self.ctx.group_id is not None
                entity_id = self.ctx.group_id if is_group else self.ctx.phone
                await save_custom_prompt(session, entity_id, prompt, is_group=is_group)
                return {"success": True, "message": "Personalidad guardada exitosamente en la base de datos."}
        except Exception as exc:
            logger.error("Error guardando personalidad para %s: %s", self.ctx.phone, exc)
            return {"success": False, "error": str(exc)}

    def definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="get_sheet_url",
                description="Informa que el link directo a la planilla no se comparte por seguridad. Usar cuando pide 'link', 'planilla' o 'excel'.",
                parameters={"type": "object", "properties": {}},
                fn=self._get_sheet_url,
            ),
            ToolDefinition(
                name="calculate",
                description="Evalúa una expresión matemática y devuelve el resultado numérico. Usar SIEMPRE que el mensaje del usuario involucre cualquier cálculo: porcentajes, IVA, impuestos, sumas de varios montos, descuentos, propinas, divisiones entre personas, etc. Llamar ANTES de register_expense para obtener el monto correcto.",
                parameters={
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": "Expresión aritmética pura con números y operadores (+, -, *, /, paréntesis).",
                        }
                    },
                    "required": ["expression"],
                },
                fn=self._calculate,
            ),
            ToolDefinition(
                name="convert_currency",
                description="Convierte un monto de moneda extranjera a la moneda de destino. Usar cuando el usuario mencione un gasto en moneda extranjera. Llamar ANTES de register_expense para obtener el monto en la moneda de destino.",
                parameters={
                    "type": "object",
                    "properties": {
                        "amount": {"type": "number", "description": "Monto en la moneda origen"},
                        "from_currency": {"type": "string", "description": "Código de moneda: USD, UYU, CLP, COP"},
                        "to_currency": {
                            "type": "string",
                            "description": "Código de moneda de destino: USD, UYU, CLP, COP, ARS",
                            "default": "ARS",
                        },
                    },
                    "required": ["amount", "from_currency", "to_currency"],
                },
                fn=self._convert_currency,
            ),
            ToolDefinition(
                name="send_cat_pic",
                description="Obtiene una foto aleatoria de un gatito desde internet y la envía por WhatsApp al usuario. Usar cuando el usuario pida una foto, imagen o gif de gato.",
                parameters={"type": "object", "properties": {}},
                fn=self._send_cat_pic,
            ),
            ToolDefinition(
                name="save_personality",
                description="Guarda una nueva personalidad o reglas de comportamiento para el asistente en la base de datos. Usar cuando el usuario pide explícitamente que actúes diferente o te da instrucciones persistentes.",
                parameters={
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "Las nuevas instrucciones de comportamiento o personalidad a guardar.",
                        }
                    },
                    "required": ["prompt"],
                },
                fn=self._save_personality,
            ),
        ]
