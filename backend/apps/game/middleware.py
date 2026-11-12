"""WebSocket Origin validation and signed guest token auth middleware."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs
from uuid import UUID

from channels.db import database_sync_to_async
from channels.security.websocket import OriginValidator
from django.conf import settings

from apps.rooms.codes import normalize_room_code
from apps.rooms.models import Player, RoomStatus
from apps.rooms.tokens import TokenError, verify_player_token

ROOM_WS_PATH_RE = re.compile(r"^/ws/rooms/(?P<code>[^/]+)/?$")


@dataclass(frozen=True, slots=True)
class WSAuthContext:
    """Authenticated guest player context attached to ASGI WebSocket scope."""

    player_id: UUID
    room_id: UUID
    room_code: str


class DynamicOriginValidator:
    """Validate WebSocket Origin header dynamically against ALLOWED_HOSTS and FRONTEND_ORIGIN."""

    def __init__(self, application: Any) -> None:
        self.application = application

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> Any:
        allowed: list[str] = list(getattr(settings, "ALLOWED_HOSTS", []))
        frontend_origin = getattr(settings, "FRONTEND_ORIGIN", "")
        if frontend_origin:
            allowed.append(frontend_origin)
        if getattr(settings, "DEBUG", False) and not allowed:
            allowed = ["localhost", "127.0.0.1", "[::1]"]
        validator = OriginValidator(self.application, allowed)
        return await validator(scope, receive, send)


@database_sync_to_async
def _authenticate_room_player(
    room_code: str,
    token: str,
) -> tuple[WSAuthContext | None, str | None]:
    try:
        claims = verify_player_token(token, expected_room_code=room_code)
    except TokenError as exc:
        return None, str(exc)

    player = (
        Player.objects.select_related("room")
        .filter(
            id=claims.player_id,
            room__code=claims.room_code,
            is_bot=False,
        )
        .first()
    )
    if player is None:
        return None, "Player not found in room"
    if player.room.status == RoomStatus.ABANDONED:
        return None, "Room is abandoned"

    return (
        WSAuthContext(
            player_id=player.id,
            room_id=player.room_id,
            room_code=player.room.code,
        ),
        None,
    )


class TokenAuthMiddleware:
    """Authenticate /ws/rooms/<code>/?token=<token> WebSocket connections."""

    def __init__(self, application: Any) -> None:
        self.application = application

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> Any:
        if scope.get("type") == "websocket":
            path = str(scope.get("path", ""))
            match = ROOM_WS_PATH_RE.match(path)
            if match:
                room_code = normalize_room_code(match.group("code"))
                query_bytes = scope.get("query_string", b"")
                params = parse_qs(query_bytes.decode("utf-8", errors="ignore"))
                token = params.get("token", [""])[0]
                auth_ctx, auth_error = await _authenticate_room_player(room_code, token)
                scope["ws_auth"] = auth_ctx
                scope["ws_auth_error"] = auth_error

        return await self.application(scope, receive, send)
