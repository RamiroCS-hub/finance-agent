from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PlanUsageEvent, User
from app.services.paywall import get_plan_quota
from app.services.timezones import (
    utc_now,
    utc_window_for_local_month_by_timezone,
    utc_window_for_local_week,
)


@dataclass
class QuotaDecision:
    allowed: bool
    limit: int | None
    used: int
    remaining: int | None
    quota_key: str
    period_kind: str | None


async def check_quota(
    session: AsyncSession,
    *,
    user_id: int,
    plan: str,
    quota_key: str,
    timezone: str,
    now: datetime | None = None,
) -> QuotaDecision:
    quota = get_plan_quota(plan, quota_key)
    if quota is None:
        return QuotaDecision(
            allowed=True,
            limit=None,
            used=0,
            remaining=None,
            quota_key=quota_key,
            period_kind=None,
        )

    window_start, window_end = _quota_window(quota["period"], timezone, now)
    used = await _count_usage_events(
        session,
        user_id=user_id,
        quota_key=quota_key,
        window_start=window_start,
        window_end=window_end,
    )
    limit = int(quota["limit"])
    return QuotaDecision(
        allowed=used < limit,
        limit=limit,
        used=used,
        remaining=max(limit - used, 0),
        quota_key=quota_key,
        period_kind=str(quota["period"]),
    )


async def consume_quota_if_available(
    session: AsyncSession,
    *,
    user_id: int,
    plan: str,
    quota_key: str,
    timezone: str,
    source_ref: str | None = None,
    now: datetime | None = None,
) -> QuotaDecision:
    quota = get_plan_quota(plan, quota_key)
    if quota is None:
        return QuotaDecision(
            allowed=True,
            limit=None,
            used=0,
            remaining=None,
            quota_key=quota_key,
            period_kind=None,
        )

    window_start, window_end = _quota_window(quota["period"], timezone, now)
    limit = int(quota["limit"])
    consumed_at = now or utc_now()
    try:
        await session.execute(select(User.id).where(User.id == user_id).with_for_update())
        if source_ref:
            existing = await session.scalar(
                select(PlanUsageEvent.id).where(
                    PlanUsageEvent.user_id == user_id,
                    PlanUsageEvent.quota_key == quota_key,
                    PlanUsageEvent.source_ref == source_ref,
                )
            )
            if existing is not None:
                used = await _count_usage_events(
                    session,
                    user_id=user_id,
                    quota_key=quota_key,
                    window_start=window_start,
                    window_end=window_end,
                )
                return QuotaDecision(
                    allowed=True,
                    limit=limit,
                    used=used,
                    remaining=max(limit - used, 0),
                    quota_key=quota_key,
                    period_kind=str(quota["period"]),
                )

        used = await _count_usage_events(
            session,
            user_id=user_id,
            quota_key=quota_key,
            window_start=window_start,
            window_end=window_end,
        )
        if used >= limit:
            await session.rollback()
            return QuotaDecision(
                allowed=False,
                limit=limit,
                used=used,
                remaining=0,
                quota_key=quota_key,
                period_kind=str(quota["period"]),
            )

        session.add(
            PlanUsageEvent(
                user_id=user_id,
                quota_key=quota_key,
                period_kind=str(quota["period"]),
                source_ref=source_ref,
                consumed_at=consumed_at,
            )
        )
        await session.flush()
        await session.commit()
        used += 1
        return QuotaDecision(
            allowed=True,
            limit=limit,
            used=used,
            remaining=max(limit - used, 0),
            quota_key=quota_key,
            period_kind=str(quota["period"]),
        )
    except IntegrityError:
        await session.rollback()
        used = await _count_usage_events(
            session,
            user_id=user_id,
            quota_key=quota_key,
            window_start=window_start,
            window_end=window_end,
        )
        return QuotaDecision(
            allowed=True,
            limit=limit,
            used=used,
            remaining=max(limit - used, 0),
            quota_key=quota_key,
            period_kind=str(quota["period"]),
        )
    except Exception:
        await session.rollback()
        raise


def _quota_window(
    period_kind: str,
    timezone: str,
    now: datetime | None,
) -> tuple[datetime, datetime]:
    if period_kind == "weekly":
        return utc_window_for_local_week(timezone, reference=now)
    if period_kind == "monthly":
        return utc_window_for_local_month_by_timezone(timezone, reference=now)
    raise ValueError(f"Periodo de cuota no soportado: {period_kind}")


async def _count_usage_events(
    session: AsyncSession,
    *,
    user_id: int,
    quota_key: str,
    window_start: datetime,
    window_end: datetime,
) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(PlanUsageEvent)
        .where(
            PlanUsageEvent.user_id == user_id,
            PlanUsageEvent.quota_key == quota_key,
            PlanUsageEvent.consumed_at >= window_start,
            PlanUsageEvent.consumed_at < window_end,
        )
    )
    return int(count or 0)
