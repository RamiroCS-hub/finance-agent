from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from app.db.database import async_session_maker
from app.db.models import Group, GroupExpense, GroupExpenseShare, GroupMember, User
from app.services.group_service import ensure_group_member
from app.services.timezones import display_datetime_for_phone, to_utc
from app.services.user_service import get_or_create_user

logger = logging.getLogger(__name__)


@dataclass
class BalanceRow:
    phone: str
    paid: float
    owes: float

    @property
    def net(self) -> float:
        return round(self.paid - self.owes, 2)


def split_amount_evenly(amount: float, count: int) -> list[float]:
    if count <= 0:
        return []
    cents = round(amount * 100)
    base = cents // count
    remainder = cents % count
    shares = []
    for index in range(count):
        extra = 1 if index < remainder else 0
        shares.append((base + extra) / 100)
    return shares


def minimize_settlements(rows: list[BalanceRow]) -> list[dict]:
    creditors = []
    debtors = []
    for row in rows:
        net = round(row.net, 2)
        if net > 0:
            creditors.append({"phone": row.phone, "amount": net})
        elif net < 0:
            debtors.append({"phone": row.phone, "amount": abs(net)})

    transfers: list[dict] = []
    creditor_index = 0
    debtor_index = 0
    while creditor_index < len(creditors) and debtor_index < len(debtors):
        creditor = creditors[creditor_index]
        debtor = debtors[debtor_index]
        amount = round(min(creditor["amount"], debtor["amount"]), 2)
        if amount > 0:
            transfers.append(
                {
                    "from": debtor["phone"],
                    "to": creditor["phone"],
                    "amount": amount,
                }
            )
        creditor["amount"] = round(creditor["amount"] - amount, 2)
        debtor["amount"] = round(debtor["amount"] - amount, 2)
        if creditor["amount"] == 0:
            creditor_index += 1
        if debtor["amount"] == 0:
            debtor_index += 1
    return transfers


class GroupExpenseService:
    def __init__(self, session_maker: async_sessionmaker | None = None) -> None:
        self.session_maker = session_maker or async_session_maker

    async def register_group_expense(
        self,
        whatsapp_group_id: str,
        payer_phone: str,
        amount: float,
        description: str,
        category: str = "General",
        currency: str = "ARS",
        shop: str | None = None,
        spent_at=None,
        source_timezone: str | None = None,
        split_member_phones: list[str] | None = None,
    ) -> dict:
        async with self.session_maker() as session:
            group, payer, _ = await ensure_group_member(
                session,
                whatsapp_group_id,
                payer_phone,
            )
            participants = await self._resolve_participants(
                session, group, split_member_phones, payer_phone
            )
            shares = split_amount_evenly(amount, len(participants))
            spent_at_utc, effective_timezone = to_utc(
                spent_at,
                phone=payer_phone,
                source_timezone=source_timezone,
            )

            expense = GroupExpense(
                group_id=group.id,
                payer_user_id=payer.id,
                spent_at=spent_at_utc,
                amount=amount,
                currency=currency,
                shop=shop,
                source_timezone=effective_timezone,
                description=description,
                category=category,
            )
            session.add(expense)
            await session.flush()

            for user, share_amount in zip(participants, shares, strict=False):
                session.add(
                    GroupExpenseShare(
                        expense_id=expense.id,
                        user_id=user.id,
                        share_amount=share_amount,
                    )
                )

            await session.commit()
            await session.refresh(expense)
            return {
                "success": True,
                "group_expense_id": expense.id,
                "group_id": whatsapp_group_id,
                "payer_phone": payer_phone,
                "participants": [user.whatsapp_number for user in participants],
                "shares": shares,
                "amount": amount,
                "shop": shop,
                "source_timezone": effective_timezone,
                "description": description,
                "category": category,
                "currency": currency,
            }

    async def get_group_balance(
        self,
        whatsapp_group_id: str,
        requester_phone: str,
    ) -> dict:
        async with self.session_maker() as session:
            group = await self._load_group(session, whatsapp_group_id)
            if group is None:
                return {"success": False, "error": "Grupo no encontrado"}

            if not any(
                membership.user.whatsapp_number == requester_phone
                for membership in group.members
            ):
                return {"success": False, "error": "No perteneces a este grupo"}

            rows = self._compute_balance_rows(group)
            return {
                "success": True,
                "group_id": whatsapp_group_id,
                "members": [
                    {
                        "phone": row.phone,
                        "paid": row.paid,
                        "owes": row.owes,
                        "net": row.net,
                    }
                    for row in rows
                ],
            }

    async def settle_group(
        self,
        whatsapp_group_id: str,
        requester_phone: str,
    ) -> dict:
        balance = await self.get_group_balance(whatsapp_group_id, requester_phone)
        if not balance.get("success"):
            return balance

        rows = [
            BalanceRow(
                phone=member["phone"],
                paid=member["paid"],
                owes=member["owes"],
            )
            for member in balance["members"]
        ]
        return {
            "success": True,
            "group_id": whatsapp_group_id,
            "transfers": minimize_settlements(rows),
        }

    def _compute_balance_rows(self, group: Group) -> list[BalanceRow]:
        paid_by_user: dict[str, float] = {}
        owes_by_user: dict[str, float] = {}

        for membership in group.members:
            phone = membership.user.whatsapp_number
            paid_by_user.setdefault(phone, 0.0)
            owes_by_user.setdefault(phone, 0.0)

        for expense in group.expenses:
            payer_phone = expense.payer.whatsapp_number
            paid_by_user[payer_phone] = round(
                paid_by_user.get(payer_phone, 0.0) + expense.amount, 2
            )
            for share in expense.shares:
                phone = share.user.whatsapp_number
                owes_by_user[phone] = round(
                    owes_by_user.get(phone, 0.0) + share.share_amount, 2
                )

        rows = [
            BalanceRow(phone=phone, paid=paid_by_user[phone], owes=owes_by_user[phone])
            for phone in sorted(paid_by_user.keys())
        ]
        return rows

    async def _load_group(self, session: AsyncSession, whatsapp_group_id: str) -> Group | None:
        query = (
            select(Group)
            .where(Group.whatsapp_group_id == whatsapp_group_id)
            .options(
                selectinload(Group.members).selectinload(GroupMember.user),
                selectinload(Group.expenses).selectinload(GroupExpense.payer),
                selectinload(Group.expenses)
                .selectinload(GroupExpense.shares)
                .selectinload(GroupExpenseShare.user),
            )
        )
        result = await session.execute(query)
        return result.scalar_one_or_none()

    async def _resolve_participants(
        self,
        session: AsyncSession,
        group: Group,
        split_member_phones: list[str] | None,
        payer_phone: str,
    ) -> list[User]:
        if split_member_phones:
            participants: list[User] = []
            for phone in split_member_phones:
                _, user, _ = await ensure_group_member(
                    session, group.whatsapp_group_id, phone
                )
                participants.append(user)
            return participants

        memberships = await session.execute(
            select(GroupMember)
            .where(GroupMember.group_id == group.id)
            .options(selectinload(GroupMember.user))
        )
        members = memberships.scalars().all()
        if not members:
            user = await get_or_create_user(session, payer_phone)
            return [user]
        return [membership.user for membership in members]
