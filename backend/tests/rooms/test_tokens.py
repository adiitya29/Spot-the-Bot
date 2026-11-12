"""Unit tests for 24h signed guest player tokens."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from freezegun import freeze_time

from apps.rooms.tokens import (
    InvalidTokenError,
    TokenExpiredError,
    sign_player_token,
    verify_player_token,
)


def test_sign_and_verify_player_token_roundtrip() -> None:
    """Signed token verifies claims and normalizes room code."""
    player_id = uuid.uuid4()
    token = sign_player_token(player_id, "ab2c3d")
    claims = verify_player_token(token, expected_room_code="AB2C3D")
    assert claims.player_id == player_id
    assert claims.room_code == "AB2C3D"


def test_verify_token_rejects_wrong_room() -> None:
    """Token valid for one room is rejected for another room."""
    token = sign_player_token(uuid.uuid4(), "AB2C3D")
    with pytest.raises(InvalidTokenError, match="does not match"):
        verify_player_token(token, expected_room_code="XY7Z8K")


def test_verify_token_rejects_tampered_or_empty_token() -> None:
    """Tampered, malformed, or empty tokens raise InvalidTokenError."""
    token = sign_player_token(uuid.uuid4(), "AB2C3D")
    tampered = f"{token[:-2]}aa"

    with pytest.raises(InvalidTokenError):
        verify_player_token(tampered)

    with pytest.raises(InvalidTokenError):
        verify_player_token("")

    with pytest.raises(InvalidTokenError):
        verify_player_token("not-a-valid-token")


def test_verify_token_expires_after_24_hours() -> None:
    """Tokens older than 24 hours raise TokenExpiredError."""
    start = datetime(2026, 11, 12, 9, 0, 0, tzinfo=UTC)
    with freeze_time(start):
        token = sign_player_token(uuid.uuid4(), "AB2C3D")

    with freeze_time(datetime(2026, 11, 13, 8, 59, 59, tzinfo=UTC)):
        claims = verify_player_token(token, expected_room_code="AB2C3D")
        assert claims.room_code == "AB2C3D"

    with (
        freeze_time(datetime(2026, 11, 13, 9, 0, 2, tzinfo=UTC)),
        pytest.raises(TokenExpiredError),
    ):
        verify_player_token(token, expected_room_code="AB2C3D")
