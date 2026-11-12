"""Redis client helper stub (expanded in Phases 2-3)."""

from __future__ import annotations

import redis
from django.conf import settings


def get_redis_client() -> redis.Redis:
    """Return a decoded-string Redis client bound to REDIS_URL."""
    if not settings.REDIS_URL:
        raise RuntimeError("REDIS_URL is not configured")
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)
