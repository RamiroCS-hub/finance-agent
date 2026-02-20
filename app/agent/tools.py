from __future__ import annotations

import ast
import logging
import operator
from datetime import datetime

from app.models.agent import ToolDefinition
from app.models.expense import ParsedExpense
from app.services.sheets import SheetsService

logger = logging.getLogger(__name__)

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
    """Evalúa una expresión aritmética de forma segura (sin eval)."""
    tree = ast.parse(expression.strip(), mode="eval")
    return _eval_node(tree.body)


class ToolRegistry:
    """
    Registro de las herramientas disponibles para el agente.
    Cada instancia está ligada a un usuario (phone) y a un SheetsService.
    """

    def __init__(self, sheets: SheetsService, phone: str) -> None:
        self.sheets = sheets
        self.phone = phone
        self._tools: dict[str, ToolDefinition] = {
            t.name: t for t in self._build_definitions()
        }

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def definitions(self) -> list[ToolDefinition]:
        """Retorna todas las definiciones para pasarlas al LLM."""
        return list(self._tools.values())

    def run(self, name: str, **kwargs) -> dict:
        """
        Ejecuta la herramienta por nombre.
        Retorna dict JSON-serializable.
        Lanza ValueError si el nombre no existe.
        """
        if name not in self._tools:
            raise ValueError(f"Herramienta desconocida: '{name}'")
        tool = self._tools[name]
        logger.debug("Ejecutando herramienta '%s' con args: %s", name, kwargs)
        return tool.fn(**kwargs)

    # ------------------------------------------------------------------
    # Implementaciones de herramientas
    # ------------------------------------------------------------------

    def _register_expense(
        self,
        amount: float,
        description: str,
        category: str = "General",
        currency: str | None = None,
    ) -> dict:
        from app.config import settings

        expense = ParsedExpense(
            amount=float(amount),
            description=description,
            category=category,
            currency=currency or settings.DEFAULT_CURRENCY,
            raw_message=f"{amount} {description}",
            source="agent",
        )
        row_index = self.sheets.append_expense(self.phone, expense)
        if row_index:
            return {
                "success": True,
                "row_index": row_index,
                "amount": expense.amount,
                "description": expense.description,
                "category": expense.category,
                "currency": expense.currency,
            }
        return {"success": False, "error": "No se pudo guardar el gasto en Google Sheets"}

    def _get_monthly_summary(
        self,
        month: int | None = None,
        year: int | None = None,
    ) -> dict:
        now = datetime.now()
        month = int(month) if month else now.month
        year = int(year) if year else now.year
        total = self.sheets.get_monthly_total(self.phone, month, year)
        categories = self.sheets.get_category_totals(self.phone, month, year)
        return {
            "month": month,
            "year": year,
            "total": total,
            "categories": categories,
        }

    def _get_category_breakdown(
        self,
        month: int | None = None,
        year: int | None = None,
        category: str | None = None,
    ) -> dict:
        now = datetime.now()
        month = int(month) if month else now.month
        year = int(year) if year else now.year
        categories = self.sheets.get_category_totals(self.phone, month, year)
        if category:
            filtered = {k: v for k, v in categories.items() if k.lower() == category.lower()}
            return {"month": month, "year": year, "category": category, "breakdown": filtered}
        return {"month": month, "year": year, "breakdown": categories}

    def _get_recent_expenses(self, limit: int = 5) -> dict:
        expenses = self.sheets.get_recent_expenses(self.phone, n=int(limit))
        return {"expenses": expenses, "count": len(expenses)}

    def _delete_last_expense(self) -> dict:
        all_expenses = self.sheets.search_expenses(self.phone)
        if not all_expenses:
            return {"success": False, "error": "No hay gastos registrados para eliminar"}
        last = all_expenses[-1]
        success = self.sheets.delete_expense(self.phone, last["row_index"])
        if success:
            return {"success": True, "deleted": last}
        return {"success": False, "error": "Error al eliminar el gasto en Google Sheets"}

    def _search_expenses(
        self,
        query: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict:
        results = self.sheets.search_expenses(
            self.phone,
            query=query,
            date_from=date_from,
            date_to=date_to,
        )
        return {"expenses": results, "count": len(results)}

    def _get_sheet_url(self) -> dict:
        return {"url": self.sheets.get_sheet_url()}

    def _calculate(self, expression: str) -> dict:
        try:
            result = safe_calc(expression)
            return {"expression": expression, "result": round(result, 2)}
        except Exception as e:
            return {"error": f"No se pudo evaluar '{expression}': {e}"}

    # ------------------------------------------------------------------
    # Definiciones (nombre, descripción, JSON Schema)
    # ------------------------------------------------------------------

    def _build_definitions(self) -> list[ToolDefinition]:
        return [
            ToolDefinition(
                name="register_expense",
                description=(
                    "Registra un gasto del usuario en Google Sheets. "
                    "Llamar siempre que el usuario mencione un monto y una descripción."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "amount": {
                            "type": "number",
                            "description": "Monto del gasto (número positivo)",
                        },
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
                    },
                    "required": ["amount", "description"],
                },
                fn=self._register_expense,
            ),
            ToolDefinition(
                name="get_monthly_summary",
                description=(
                    "Obtiene el total de gastos y el desglose por categoría de un mes. "
                    "Usar cuando el usuario pide 'resumen', 'cuánto gasté', 'total del mes'."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "month": {
                            "type": "integer",
                            "description": "Mes (1-12). Default: mes actual.",
                        },
                        "year": {
                            "type": "integer",
                            "description": "Año. Default: año actual.",
                        },
                    },
                },
                fn=self._get_monthly_summary,
            ),
            ToolDefinition(
                name="get_category_breakdown",
                description=(
                    "Obtiene el desglose detallado por categoría. "
                    "Usar cuando el usuario pide 'por categoría', 'desglose', o una categoría específica."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "month": {"type": "integer", "description": "Mes (1-12). Default: mes actual."},
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
                description=(
                    "Obtiene los últimos gastos registrados. "
                    "Usar cuando el usuario pide 'últimos gastos', 'historial', 'recientes'."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": "Cantidad de gastos a mostrar (default: 5, max: 20).",
                        },
                    },
                },
                fn=self._get_recent_expenses,
            ),
            ToolDefinition(
                name="delete_last_expense",
                description=(
                    "Elimina el último gasto registrado. "
                    "Usar cuando el usuario pide 'borrar', 'eliminar', 'cancelar el último gasto'."
                ),
                parameters={"type": "object", "properties": {}},
                fn=self._delete_last_expense,
            ),
            ToolDefinition(
                name="search_expenses",
                description=(
                    "Busca gastos por texto en la descripción y/o rango de fechas. "
                    "Usar cuando el usuario pregunta por gastos específicos."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Texto a buscar en la descripción (case-insensitive).",
                        },
                        "date_from": {
                            "type": "string",
                            "description": "Fecha inicio en formato YYYY-MM-DD (inclusive).",
                        },
                        "date_to": {
                            "type": "string",
                            "description": "Fecha fin en formato YYYY-MM-DD (inclusive).",
                        },
                    },
                },
                fn=self._search_expenses,
            ),
            ToolDefinition(
                name="get_sheet_url",
                description=(
                    "Retorna el link a la planilla de Google Sheets del usuario. "
                    "Usar cuando pide 'link', 'planilla', 'excel'."
                ),
                parameters={"type": "object", "properties": {}},
                fn=self._get_sheet_url,
            ),
            ToolDefinition(
                name="calculate",
                description=(
                    "Evalúa una expresión matemática y devuelve el resultado numérico. "
                    "Usar SIEMPRE que el mensaje del usuario involucre cualquier cálculo: "
                    "porcentajes, IVA, impuestos, sumas de varios montos, descuentos, "
                    "propinas, divisiones entre personas, etc. "
                    "Llamar ANTES de register_expense para obtener el monto correcto."
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "expression": {
                            "type": "string",
                            "description": (
                                "Expresión aritmética pura con números y operadores "
                                "(+, -, *, /, paréntesis). "
                                "Ejemplos: '200 - 200 * 0.22', '(200 + 300 + 400) * 1.21', "
                                "'1500 / 3', '850 * 1.03'"
                            ),
                        },
                    },
                    "required": ["expression"],
                },
                fn=self._calculate,
            ),
        ]
