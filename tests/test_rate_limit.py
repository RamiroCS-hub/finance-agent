import pytest

from app.services.rate_limit import RateLimitService


class FakeRedis:
    def __init__(self, now_ref):
        self._store: dict[str, int | str] = {}
        self._expires: dict[str, int] = {}
        self._now_ref = now_ref

    def _cleanup(self) -> None:
        now = self._now_ref[0]
        expired = [key for key, expires_at in self._expires.items() if expires_at <= now]
        for key in expired:
            self._store.pop(key, None)
            self._expires.pop(key, None)

    async def incr(self, key: str) -> int:
        self._cleanup()
        value = int(self._store.get(key, 0)) + 1
        self._store[key] = value
        return value

    async def expire(self, key: str, seconds: int) -> bool:
        self._cleanup()
        self._expires[key] = self._now_ref[0] + seconds
        return True

    async def set(self, key: str, value: str, ex: int | None = None, nx: bool = False):
        self._cleanup()
        if nx and key in self._store:
            return None
        self._store[key] = value
        if ex is not None:
            self._expires[key] = self._now_ref[0] + ex
        return True


@pytest.mark.asyncio
async def test_rate_limit_allows_until_threshold_then_blocks():
    now = [10]
    redis = FakeRedis(now)
    service = RateLimitService(
        redis,
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
    redis = FakeRedis(now)
    service = RateLimitService(
        redis,
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
    redis = FakeRedis(now)
    service = RateLimitService(
        redis,
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
