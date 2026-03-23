import pytest

from app.services.rate_limit import RateLimitService


@pytest.mark.asyncio
async def test_rate_limit_allows_until_threshold_then_blocks():
    now = [10]
    service = RateLimitService(
        max_messages=2,
        window_seconds=60,
        notify_cooldown_seconds=120,
        time_fn=lambda: now[0],
    )

    first = await service.allow_message("5491112345678")
    second = await service.allow_message("5491112345678")
    blocked = await service.allow_message("5491112345678")
    blocked_again = await service.allow_message("5491112345678")

    assert first.allowed is True
    assert first.remaining == 1
    assert second.allowed is True
    assert second.remaining == 0
    assert blocked.allowed is False
    assert blocked.retry_after_seconds == 50
    assert blocked.should_notify is True
    assert blocked_again.allowed is False
    assert blocked_again.should_notify is False


@pytest.mark.asyncio
async def test_rate_limit_resets_in_next_window():
    now = [59]
    service = RateLimitService(
        max_messages=1,
        window_seconds=60,
        notify_cooldown_seconds=30,
        time_fn=lambda: now[0],
    )

    allowed = await service.allow_message("5491112345678")
    blocked = await service.allow_message("5491112345678")
    now[0] = 61
    allowed_next_window = await service.allow_message("5491112345678")

    assert allowed.allowed is True
    assert blocked.allowed is False
    assert allowed_next_window.allowed is True
    assert allowed_next_window.remaining == 0


@pytest.mark.asyncio
async def test_rate_limit_notifies_again_after_cooldown_expires():
    now = [0]
    service = RateLimitService(
        max_messages=1,
        window_seconds=60,
        notify_cooldown_seconds=5,
        time_fn=lambda: now[0],
    )

    await service.allow_message("5491112345678")
    blocked = await service.allow_message("5491112345678")
    now[0] = 6
    blocked_after_cooldown = await service.allow_message("5491112345678")

    assert blocked.allowed is False
    assert blocked.should_notify is True
    assert blocked_after_cooldown.allowed is False
    assert blocked_after_cooldown.should_notify is True


@pytest.mark.asyncio
async def test_rate_limit_cleans_expired_state():
    now = [0]
    service = RateLimitService(
        max_messages=1,
        window_seconds=10,
        notify_cooldown_seconds=5,
        time_fn=lambda: now[0],
    )

    await service.allow_message("5491112345678")
    await service.allow_message("5491112345678")

    assert service._counts
    assert service._notify_until

    now[0] = 20
    allowed = await service.allow_message("5491112345678")

    assert allowed.allowed is True
    assert allowed.remaining == 0
    assert len(service._counts) == 1
    assert service._notify_until == {}
