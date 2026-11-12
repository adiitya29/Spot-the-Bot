"""Distributed per-room lock helper backed by Redis with local-process fallback."""

from __future__ import annotations

import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from uuid import UUID

import redis
from django.conf import settings

_LOCAL_LOCKS_GUARD = threading.Lock()
_LOCAL_LOCKS: dict[str, threading.RLock] = {}

_RELEASE_SCRIPT = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
end
return 0
"""


def _get_local_lock(key: str) -> threading.RLock:
    with _LOCAL_LOCKS_GUARD:
        lock = _LOCAL_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _LOCAL_LOCKS[key] = lock
        return lock


@contextmanager
def room_lock(
    room_id: UUID,
    *,
    ttl_seconds: float = 5.0,
    wait_timeout_seconds: float = 2.5,
) -> Iterator[None]:
    """Acquire a mutual-exclusion lock for state transitions in a room."""
    key = f"stb:lock:room:{room_id}"
    redis_url = getattr(settings, "REDIS_URL", "")
    if not redis_url:
        local_lock = _get_local_lock(key)
        acquired = local_lock.acquire(timeout=wait_timeout_seconds)
        if not acquired:
            raise TimeoutError(f"Could not acquire local lock for room {room_id}")
        try:
            yield
        finally:
            local_lock.release()
        return

    client = redis.Redis.from_url(redis_url, decode_responses=True)
    token = str(uuid.uuid4())
    ttl_ms = max(500, int(ttl_seconds * 1000))
    deadline = time.monotonic() + wait_timeout_seconds
    acquired = False
    try:
        while not acquired:
            acquired = bool(client.set(key, token, nx=True, px=ttl_ms))
            if acquired:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Could not acquire Redis lock for room {room_id}")
            time.sleep(0.01)
        yield
    finally:
        if acquired:
            with suppress(redis.RedisError):
                client.eval(_RELEASE_SCRIPT, 1, key, token)
        client.close()
