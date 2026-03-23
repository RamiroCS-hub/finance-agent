from __future__ import annotations

from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.database import async_session_maker
from app.db.models import Expense, Goal, User
from app.services.timezones import DB_ZONE, local_now_for_phone
from app.services.user_service import get_user_by_identity


class SavingsProjectionService:
    def __init__(self, session_maker: async_sessionmaker | None = None) -> None:
        self.session_maker = session_maker or async_session_maker

    async def project_savings(
        self,
        phone: str,
        amount: float | None = None,
        frequency: str | None = None,
        horizon_months: int = 6,
        category: str | None = None,
        reduction_percent: float | None = None,
    ) -> dict[str, Any]:
        if amount is None and category is None:
            return self._clarification_response(
                "Necesito un monto manual o una categoría para proyectar."
            )

        if amount is not None and not frequency:
            return self._clarification_response(
                "Decime si ese ahorro sería semanal o mensual."
            )

        if category is not None and reduction_percent is None:
            return self._clarification_response(
                "Decime qué porcentaje querés recortar de esa categoría."
            )

        frequency = (frequency or "monthly").lower()
        if frequency not in {"weekly", "monthly"}:
            return self._clarification_response(
                "La frecuencia soportada es weekly o monthly."
            )

        horizon_months = max(int(horizon_months), 1)

        async with self.session_maker() as session:
            user = await self._get_user(session, phone)
            active_goal = await self._get_active_goal(session, user.id) if user else None

            if amount is not None:
                periodic_saving = round(float(amount), 2)
                source = "manual"
                assumptions = [
                    f"Supuesto manual: ahorrar ${periodic_saving:.2f} por {self._frequency_label(frequency)}."
                ]
            else:
                if user is None:
                    return {
                        "status": "insufficient_data",
                        "message": "No encontré histórico suficiente para estimarlo; si querés, pasame un monto manual.",
                    }

                historical_average = await self._historical_average_for_category(
                    session,
                    user.id,
                    phone,
                    category or "",
                    frequency,
                )
                if historical_average is None:
                    return {
                        "status": "insufficient_data",
                        "message": (
                            "Todavía no tengo suficiente histórico en esa categoría. "
                            "Si querés, te lo simulo con un monto manual."
                        ),
                    }

                periodic_saving = round(
                    historical_average * (float(reduction_percent or 0) / 100.0),
                    2,
                )
                source = "historical"
                assumptions = [
                    (
                        f"Base histórica: {category} promedia ${historical_average:.2f} "
                        f"por {self._frequency_label(frequency)}."
                    ),
                    f"Escenario: recorte del {float(reduction_percent):.1f}%.",
                ]

        periods = horizon_months if frequency == "monthly" else horizon_months * 4
        projected_savings = round(periodic_saving * periods, 2)

        payload: dict[str, Any] = {
            "status": "ok",
            "source": source,
            "frequency": frequency,
            "horizon_months": horizon_months,
            "periodic_saving": periodic_saving,
            "projected_savings": projected_savings,
            "assumptions": assumptions,
        }
        if category:
            payload["category"] = category
        if reduction_percent is not None:
            payload["reduction_percent"] = float(reduction_percent)

        if active_goal is not None:
            projected_goal_total = round(
                float(active_goal.current_amount) + projected_savings,
                2,
            )
            payload["goal_impact"] = {
                "target_amount": float(active_goal.target_amount),
                "current_amount": float(active_goal.current_amount),
                "projected_total": projected_goal_total,
                "remaining_after_projection": max(
                    round(float(active_goal.target_amount) - projected_goal_total, 2),
                    0.0,
                ),
                "reaches_goal": projected_goal_total >= float(active_goal.target_amount),
            }
        return payload

    async def _historical_average_for_category(
        self,
        session,
        user_id: int,
        phone: str,
        category: str,
        frequency: str,
    ) -> float | None:
        local_now = local_now_for_phone(phone)
        window_days = 84 if frequency == "weekly" else 90
        start = (local_now - timedelta(days=window_days)).astimezone(DB_ZONE)
        end = local_now.astimezone(DB_ZONE)
        query = (
            select(Expense)
            .where(
                Expense.user_id == user_id,
                Expense.category == category,
                Expense.spent_at >= start,
                Expense.spent_at < end,
            )
            .order_by(Expense.spent_at.asc(), Expense.id.asc())
        )
        result = await session.execute(query)
        expenses = list(result.scalars().all())
        if len(expenses) < 3:
            return None

        total = sum(float(expense.amount) for expense in expenses)
        periods = 12 if frequency == "weekly" else 3
        return round(total / periods, 2)

    async def _get_user(self, session, phone: str) -> User | None:
        return await get_user_by_identity(session, phone)

    async def _get_active_goal(self, session, user_id: int) -> Goal | None:
        result = await session.execute(
            select(Goal).where(Goal.user_id == user_id, Goal.status == "active")
        )
        return result.scalar_one_or_none()

    def _clarification_response(self, message: str) -> dict[str, Any]:
        return {
            "status": "needs_clarification",
            "message": message,
        }

    def _frequency_label(self, frequency: str) -> str:
        return "semana" if frequency == "weekly" else "mes"
