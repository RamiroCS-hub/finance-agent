from __future__ import annotations

import asyncio
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
        *,
        max_messages: int,
        window_seconds: int,
        notify_cooldown_seconds: int,
        time_fn: Callable[[], int] | None = None,
    ) -> None:
        if max_messages <= 0:
            raise ValueError("max_messages must be > 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        if notify_cooldown_seconds < 0:
            raise ValueError("notify_cooldown_seconds must be >= 0")

        self._max_messages = max_messages
        self._window_seconds = window_seconds
        self._notify_cooldown_seconds = notify_cooldown_seconds
        self._time_fn = time_fn or (lambda: int(time.time()))
        self._lock = asyncio.Lock()
        self._counts: dict[tuple[str, int], tuple[int, int]] = {}
        self._notify_until: dict[str, int] = {}

    def _cleanup(self, now: int) -> None:
        expired_count_keys = [
            key for key, (_, expires_at) in self._counts.items() if expires_at <= now
        ]
        for key in expired_count_keys:
            self._counts.pop(key, None)

        expired_notify_keys = [
            phone for phone, expires_at in self._notify_until.items() if expires_at <= now
        ]
        for phone in expired_notify_keys:
            self._notify_until.pop(phone, None)

    async def allow_message(self, phone: str) -> RateLimitDecision:
        now = int(self._time_fn())
        window_bucket = now // self._window_seconds
        retry_after_seconds = self._window_seconds - (now % self._window_seconds)
        async with self._lock:
            self._cleanup(now)

            counter_key = (phone, window_bucket)
            count, _ = self._counts.get(counter_key, (0, now + self._window_seconds + 5))
            count += 1
            self._counts[counter_key] = (count, now + self._window_seconds + 5)

            remaining = max(self._max_messages - count, 0)
            if count <= self._max_messages:
                return RateLimitDecision(
                    allowed=True,
                    remaining=remaining,
                    retry_after_seconds=0,
                    should_notify=False,
                )

            if self._notify_cooldown_seconds == 0:
                should_notify = True
            else:
                notify_until = self._notify_until.get(phone, 0)
                should_notify = notify_until <= now
                if should_notify:
                    self._notify_until[phone] = now + self._notify_cooldown_seconds

            return RateLimitDecision(
                allowed=False,
                remaining=0,
                retry_after_seconds=retry_after_seconds,
                should_notify=should_notify,
            )
