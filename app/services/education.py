from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import settings
from app.db.database import async_session_maker
from app.db.models import Expense, User
from app.services.insights import SpendingInsightsService
from app.services.timezones import DB_ZONE, local_now_for_phone
from app.services.user_service import get_user_by_identity

ESSENTIAL_CATEGORIES = {
    "Hogar",
    "Supermercado",
    "Salud",
    "Transporte",
    "Educación",
    "Comida",
}


class EducationService:
    def __init__(
        self,
        session_maker: async_sessionmaker | None = None,
        insights_service: SpendingInsightsService | None = None,
    ) -> None:
        self.session_maker = session_maker or async_session_maker
        self.insights_service = insights_service or SpendingInsightsService(
            session_maker=self.session_maker
        )

    async def evaluate_financial_education(self, phone: str) -> dict[str, Any]:
        async with self.session_maker() as session:
            user = await self._get_user(session, phone)
            if user is None:
                return self._insufficient()

            recent_expenses = await self._load_recent_expenses(session, user.id, phone)
            if len(recent_expenses) < 5:
                return self._insufficient()

        benchmark = self._build_benchmark(recent_expenses)
        emergency = self._build_emergency_fund(benchmark["average_monthly_spend"])
        inflation = await self._build_inflation_comparison(phone, benchmark["average_monthly_spend"])
        tips = await self.generate_personalized_tips(phone, benchmark)

        return {
            "status": "ok",
            "benchmark_50_30_20": benchmark,
            "emergency_fund": emergency,
            "inflation_adjusted_comparison": inflation,
            "tips": tips,
            "disclaimer": (
                "Esta lectura usa gasto observado y no ingresos reales; tomala como guía educativa, no como diagnóstico financiero completo."
            ),
        }

    async def generate_personalized_tips(
        self,
        phone: str,
        benchmark: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        tips: list[dict[str, Any]] = []
        if benchmark and benchmark["wants_ratio"] > 30:
            excess = round(
                benchmark["average_monthly_spend"] * ((benchmark["wants_ratio"] - 30) / 100.0),
                2,
            )
            tips.append(
                {
                    "type": "wants_ratio",
                    "message": (
                        f"Tus gastos discrecionales están en {benchmark['wants_ratio']:.1f}% del gasto observado. "
                        f"Recortar ~${excess:.2f} por mes te acercaría a una regla 50/30/20."
                    ),
                }
            )

        leak_payload = await self.insights_service.detect_spending_leaks(phone)
        if leak_payload.get("status") == "ok":
            repetitive = next(
                (
                    item
                    for item in leak_payload.get("insights", [])
                    if item.get("type") == "repetitive_merchant"
                ),
                None,
            )
            if repetitive is not None:
                tips.append(
                    {
                        "type": "repetitive_merchant",
                        "message": (
                            f"Ojo con {repetitive['merchant']}: ahí se te fueron "
                            f"${repetitive['impact_amount']:.2f} recientemente."
                        ),
                    }
                )
        return tips[:3]

    async def _build_inflation_comparison(
        self,
        phone: str,
        average_monthly_spend: float,
    ) -> dict[str, Any]:
        rate = float(settings.MONTHLY_INFLATION_RATE)
        if rate <= 0:
            return {
                "status": "nominal_only",
                "message": "No hay índice de inflación configurado; la lectura queda en términos nominales.",
            }

        comparison = await self.insights_service.compare_spending_periods(
            phone,
            period="monthly",
            group_by="category",
        )
        if comparison.get("status") != "ok":
            return {
                "status": "nominal_only",
                "message": "No hubo suficiente histórico comparable para ajustar por inflación.",
            }

        nominal_delta = comparison["current_total"] - comparison["previous_total"]
        adjusted_current = comparison["current_total"] / (1 + rate)
        real_delta = round(adjusted_current - comparison["previous_total"], 2)
        return {
            "status": "ok",
            "monthly_inflation_rate": rate,
            "nominal_delta": round(nominal_delta, 2),
            "real_delta": real_delta,
            "message": (
                f"Con inflación mensual de referencia {rate:.2%}, el cambio real estimado fue ${real_delta:.2f}."
            ),
        }

    async def _load_recent_expenses(self, session, user_id: int, phone: str) -> list[Expense]:
        local_now = local_now_for_phone(phone)
        start = (local_now - timedelta(days=90)).astimezone(DB_ZONE)
        end = local_now.astimezone(DB_ZONE)
        result = await session.execute(
            select(Expense).where(
                Expense.user_id == user_id,
                Expense.spent_at >= start,
                Expense.spent_at < end,
            )
        )
        return list(result.scalars().all())

    async def _get_user(self, session, phone: str) -> User | None:
        return await get_user_by_identity(session, phone)

    def _build_benchmark(self, expenses: list[Expense]) -> dict[str, Any]:
        monthly_totals: dict[str, float] = defaultdict(float)
        essential_total = 0.0
        total = 0.0
        for expense in expenses:
            month_key = expense.spent_at.strftime("%Y-%m")
            amount = float(expense.amount)
            monthly_totals[month_key] += amount
            total += amount
            if expense.category in ESSENTIAL_CATEGORIES:
                essential_total += amount

        months = max(len(monthly_totals), 1)
        average_monthly_spend = round(total / months, 2)
        essential_monthly = round(essential_total / months, 2)
        discretionary_monthly = round(max(average_monthly_spend - essential_monthly, 0.0), 2)
        needs_ratio = round((essential_monthly / average_monthly_spend) * 100, 1)
        wants_ratio = round((discretionary_monthly / average_monthly_spend) * 100, 1)
        return {
            "average_monthly_spend": average_monthly_spend,
            "basis": "observed_spend",
            "framework": "50/30/20 adaptado sobre gasto observado",
            "needs_ratio": needs_ratio,
            "wants_ratio": wants_ratio,
            "target_savings_ratio": 20.0,
            "illustrative_monthly_buffer_target": round(average_monthly_spend * 0.2, 2),
            "disclaimer": (
                "Sin ingresos registrados, la comparación 50/30/20 se estima solo sobre la mezcla de tus gastos."
            ),
        }

    def _build_emergency_fund(self, average_monthly_spend: float) -> dict[str, Any]:
        return {
            "recommended_min": round(average_monthly_spend * 3, 2),
            "recommended_max": round(average_monthly_spend * 6, 2),
        }

    def _insufficient(self) -> dict[str, Any]:
        return {
            "status": "insufficient_data",
            "message": "Todavía no tengo suficiente histórico para darte una lectura educativa confiable.",
        }
