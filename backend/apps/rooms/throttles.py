"""DRF rate throttles for room creation and joining."""

from __future__ import annotations

from rest_framework.request import Request
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView


class CreateRoomThrottle(SimpleRateThrottle):
    """Limit room creation to 10 requests per hour per client IP."""

    scope = "room_create"

    def get_cache_key(self, request: Request, view: APIView) -> str | None:
        ident = self.get_ident(request)
        if not ident:
            return None
        return self.cache_format % {"scope": self.scope, "ident": ident}


class JoinRoomThrottle(SimpleRateThrottle):
    """Limit room join attempts to 30 requests per hour per client IP."""

    scope = "room_join"

    def get_cache_key(self, request: Request, view: APIView) -> str | None:
        ident = self.get_ident(request)
        if not ident:
            return None
        return self.cache_format % {"scope": self.scope, "ident": ident}
