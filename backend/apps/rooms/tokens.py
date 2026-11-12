"""Signed 24-hour guest player token creation and verification."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from django.core import signing

from apps.rooms.codes import normalize_room_code

TOKEN_SALT = "spot-the-bot.player-token"
TOKEN_MAX_AGE_SECONDS = 86_400


class TokenError(Exception):
    """Base error raised when verifying a player token fails."""


class TokenExpiredError(TokenError):
    """Raised when a signed token is older than 24 hours."""


class InvalidTokenError(TokenError):
    """Raised when a signed token has an invalid signature or payload."""


@dataclass(frozen=True, slots=True)
class TokenClaims:
    """Verified claims embedded in a guest player token."""

    player_id: UUID
    room_code: str


def sign_player_token(player_id: UUID, room_code: str) -> str:
    """Sign a guest player token encoding player_id and normalized room_code."""
    payload = {
        "player_id": str(player_id),
        "room_code": normalize_room_code(room_code),
    }
    return signing.dumps(payload, salt=TOKEN_SALT)


def verify_player_token(
    token: str,
    *,
    expected_room_code: str | None = None,
    max_age: int = TOKEN_MAX_AGE_SECONDS,
) -> TokenClaims:
    """Verify signature, expiry, payload shape, and optional room code match."""
    if not token:
        raise InvalidTokenError("Missing player token")

    try:
        data = signing.loads(token, salt=TOKEN_SALT, max_age=max_age)
    except signing.SignatureExpired as exc:
        raise TokenExpiredError("Player token has expired") from exc
    except signing.BadSignature as exc:
        raise InvalidTokenError("Invalid player token") from exc

    if not isinstance(data, dict):
        raise InvalidTokenError("Malformed token payload")

    raw_player_id = data.get("player_id")
    raw_room_code = data.get("room_code")
    if not isinstance(raw_player_id, str) or not isinstance(raw_room_code, str):
        raise InvalidTokenError("Incomplete token claims")

    try:
        player_id = UUID(raw_player_id)
    except ValueError as exc:
        raise InvalidTokenError("Invalid player_id claim") from exc

    room_code = normalize_room_code(raw_room_code)
    if expected_room_code is not None and room_code != normalize_room_code(expected_room_code):
        raise InvalidTokenError("Token does not match target room")

    return TokenClaims(player_id=player_id, room_code=room_code)
