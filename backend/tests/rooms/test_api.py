"""Integration tests for rooms REST API, conflicts, DB invariants, and IP throttles."""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from django.core.cache import cache
from django.db import IntegrityError
from rest_framework.test import APIClient

from apps.rooms.codes import is_valid_room_code
from apps.rooms.models import Player, Room, RoomStatus
from apps.rooms.tokens import verify_player_token
from tests.rooms.factories import PlayerFactory, RoomFactory


@pytest.fixture(autouse=True)
def clear_throttle_cache() -> Iterator[None]:
    """Reset throttle cache before and after every test."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
def test_create_room_and_get_public_info() -> None:
    """POST /api/rooms/ creates host + room, returns 24h token, and hides is_bot."""
    client = APIClient()
    response = client.post(
        "/api/rooms/",
        {
            "nickname": "  Alice\x00 ",
            "config": {
                "rounds": 4,
                "min_humans": 3,
                "allow_replay_use": True,
                "phase_durations": {"chat": 90},
            },
        },
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    code = payload["code"]
    assert is_valid_room_code(code)
    assert payload["player"]["nickname"] == "Alice"
    assert payload["player"]["is_host"] is True
    assert "is_bot" not in json.dumps(payload)

    claims = verify_player_token(payload["player_token"], expected_room_code=code)
    assert str(claims.player_id) == payload["player"]["id"]

    room = Room.objects.get(code=code)
    assert room.host_id == claims.player_id
    assert room.config["rounds"] == 4
    assert room.config["min_humans"] == 3
    assert room.config["allow_replay_use"] is True
    assert room.config["phase_durations"] == {
        "answer": 45,
        "chat": 90,
        "vote": 30,
        "reveal": 12,
    }

    detail = client.get(f"/api/rooms/{code.lower()}/")
    assert detail.status_code == 200
    detail_data = detail.json()
    assert detail_data["code"] == code
    assert detail_data["status"] == RoomStatus.LOBBY
    assert detail_data["human_count"] == 1
    assert detail_data["capacity"] == 7
    assert detail_data["min_humans"] == 3
    assert detail_data["allow_replay_use"] is True
    assert "is_bot" not in json.dumps(detail_data)


@pytest.mark.django_db
def test_create_room_rejects_invalid_nickname_or_min_humans() -> None:
    """Nickname bounds and min_humans limits are enforced."""
    client = APIClient()

    short = client.post("/api/rooms/", {"nickname": "A"}, format="json")
    assert short.status_code == 400

    too_long = client.post("/api/rooms/", {"nickname": "X" * 21}, format="json")
    assert too_long.status_code == 400

    bad_min = client.post(
        "/api/rooms/",
        {"nickname": "Alice", "config": {"min_humans": 2}},
        format="json",
    )
    assert bad_min.status_code == 400


@pytest.mark.django_db
def test_join_room_success_and_unknown_room_404() -> None:
    """Valid guest can join open lobby; unknown/invalid room codes return 404."""
    client = APIClient()
    create_resp = client.post("/api/rooms/", {"nickname": "Host"}, format="json")
    code = create_resp.json()["code"]

    join_resp = client.post(f"/api/rooms/{code.lower()}/join/", {"nickname": "Bob"}, format="json")
    assert join_resp.status_code == 200
    data = join_resp.json()
    assert data["player"]["nickname"] == "Bob"
    assert data["player"]["is_host"] is False
    assert data["room"]["human_count"] == 2
    assert "is_bot" not in json.dumps(data)

    claims = verify_player_token(data["player_token"], expected_room_code=code)
    assert str(claims.player_id) == data["player"]["id"]

    missing = client.post("/api/rooms/ZZZZZZ/join/", {"nickname": "Bob"}, format="json")
    assert missing.status_code == 404

    invalid = client.get("/api/rooms/BAD0I1/")
    assert invalid.status_code == 404


@pytest.mark.django_db
def test_join_room_409_conflicts() -> None:
    """Duplicate nickname, full room, started room, and finished room return 409."""
    client = APIClient()
    room = RoomFactory()
    PlayerFactory(room=room, nickname="Alice", is_host=True)

    # Duplicate nickname (case-insensitive)
    dup = client.post(f"/api/rooms/{room.code}/join/", {"nickname": "alice"}, format="json")
    assert dup.status_code == 409
    assert dup.json()["code"] == "nickname_taken"

    # Fill up to capacity = 7 humans
    for i in range(6):
        PlayerFactory(room=room, nickname=f"Human{i}")
    full = client.post(f"/api/rooms/{room.code}/join/", {"nickname": "Eighth"}, format="json")
    assert full.status_code == 409
    assert full.json()["code"] == "room_full"

    # Started room rejects new joins even when below capacity
    started_room = RoomFactory(status=RoomStatus.IN_PROGRESS)
    started = client.post(
        f"/api/rooms/{started_room.code}/join/",
        {"nickname": "Latecomer"},
        format="json",
    )
    assert started.status_code == 409
    assert started.json()["code"] == "room_started"

    # Finished / abandoned room rejects new joins
    closed_room = RoomFactory(status=RoomStatus.FINISHED)
    closed = client.post(
        f"/api/rooms/{closed_room.code}/join/",
        {"nickname": "Latecomer"},
        format="json",
    )
    assert closed.status_code == 409
    assert closed.json()["code"] == "room_closed"


@pytest.mark.django_db
def test_unique_bot_per_room_constraint() -> None:
    """Database partial unique constraint rejects a second bot in the same room."""
    room = RoomFactory()
    PlayerFactory(room=room, nickname="Bot1", is_bot=True)
    with pytest.raises(IntegrityError):
        Player.objects.create(room=room, nickname="Bot2", is_bot=True)


@pytest.mark.django_db
def test_room_creation_ip_throttling() -> None:
    """POST /api/rooms/ throttles after 10 rooms/hour per IP while allowing other IPs."""
    client = APIClient()
    for i in range(10):
        resp = client.post(
            "/api/rooms/",
            {"nickname": f"Host{i}"},
            format="json",
            REMOTE_ADDR="203.0.113.10",
        )
        assert resp.status_code == 201

    throttled = client.post(
        "/api/rooms/",
        {"nickname": "Host10"},
        format="json",
        REMOTE_ADDR="203.0.113.10",
    )
    assert throttled.status_code == 429

    other_ip = client.post(
        "/api/rooms/",
        {"nickname": "OtherHost"},
        format="json",
        REMOTE_ADDR="203.0.113.11",
    )
    assert other_ip.status_code == 201


@pytest.mark.django_db
def test_room_join_ip_throttling() -> None:
    """POST /api/rooms/{code}/join/ throttles after 30 attempts/hour per IP."""
    client = APIClient()
    room = RoomFactory(status=RoomStatus.IN_PROGRESS)

    for i in range(30):
        resp = client.post(
            f"/api/rooms/{room.code}/join/",
            {"nickname": f"Guest{i}"},
            format="json",
            REMOTE_ADDR="198.51.100.5",
        )
        assert resp.status_code == 409

    throttled = client.post(
        f"/api/rooms/{room.code}/join/",
        {"nickname": "Guest30"},
        format="json",
        REMOTE_ADDR="198.51.100.5",
    )
    assert throttled.status_code == 429

    other_ip = client.post(
        f"/api/rooms/{room.code}/join/",
        {"nickname": "OtherGuest"},
        format="json",
        REMOTE_ADDR="198.51.100.6",
    )
    assert other_ip.status_code == 409
