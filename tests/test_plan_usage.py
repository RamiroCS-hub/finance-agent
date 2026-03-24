from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.plan_usage import QuotaDecision, check_quota, consume_quota_if_available
from app.services.timezones import utc_window_for_local_month_by_timezone, utc_window_for_local_week


def test_utc_window_for_local_week_uses_local_calendar():
    start, end = utc_window_for_local_week(
        "America/Argentina/Buenos_Aires",
        reference=datetime(2026, 3, 18, 15, 0, tzinfo=timezone.utc),
    )
    assert start.isoformat() == "2026-03-16T03:00:00+00:00"
    assert end.isoformat() == "2026-03-23T03:00:00+00:00"


def test_utc_window_for_local_month_uses_local_calendar():
    start, end = utc_window_for_local_month_by_timezone(
        "America/Argentina/Buenos_Aires",
        reference=datetime(2026, 3, 18, 15, 0, tzinfo=timezone.utc),
    )
    assert start.isoformat() == "2026-03-01T03:00:00+00:00"
    assert end.isoformat() == "2026-04-01T03:00:00+00:00"


@pytest.mark.asyncio
async def test_check_quota_free_audio_under_limit():
    session = AsyncMock()
    with patch("app.services.plan_usage._count_usage_events", new=AsyncMock(return_value=4)):
        decision = await check_quota(
            session,
            user_id=1,
            plan="FREE",
            quota_key="audio_processing",
            timezone="UTC",
            now=datetime(2026, 3, 18, tzinfo=timezone.utc),
        )

    assert decision == QuotaDecision(
        allowed=True,
        limit=5,
        used=4,
        remaining=1,
        quota_key="audio_processing",
        period_kind="weekly",
    )


@pytest.mark.asyncio
async def test_check_quota_premium_is_unlimited():
    session = AsyncMock()
    decision = await check_quota(
        session,
        user_id=1,
        plan="PREMIUM",
        quota_key="audio_processing",
        timezone="UTC",
    )

    assert decision.allowed is True
    assert decision.limit is None
    assert decision.remaining is None


@pytest.mark.asyncio
async def test_consume_quota_if_available_inserts_event():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock(return_value=None)

    with patch("app.services.plan_usage._count_usage_events", new=AsyncMock(return_value=4)):
        decision = await consume_quota_if_available(
            session,
            user_id=1,
            plan="FREE",
            quota_key="audio_processing",
            timezone="UTC",
            source_ref="wamid_123",
            now=datetime(2026, 3, 18, tzinfo=timezone.utc),
        )

    assert decision.allowed is True
    assert decision.used == 5
    session.add.assert_called_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_consume_quota_if_available_blocks_when_exhausted():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock(return_value=None)

    with patch("app.services.plan_usage._count_usage_events", new=AsyncMock(return_value=5)):
        decision = await consume_quota_if_available(
            session,
            user_id=1,
            plan="FREE",
            quota_key="audio_processing",
            timezone="UTC",
            source_ref="wamid_123",
            now=datetime(2026, 3, 18, tzinfo=timezone.utc),
        )

    assert decision.allowed is False
    assert decision.remaining == 0
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_consume_quota_if_available_deduplicates_source_ref():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.scalar = AsyncMock(return_value=99)

    with patch("app.services.plan_usage._count_usage_events", new=AsyncMock(return_value=3)):
        decision = await consume_quota_if_available(
            session,
            user_id=1,
            plan="FREE",
            quota_key="audio_processing",
            timezone="UTC",
            source_ref="wamid_123",
            now=datetime(2026, 3, 18, tzinfo=timezone.utc),
        )

    assert decision.allowed is True
    assert decision.used == 3
    session.add.assert_not_called()
