from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.database import async_session_maker
from app.db.models import BudgetRule, User
from app.services.user_service import get_or_create_user, get_user_by_identity


class BudgetService:
    def __init__(self, session_maker: async_sessionmaker | None = None) -> None:
        self.session_maker = session_maker or async_session_maker

    async def save_budget(
        self,
        phone: str,
        category: str,
        limit_amount: float,
        period: str = "monthly",
    ) -> dict:
        async with self.session_maker() as session:
            user = await get_or_create_user(session, phone)
            query = select(BudgetRule).where(
                BudgetRule.user_id == user.id,
                BudgetRule.category == category,
                BudgetRule.period == period,
                BudgetRule.is_active.is_(True),
            )
            result = await session.execute(query)
            rule = result.scalar_one_or_none()
            action = "updated"
            if rule is None:
                rule = BudgetRule(
                    user_id=user.id,
                    category=category,
                    period=period,
                    limit_amount=limit_amount,
                    is_active=True,
                )
                session.add(rule)
                action = "created"
            else:
                rule.limit_amount = limit_amount
                rule.is_active = True

            await session.commit()
            return {
                "status": action,
                "category": category,
                "period": period,
                "limit_amount": limit_amount,
            }

    async def list_budgets(self, phone: str) -> list[dict]:
        async with self.session_maker() as session:
            user = await self._get_user(session, phone)
            if user is None:
                return []

            query = (
                select(BudgetRule)
                .where(BudgetRule.user_id == user.id, BudgetRule.is_active.is_(True))
                .order_by(BudgetRule.category.asc())
            )
            result = await session.execute(query)
            rules = result.scalars().all()
            return [
                {
                    "category": rule.category,
                    "period": rule.period,
                    "limit_amount": float(rule.limit_amount),
                }
                for rule in rules
            ]

    async def get_budget_rule(
        self,
        phone: str,
        category: str,
        period: str = "monthly",
    ) -> BudgetRule | None:
        async with self.session_maker() as session:
            user = await self._get_user(session, phone)
            if user is None:
                return None

            query = select(BudgetRule).where(
                BudgetRule.user_id == user.id,
                BudgetRule.category == category,
                BudgetRule.period == period,
                BudgetRule.is_active.is_(True),
            )
            result = await session.execute(query)
            return result.scalar_one_or_none()

    async def _get_user(self, session, phone: str) -> User | None:
        return await get_user_by_identity(session, phone)
