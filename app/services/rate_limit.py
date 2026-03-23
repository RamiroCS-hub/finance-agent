from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass(slots=True)
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int
    should_notify: bool


class RateLimitService:
    def __init__(
        self,
        redis_client,
        *,
        max_messages: int,
        window_seconds: int,
        notify_cooldown_seconds: int,
        key_prefix: str = "ratelimit:whatsapp",
        time_fn: Callable[[], int] | None = None,
    ) -> None:
        if max_messages <= 0:
            raise ValueError("max_messages must be > 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        if notify_cooldown_seconds < 0:
            raise ValueError("notify_cooldown_seconds must be >= 0")

        self._redis = redis_client
        self._max_messages = max_messages
        self._window_seconds = window_seconds
        self._notify_cooldown_seconds = notify_cooldown_seconds
        self._key_prefix = key_prefix
        self._time_fn = time_fn or (lambda: int(time.time()))

    async def allow_message(self, phone: str) -> RateLimitDecision:
        now = int(self._time_fn())
        window_bucket = now // self._window_seconds
        retry_after_seconds = self._window_seconds - (now % self._window_seconds)
        counter_key = f"{self._key_prefix}:count:{phone}:{window_bucket}"

        count = await self._redis.incr(counter_key)
        if count == 1:
            await self._redis.expire(counter_key, self._window_seconds + 5)

        remaining = max(self._max_messages - count, 0)
        if count <= self._max_messages:
            return RateLimitDecision(
                allowed=True,
                remaining=remaining,
                retry_after_seconds=0,
                should_notify=False,
            )

        should_notify = False
        if self._notify_cooldown_seconds == 0:
            should_notify = True
        else:
            notify_key = f"{self._key_prefix}:notify:{phone}"
            notify_result = await self._redis.set(
                notify_key,
                "1",
                ex=self._notify_cooldown_seconds,
                nx=True,
            )
            should_notify = bool(notify_result)

        return RateLimitDecision(
            allowed=False,
            remaining=0,
            retry_after_seconds=retry_after_seconds,
            should_notify=should_notify,
        )
