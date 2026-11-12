"""Sliding-window rate limiting backed by Redis ZSET with in-memory fallback."""

from __future__ import annotations

import threading
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

import redis
from django.conf import settings


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    """Outcome of a single sliding-window rate-limit check."""

    allowed: bool
    remaining: int
    retry_after_seconds: float


class SlidingWindowLimiter:
    """Sliding-window rate limiter supporting Redis ZSET and in-memory testing."""

    def __init__(
        self,
        max_events: int,
        window_seconds: float,
        *,
        clock: Callable[[], float] | None = None,
        redis_client: redis.Redis | None = None,
    ) -> None:
        if max_events < 1:
            raise ValueError("max_events must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._clock = clock or time.time
        self._redis_client = redis_client
        self._lock = threading.Lock()
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> RateLimitResult:
        """Record an attempt for `key` if within budget, or return retry_after_seconds."""
        now = self._clock()
        client = self._get_redis()
        if client is not None:
            return self._allow_redis(client, key, now)
        return self._allow_memory(key, now)

    def _get_redis(self) -> redis.Redis | None:
        if self._redis_client is not None:
            return self._redis_client
        redis_url = getattr(settings, "REDIS_URL", "")
        if not redis_url:
            return None
        return redis.Redis.from_url(redis_url, decode_responses=True)

    def _allow_memory(self, key: str, now: float) -> RateLimitResult:
        cutoff = now - self.window_seconds
        with self._lock:
            bucket = self._buckets[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_events:
                retry_after = max(0.0, (bucket[0] + self.window_seconds) - now)
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    retry_after_seconds=retry_after,
                )
            bucket.append(now)
            remaining = max(0, self.max_events - len(bucket))
            return RateLimitResult(allowed=True, remaining=remaining, retry_after_seconds=0.0)

    def _allow_redis(self, client: redis.Redis, key: str, now: float) -> RateLimitResult:
        cutoff = now - self.window_seconds
        should_close = self._redis_client is None
        try:
            pipe = client.pipeline(transaction=True)
            pipe.zremrangebyscore(key, "-inf", cutoff)
            pipe.zcard(key)
            pipe.zrange(key, 0, 0, withscores=True)
            _, count, oldest = pipe.execute()
            count_int = int(count)
            if count_int >= self.max_events:
                oldest_score = float(oldest[0][1]) if oldest else now
                retry_after = max(0.0, (oldest_score + self.window_seconds) - now)
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    retry_after_seconds=retry_after,
                )
            member = f"{now:.6f}:{uuid.uuid4().hex[:8]}"
            ttl_ms = max(1000, int(self.window_seconds * 1000) + 1000)
            write_pipe = client.pipeline(transaction=True)
            write_pipe.zadd(key, {member: now})
            write_pipe.pexpire(key, ttl_ms)
            write_pipe.execute()
            return RateLimitResult(
                allowed=True,
                remaining=max(0, self.max_events - (count_int + 1)),
                retry_after_seconds=0.0,
            )
        finally:
            if should_close:
                client.close()


def check_chat_rate_limit(room_id: UUID, player_id: UUID) -> RateLimitResult:
    """Enforce per-player chat message sliding window rate limit."""
    limiter = SlidingWindowLimiter(
        max_events=int(getattr(settings, "CHAT_RATE_LIMIT_COUNT", 5)),
        window_seconds=float(getattr(settings, "CHAT_RATE_LIMIT_WINDOW_SECONDS", 5.0)),
    )
    return limiter.allow(f"stb:rl:chat:{room_id}:{player_id}")


def check_typing_rate_limit(room_id: UUID, player_id: UUID) -> RateLimitResult:
    """Enforce per-player typing indicator sliding window rate limit."""
    limiter = SlidingWindowLimiter(
        max_events=int(getattr(settings, "TYPING_RATE_LIMIT_COUNT", 4)),
        window_seconds=float(getattr(settings, "TYPING_RATE_LIMIT_WINDOW_SECONDS", 2.0)),
    )
    return limiter.allow(f"stb:rl:typing:{room_id}:{player_id}")
