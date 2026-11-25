"""Shared Redis client helper and socket timeout defaults."""

from __future__ import annotations

from typing import Any

import redis
from django.conf import settings

REDIS_SOCKET_OPTIONS: dict[str, Any] = {
    "socket_connect_timeout": 5.0,
    "socket_timeout": 5.0,
    "retry_on_timeout": True,
    "health_check_interval": 30,
}


def get_redis_client() -> redis.Redis:
    """Return a decoded-string Redis client bound to REDIS_URL with bounded timeouts."""
    if not settings.REDIS_URL:
        raise RuntimeError("REDIS_URL is not configured")
    return redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, **REDIS_SOCKET_OPTIONS)
