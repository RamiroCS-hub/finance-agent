from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.database import async_session_maker
from app.db.models import Liability, User
from app.services.user_service import get_or_create_user


class LiabilityService:
    def __init__(self, session_maker: async_sessionmaker | None = None) -> None:
        self.session_maker = session_maker or async_session_maker

    async def create_liability(
        self,
        phone: str,
        kind: str,
        description: str,
        monthly_amount: float,
        remaining_periods: int,
        currency: str = "ARS",
    ) -> dict:
        if not description or monthly_amount <= 0 or remaining_periods <= 0:
            return {
                "success": False,
                "error": "Necesito descripción, monto mensual positivo y períodos restantes.",
            }

        async with self.session_maker() as session:
            user = await get_or_create_user(session, phone)
            liability = Liability(
                user_id=user.id,
                kind=kind,
                description=description,
                currency=currency,
                monthly_amount=float(monthly_amount),
                remaining_periods=int(remaining_periods),
                status="active",
            )
            session.add(liability)
            await session.commit()
            await session.refresh(liability)
            label = "Cuotas restantes" if liability.kind == "installment" else "Períodos restantes"
            return {
                "success": True,
                "liability_id": liability.id,
                "kind": liability.kind,
                "description": liability.description,
                "monthly_amount": float(liability.monthly_amount),
                "remaining_periods": liability.remaining_periods,
                "currency": liability.currency,
                "formatted_confirmation": (
                    f"✅ Registré la obligación: *{liability.description}*\n"
                    f"- {label}: {liability.remaining_periods}\n"
                    f"- Monto mensual: *${self._format_currency(float(liability.monthly_amount))}*"
                ),
            }

    async def get_monthly_commitment(self, phone: str) -> dict:
        async with self.session_maker() as session:
            user = await self._get_user(session, phone)
            if user is None:
                return self._empty_commitment()

            result = await session.execute(
                select(Liability).where(
                    Liability.user_id == user.id,
                    Liability.status == "active",
                    Liability.remaining_periods > 0,
                )
            )
            liabilities = list(result.scalars().all())
            if not liabilities:
                return self._empty_commitment()

            total_monthly = round(sum(float(item.monthly_amount) for item in liabilities), 2)
            total_remaining = round(
                sum(float(item.monthly_amount) * item.remaining_periods for item in liabilities),
                2,
            )
            return {
                "success": True,
                "total_monthly_commitment": total_monthly,
                "total_remaining_commitment": total_remaining,
                "count": len(liabilities),
                "liabilities": [
                    {
                        "liability_id": item.id,
                        "kind": item.kind,
                        "description": item.description,
                        "monthly_amount": float(item.monthly_amount),
                        "remaining_periods": item.remaining_periods,
                        "currency": item.currency,
                    }
                    for item in liabilities
                ],
            }

    async def close_liability(self, phone: str, liability_id: int) -> dict:
        async with self.session_maker() as session:
            user = await self._get_user(session, phone)
            if user is None:
                return {"success": False, "error": "Obligación no encontrada."}

            result = await session.execute(
                select(Liability).where(
                    Liability.id == int(liability_id),
                    Liability.user_id == user.id,
                    Liability.status == "active",
                )
            )
            liability = result.scalar_one_or_none()
            if liability is None:
                return {"success": False, "error": "Obligación inexistente o ya cerrada."}

            liability.status = "closed"
            liability.remaining_periods = 0
            await session.commit()
            return {
                "success": True,
                "liability_id": liability.id,
                "status": liability.status,
            }

    async def _get_user(self, session, phone: str) -> User | None:
        result = await session.execute(select(User).where(User.whatsapp_number == phone))
        return result.scalar_one_or_none()

    def _empty_commitment(self) -> dict:
        return {
            "success": True,
            "total_monthly_commitment": 0.0,
            "total_remaining_commitment": 0.0,
            "count": 0,
            "liabilities": [],
        }

    def _format_currency(self, value: float) -> str:
        return f"{value:,.0f}".replace(",", ".")
