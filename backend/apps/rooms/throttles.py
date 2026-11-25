"""DRF rate throttles for room creation and joining."""

from __future__ import annotations

import logging

from redis.exceptions import RedisError
from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


class _ResilientIPThrottle(SimpleRateThrottle):
    """IP-scoped throttle that fails open if the Redis cache backend stalls."""

    def get_cache_key(self, request: Request, view: APIView) -> str | None:
        ident = self.get_ident(request)
        if not ident:
            return None
        return self.cache_format % {"scope": self.scope, "ident": ident}

    def allow_request(self, request: Request, view: APIView) -> bool:
        try:
            return super().allow_request(request, view)
        except (RedisError, OSError, TimeoutError) as exc:
            logger.warning("Throttle cache unavailable (%s); failing open: %s", self.scope, exc)
            return True


class CreateRoomThrottle(_ResilientIPThrottle):
    """Limit room creation to 10 requests per hour per client IP."""

    scope = "room_create"


class JoinRoomThrottle(_ResilientIPThrottle):
    """Limit room join attempts to 30 requests per hour per client IP."""

    scope = "room_join"
