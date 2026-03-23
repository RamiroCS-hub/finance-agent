from __future__ import annotations

from statistics import mean, median

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.database import async_session_maker
from app.db.models import BudgetRule, Expense, User
from app.services.timezones import display_datetime_for_phone, utc_window_for_local_month


class AlertService:
    def __init__(self, session_maker: async_sessionmaker | None = None) -> None:
        self.session_maker = session_maker or async_session_maker

    async def evaluate_expense_alerts(
        self,
        phone: str,
        amount: float,
        category: str,
        spent_at,
    ) -> list[dict]:
        async with self.session_maker() as session:
            user = await self._get_user(session, phone)
            if user is None:
                return []

            alerts: list[dict] = []
            local_spent_at = display_datetime_for_phone(spent_at, phone)
            start, end = utc_window_for_local_month(phone, local_spent_at.year, local_spent_at.month)

            budget_query = select(BudgetRule).where(
                BudgetRule.user_id == user.id,
                BudgetRule.category == category,
                BudgetRule.period == "monthly",
                BudgetRule.is_active.is_(True),
            )
            budget_result = await session.execute(budget_query)
            budget_rule = budget_result.scalar_one_or_none()
            if budget_rule is not None:
                total_query = select(Expense).where(
                    Expense.user_id == user.id,
                    Expense.category == category,
                    Expense.spent_at >= start,
                    Expense.spent_at < end,
                )
                total_result = await session.execute(total_query)
                expenses = total_result.scalars().all()
                total = round(sum(expense.amount for expense in expenses), 2)
                if total > budget_rule.limit_amount:
                    alerts.append(
                        {
                            "type": "budget_exceeded",
                            "message": (
                                f"Alerta: superaste tu presupuesto de {category}. "
                                f"Vas {total} sobre un límite de {budget_rule.limit_amount}."
                            ),
                        }
                    )

            recent_query = (
                select(Expense)
                .where(Expense.user_id == user.id, Expense.category == category)
                .order_by(Expense.spent_at.desc(), Expense.id.desc())
                .limit(6)
            )
            recent_result = await session.execute(recent_query)
            recent_expenses = recent_result.scalars().all()
            historical_amounts = [
                float(expense.amount)
                for expense in recent_expenses
                if round(float(expense.amount), 2) != round(float(amount), 2)
            ]
            if len(historical_amounts) >= 3:
                avg = mean(historical_amounts)
                med = median(historical_amounts)
                if amount >= avg * 2 and amount >= med * 1.75:
                    alerts.append(
                        {
                            "type": "spike_detected",
                            "message": (
                                f"Alerta: este gasto en {category} parece inusualmente alto "
                                f"frente a tu histórico reciente."
                            ),
                        }
                    )

            return alerts

    async def _get_user(self, session, phone: str) -> User | None:
        result = await session.execute(select(User).where(User.whatsapp_number == phone))
        return result.scalar_one_or_none()
