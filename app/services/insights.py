from __future__ import annotations

import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.database import async_session_maker
from app.db.models import Expense, User
from app.services.timezones import DB_ZONE, local_now_for_phone
from app.services.user_service import get_user_by_identity

logger = logging.getLogger(__name__)


class SpendingInsightsService:
    def __init__(self, session_maker: async_sessionmaker | None = None) -> None:
        self.session_maker = session_maker or async_session_maker

    async def compare_spending_periods(
        self,
        phone: str,
        period: str = "monthly",
        group_by: str = "category",
    ) -> dict[str, Any]:
        async with self.session_maker() as session:
            user = await self._get_user(session, phone)
            if user is None:
                return self._empty_comparison(period, group_by)

            local_now = local_now_for_phone(phone)
            current_start, current_end, current_label = self._get_period_window(
                phone, local_now, period=period, offset=0
            )
            previous_start, previous_end, previous_label = self._get_period_window(
                phone, local_now, period=period, offset=-1
            )

            current_expenses = await self._load_expenses_between(
                session, user.id, current_start, current_end
            )
            previous_expenses = await self._load_expenses_between(
                session, user.id, previous_start, previous_end
            )

        if not current_expenses or not previous_expenses:
            return self._empty_comparison(period, group_by)

        current_totals = self._aggregate_expenses(current_expenses, group_by)
        previous_totals = self._aggregate_expenses(previous_expenses, group_by)
        if not current_totals and not previous_totals:
            return self._empty_comparison(period, group_by)

        changes: list[dict[str, Any]] = []
        for key in sorted(set(current_totals) | set(previous_totals)):
            current_total = round(current_totals.get(key, 0.0), 2)
            previous_total = round(previous_totals.get(key, 0.0), 2)
            delta = round(current_total - previous_total, 2)
            baseline = previous_total if previous_total > 0 else current_total
            delta_pct = round((delta / baseline) * 100, 1) if baseline else 0.0
            if current_total == 0 and previous_total == 0:
                continue
            changes.append(
                {
                    "key": key,
                    "current_total": current_total,
                    "previous_total": previous_total,
                    "delta": delta,
                    "delta_pct": delta_pct,
                    "trend": "up" if delta > 0 else "down" if delta < 0 else "flat",
                }
            )

        changes.sort(key=lambda item: abs(item["delta"]), reverse=True)
        if not changes:
            return self._empty_comparison(period, group_by)

        top_change = changes[0]
        direction = "subió" if top_change["delta"] > 0 else "bajó"
        headline = (
            f"{top_change['key']} {direction} ${abs(top_change['delta']):.2f} "
            f"vs {previous_label}."
        )

        return {
            "status": "ok",
            "period": period,
            "group_by": group_by,
            "current_label": current_label,
            "previous_label": previous_label,
            "current_total": round(sum(current_totals.values()), 2),
            "previous_total": round(sum(previous_totals.values()), 2),
            "headline": headline,
            "changes": changes[:5],
        }

    async def detect_spending_leaks(self, phone: str) -> dict[str, Any]:
        async with self.session_maker() as session:
            user = await self._get_user(session, phone)
            if user is None:
                return self._empty_insights()

            local_now = local_now_for_phone(phone)
            recent_end = (local_now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            recent_start = recent_end - timedelta(days=90)
            recent_expenses = await self._load_expenses_between(
                session,
                user.id,
                recent_start.astimezone(DB_ZONE),
                recent_end.astimezone(DB_ZONE),
            )

        if len(recent_expenses) < 4:
            return self._empty_insights()

        comparison = await self.compare_spending_periods(
            phone,
            period="monthly",
            group_by="category",
        )

        insights: list[dict[str, Any]] = []
        if comparison.get("status") == "ok":
            rising = next(
                (
                    change
                    for change in comparison["changes"]
                    if change["delta"] > 0 and change["current_total"] >= 1000
                ),
                None,
            )
            if rising is not None:
                insights.append(
                    {
                        "type": "category_growth",
                        "title": f"Suba en {rising['key']}",
                        "impact_amount": rising["delta"],
                        "message": (
                            f"{rising['key']} subió ${rising['delta']:.2f} "
                            f"frente a {comparison['previous_label']}."
                        ),
                    }
                )

        by_merchant: dict[str, list[Expense]] = defaultdict(list)
        total_recent = round(sum(float(expense.amount) for expense in recent_expenses), 2)
        for expense in recent_expenses:
            merchant_key = self._merchant_key(expense)
            if merchant_key:
                by_merchant[merchant_key].append(expense)

        repetitive_candidates: list[dict[str, Any]] = []
        for merchant, expenses in by_merchant.items():
            count = len(expenses)
            if count < 3:
                continue

            total = round(sum(float(expense.amount) for expense in expenses), 2)
            if total < max(1000.0, total_recent * 0.05):
                continue

            avg_amount = round(total / count, 2)
            repetitive_candidates.append(
                {
                    "type": "repetitive_merchant",
                    "title": f"Gasto repetido en {merchant}",
                    "merchant": merchant,
                    "count": count,
                    "impact_amount": total,
                    "avg_amount": avg_amount,
                    "message": (
                        f"En los últimos 90 días gastaste ${total:.2f} en {merchant} "
                        f"repartidos en {count} consumos."
                    ),
                }
            )

        repetitive_candidates.sort(key=lambda item: item["impact_amount"], reverse=True)
        insights.extend(repetitive_candidates[:2])

        if not insights:
            return {
                "status": "no_strong_findings",
                "message": "No veo una fuga clara todavía; necesitás más histórico o patrones más repetidos.",
                "insights": [],
            }

        return {
            "status": "ok",
            "message": insights[0]["message"],
            "insights": insights[:3],
        }

    async def _load_expenses_between(
        self,
        session,
        user_id: int,
        start: datetime,
        end: datetime,
    ) -> list[Expense]:
        query = (
            select(Expense)
            .where(
                Expense.user_id == user_id,
                Expense.spent_at >= start,
                Expense.spent_at < end,
            )
            .order_by(Expense.spent_at.asc(), Expense.id.asc())
        )
        result = await session.execute(query)
        return list(result.scalars().all())

    async def _get_user(self, session, phone: str) -> User | None:
        return await get_user_by_identity(session, phone)

    def _aggregate_expenses(
        self,
        expenses: list[Expense],
        group_by: str,
    ) -> dict[str, float]:
        totals: dict[str, float] = defaultdict(float)
        for expense in expenses:
            if group_by == "merchant":
                key = self._merchant_key(expense)
            else:
                key = expense.category or "Otros"
            if not key:
                continue
            totals[key] += float(expense.amount)
        return dict(totals)

    def _merchant_key(self, expense: Expense) -> str:
        raw_value = (getattr(expense, "shop", None) or expense.description or "").strip()
        if not raw_value:
            return ""
        normalized = re.sub(r"\s+", " ", raw_value).strip()
        normalized = re.sub(r"[^0-9a-zA-ZáéíóúÁÉÍÓÚñÑ\s]", "", normalized)
        return normalized.title()

    def _get_period_window(
        self,
        phone: str,
        local_now: datetime,
        period: str,
        offset: int,
    ) -> tuple[datetime, datetime, str]:
        local_zone = local_now.tzinfo or DB_ZONE
        if period == "weekly":
            current_end = (local_now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            start = current_end - timedelta(days=7)
            start += timedelta(days=offset * 7)
            end = start + timedelta(days=7)
            label = f"{start.strftime('%Y-%m-%d')} a {(end - timedelta(days=1)).strftime('%Y-%m-%d')}"
            return start.astimezone(DB_ZONE), end.astimezone(DB_ZONE), label

        year = local_now.year
        month = local_now.month + offset
        while month <= 0:
            month += 12
            year -= 1
        while month > 12:
            month -= 12
            year += 1

        start_local = datetime(year, month, 1, tzinfo=local_zone)
        if month == 12:
            end_local = datetime(year + 1, 1, 1, tzinfo=local_zone)
        else:
            end_local = datetime(year, month + 1, 1, tzinfo=local_zone)
        label = start_local.strftime("%Y-%m")
        return start_local.astimezone(DB_ZONE), end_local.astimezone(DB_ZONE), label

    def _empty_comparison(self, period: str, group_by: str) -> dict[str, Any]:
        return {
            "status": "insufficient_data",
            "period": period,
            "group_by": group_by,
            "message": "Todavía no hay suficiente histórico comparable para sacar una conclusión.",
            "changes": [],
        }

    def _empty_insights(self) -> dict[str, Any]:
        return {
            "status": "insufficient_data",
            "message": "Todavía no tengo suficiente histórico para detectar fugas con confianza.",
            "insights": [],
        }
