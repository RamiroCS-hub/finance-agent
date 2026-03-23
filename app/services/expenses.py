from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.database import async_session_maker
from app.db.models import Expense, User
from app.models.expense import ParsedExpense
from app.services.timezones import (
    display_datetime_for_phone,
    to_utc,
    utc_window_for_local_date_range,
    utc_window_for_local_month,
)
from app.services.user_service import get_or_create_user, get_user_by_identity

logger = logging.getLogger(__name__)


@dataclass
class ImportReport:
    processed: int = 0
    imported: int = 0
    skipped_duplicates: int = 0
    skipped_invalid: int = 0
    errors: list[str] | None = None

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []

    def to_dict(self) -> dict[str, Any]:
        return {
            "processed": self.processed,
            "imported": self.imported,
            "skipped_duplicates": self.skipped_duplicates,
            "skipped_invalid": self.skipped_invalid,
            "errors": self.errors or [],
        }


class ExpenseService:
    def __init__(self, session_maker: async_sessionmaker | None = None) -> None:
        self.session_maker = session_maker or async_session_maker

    async def ensure_user(self, phone: str) -> bool:
        async with self.session_maker() as session:
            existing = await get_user_by_identity(session, phone)
            if existing is not None:
                return False

            await get_or_create_user(session, phone)
            return True

    async def append_expense(self, phone: str, expense: ParsedExpense) -> Expense | None:
        try:
            async with self.session_maker() as session:
                user = await get_or_create_user(session, phone)
                spent_at, source_timezone = to_utc(
                    expense.spent_at,
                    phone=phone,
                    source_timezone=expense.source_timezone,
                )
                db_expense = Expense(
                    user_id=user.id,
                    spent_at=spent_at,
                    amount=expense.amount,
                    currency=expense.currency,
                    shop=expense.shop,
                    source_timezone=source_timezone,
                    description=expense.description,
                    category=expense.category,
                    calculation=expense.calculation,
                    raw_message=expense.raw_message,
                    source=expense.source,
                    original_amount=expense.original_amount,
                    original_currency=expense.original_currency,
                )
                session.add(db_expense)
                await session.commit()
                await session.refresh(db_expense)
                return db_expense
        except Exception as exc:
            logger.error("Error guardando gasto para %s en DB: %s", phone, exc)
            return None

    async def get_monthly_total(self, phone: str, month: int, year: int) -> float:
        expenses = await self._get_expenses_in_period(phone, month, year)
        return round(sum(expense.amount for expense in expenses), 2)

    async def get_category_totals(self, phone: str, month: int, year: int) -> dict[str, float]:
        expenses = await self._get_expenses_in_period(phone, month, year)
        totals: dict[str, float] = {}
        for expense in expenses:
            totals[expense.category] = round(
                totals.get(expense.category, 0.0) + expense.amount, 2
            )
        return totals

    async def get_recent_expenses(self, phone: str, n: int = 10) -> list[dict]:
        async with self.session_maker() as session:
            user = await self._get_user(session, phone)
            if user is None:
                return []

            query = (
                select(Expense)
                .where(Expense.user_id == user.id)
                .order_by(Expense.spent_at.desc(), Expense.id.desc())
                .limit(n)
            )
            result = await session.execute(query)
            expenses = result.scalars().all()
            return [self._serialize_expense(expense, phone=phone) for expense in expenses]

    async def search_expenses(
        self,
        phone: str,
        query: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[dict]:
        async with self.session_maker() as session:
            user = await self._get_user(session, phone)
            if user is None:
                return []

            stmt = select(Expense).where(Expense.user_id == user.id)
            if query:
                stmt = stmt.where(Expense.description.ilike(f"%{query}%"))
            start, end = utc_window_for_local_date_range(phone, date_from, date_to)
            if start is not None:
                stmt = stmt.where(Expense.spent_at >= start)
            if end is not None:
                stmt = stmt.where(Expense.spent_at <= end)

            stmt = stmt.order_by(Expense.spent_at.asc(), Expense.id.asc())
            result = await session.execute(stmt)
            expenses = result.scalars().all()
            return [self._serialize_expense(expense, phone=phone) for expense in expenses]

    async def delete_last_expense(self, phone: str) -> dict | None:
        async with self.session_maker() as session:
            user = await self._get_user(session, phone)
            if user is None:
                return None

            stmt = (
                select(Expense)
                .where(Expense.user_id == user.id)
                .order_by(Expense.spent_at.desc(), Expense.id.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            expense = result.scalar_one_or_none()
            if expense is None:
                return None

            payload = self._serialize_expense(expense, phone=phone)
            await session.delete(expense)
            await session.commit()
            return payload

    async def import_from_sheets(
        self,
        sheets_service: Any,
        phone: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        phones = [phone] if phone else list(sheets_service.list_user_phones())
        report = ImportReport()

        async with self.session_maker() as session:
            for current_phone in phones:
                user = await get_or_create_user(session, current_phone)
                for row in sheets_service.export_expenses(current_phone):
                    report.processed += 1

                    try:
                        spent_at = self._parse_sheet_datetime(row["fecha"], row["hora"])
                        spent_at_utc, source_timezone = to_utc(
                            spent_at,
                            phone=current_phone,
                        )
                        amount = float(row["monto"])
                    except (KeyError, TypeError, ValueError) as exc:
                        report.skipped_invalid += 1
                        report.errors.append(f"{current_phone}: fila inválida ({exc})")
                        continue

                    duplicate_stmt = select(Expense.id).where(
                        Expense.user_id == user.id,
                        Expense.spent_at == spent_at_utc,
                        Expense.amount == amount,
                        Expense.currency == (row.get("moneda") or ""),
                        Expense.description == (row.get("descripcion") or ""),
                        Expense.category == (row.get("categoria") or "General"),
                        Expense.raw_message == (row.get("mensaje_original") or ""),
                    )
                    duplicate_res = await session.execute(duplicate_stmt)
                    if duplicate_res.scalar_one_or_none() is not None:
                        report.skipped_duplicates += 1
                        continue

                    if dry_run:
                        report.imported += 1
                        continue

                    session.add(
                        Expense(
                            user_id=user.id,
                            spent_at=spent_at_utc,
                            amount=amount,
                            currency=row.get("moneda") or "",
                            shop=row.get("shop") or None,
                            source_timezone=source_timezone,
                            description=row.get("descripcion") or "",
                            category=row.get("categoria") or "General",
                            calculation=row.get("calculo") or None,
                            raw_message=row.get("mensaje_original") or "",
                            source="sheets_import",
                            original_amount=self._parse_optional_float(
                                row.get("monto_original")
                            ),
                            original_currency=row.get("moneda_original") or None,
                        )
                    )
                    report.imported += 1

            if not dry_run:
                await session.commit()

        return report.to_dict()

    async def _get_expenses_in_period(
        self,
        phone: str,
        month: int,
        year: int,
    ) -> list[Expense]:
        async with self.session_maker() as session:
            user = await self._get_user(session, phone)
            if user is None:
                return []

            start, end = utc_window_for_local_month(phone, year, month)

            stmt = (
                select(Expense)
                .where(
                    Expense.user_id == user.id,
                    Expense.spent_at >= start,
                    Expense.spent_at < end,
                )
                .order_by(Expense.spent_at.asc(), Expense.id.asc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def _get_user(self, session, phone: str) -> User | None:
        return await get_user_by_identity(session, phone)

    def _serialize_expense(
        self,
        expense: Expense,
        phone: str | None = None,
    ) -> dict[str, Any]:
        localized = display_datetime_for_phone(
            expense.spent_at,
            phone=phone or getattr(getattr(expense, "user", None), "whatsapp_number", None),
            source_timezone=getattr(expense, "source_timezone", None),
        )
        return {
            "expense_id": expense.id,
            "fecha": localized.strftime("%Y-%m-%d"),
            "hora": localized.strftime("%H:%M"),
            "monto": float(expense.amount),
            "moneda": expense.currency,
            "shop": getattr(expense, "shop", None),
            "source_timezone": getattr(expense, "source_timezone", None),
            "descripcion": expense.description,
            "categoria": expense.category,
        }

    def _parse_sheet_datetime(self, date_value: str, time_value: str) -> datetime:
        time_part = time_value or "00:00"
        return datetime.strptime(f"{date_value} {time_part}", "%Y-%m-%d %H:%M")

    def _parse_optional_float(self, value: Any) -> float | None:
        if value in (None, ""):
            return None
        return float(value)
