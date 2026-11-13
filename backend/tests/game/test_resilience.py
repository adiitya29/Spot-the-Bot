"""Phase 5 resilience tests: duplicate tabs, client_msg_id dedup, host promotion,

abandonment, and mid-phase drop/reconnect chaos.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any
from uuid import uuid4

import pytest
from channels.db import database_sync_to_async
from channels.layers import channel_layers
from channels.routing import get_default_application
from channels.testing import WebsocketCommunicator
from django.db import connections
from django.test import override_settings
from django.utils import timezone

from apps.common.models import Event
from apps.game.models import Message, RoundPhase
from apps.game.presence import presence_manager
from apps.game.state_machine import advance_phase, send_chat_message, start_game
from apps.rooms.models import Player, Room, RoomStatus
from apps.rooms.tasks import cleanup_abandoned_rooms, cleanup_abandoned_rooms_task
from apps.rooms.tokens import sign_player_token
from tests.rooms.factories import PlayerFactory, RoomFactory

ORIGIN_HEADER = [(b"origin", b"http://localhost:5173")]
application = get_default_application()


def _ws_url(code: str, token: str) -> str:
    return f"/ws/rooms/{code}/?token={token}"


async def _db(fn: Any) -> Any:
    return await database_sync_to_async(fn)()


async def _reset_channel_layer() -> None:
    """Flush cached channel layers so per-loop asyncio locks never cross test event loops."""
    for alias in list(channel_layers.backends.keys()):
        layer = channel_layers.backends.pop(alias)
        cleaners = list(getattr(layer, "receive_cleaners", []))
        if cleaners:
            for cleaner in cleaners:
                if not cleaner.done():
                    cleaner.cancel()
            await asyncio.gather(*cleaners, return_exceptions=True)
        flush = getattr(layer, "flush", None)
        if flush is not None:
            await flush()


@pytest.fixture(autouse=True)
async def reset_presence() -> AsyncIterator[None]:
    """Clean up grace timers, channel layer pools, and thread DB sessions per async test."""
    await presence_manager.reset_all()
    yield
    await presence_manager.reset_all()
    await _reset_channel_layer()
    await database_sync_to_async(connections.close_all)()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_duplicate_tab_replacement_closes_old_with_4001() -> None:
    """Connecting a second tab for the same player evicts the first tab with code 4001."""
    room: Room = await _db(RoomFactory)
    player: Player = await _db(lambda: PlayerFactory(room=room, nickname="TabHero", is_host=True))
    token = sign_player_token(player.id, room.code)

    tab1 = WebsocketCommunicator(application, _ws_url(room.code, token), headers=ORIGIN_HEADER)
    tab2 = WebsocketCommunicator(application, _ws_url(room.code, token), headers=ORIGIN_HEADER)

    try:
        connected1, _ = await tab1.connect()
        assert connected1
        snap1 = await tab1.receive_json_from()
        assert snap1["type"] == "room_snapshot"

        # Tab 2 connects for the exact same player
        connected2, _ = await tab2.connect()
        assert connected2
        snap2 = await tab2.receive_json_from()
        assert snap2["type"] == "room_snapshot"

        # Tab 1 is closed cleanly with close code 4001
        close_frame = await tab1.receive_output(timeout=2.0)
        assert close_frame["type"] == "websocket.close"
        assert close_frame["code"] == 4001

        # Tab 2 remains open and functional
        await tab2.send_json_to({"v": 1, "type": "ping", "payload": {}})
        pong = await tab2.receive_json_from()
        assert pong["type"] == "pong"
    finally:
        await tab1.disconnect()
        await tab2.disconnect()


@pytest.mark.django_db(transaction=True)
def test_duplicate_client_msg_id_deduplication() -> None:
    """Duplicate client_msg_id is idempotent and creates only 1 Message/Event."""
    room = RoomFactory(config={"min_humans": 3})
    p1 = PlayerFactory(room=room, nickname="Alice", is_host=True, connected=True)
    PlayerFactory(room=room, nickname="Bob", connected=True)
    PlayerFactory(room=room, nickname="Charlie", connected=True)

    # Start game and advance to CHAT phase
    start_game(room.id, p1.id)
    round_obj = room.rounds.order_by("-game_index", "-number").first()
    assert round_obj is not None
    advance_phase(round_obj.id)

    client_uuid = str(uuid4())

    # Send first chat message
    env1 = send_chat_message(
        room.id,
        p1.id,
        "Hello world!",
        client_msg_id=client_uuid,
    )
    assert env1["type"] == "chat_message"
    assert env1["payload"]["text"] == "Hello world!"
    assert env1["payload"]["client_msg_id"] == client_uuid
    assert env1["seq"] is not None

    # Re-send identical chat message with the exact same client_msg_id
    env2 = send_chat_message(
        room.id,
        p1.id,
        "Hello world!",
        client_msg_id=client_uuid,
    )
    assert env2["type"] == "chat_message"
    assert env2["payload"]["client_msg_id"] == client_uuid
    # Deduplicated response does not increment or append a new seq event
    assert env2["seq"] is None

    # Verify only exactly 1 Message row exists with this client_msg_id
    messages = Message.objects.filter(client_msg_id=client_uuid)
    assert messages.count() == 1

    # Verify only 1 chat_message event was appended to Event log
    events = Event.objects.filter(room=room, type="chat_message")
    assert events.count() == 1


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@override_settings(PRESENCE_GRACE_SECONDS=0.05)
async def test_host_departure_promotes_next_player() -> None:
    """When the room host disconnects and grace period expires, next human player is promoted."""
    room: Room = await _db(lambda: RoomFactory(config={"min_humans": 3}))
    host: Player = await _db(
        lambda: PlayerFactory(room=room, nickname="OriginalHost", is_host=True)
    )
    guest1: Player = await _db(
        lambda: PlayerFactory(
            room=room,
            nickname="GuestAlpha",
            joined_at=timezone.now() - timedelta(minutes=5),
        )
    )
    guest2: Player = await _db(
        lambda: PlayerFactory(
            room=room,
            nickname="GuestBeta",
            joined_at=timezone.now() - timedelta(minutes=3),
        )
    )
    guest3: Player = await _db(
        lambda: PlayerFactory(
            room=room,
            nickname="GuestGamma",
            joined_at=timezone.now() - timedelta(minutes=1),
        )
    )

    c_host = WebsocketCommunicator(
        application,
        _ws_url(room.code, sign_player_token(host.id, room.code)),
        headers=ORIGIN_HEADER,
    )
    c_guest1 = WebsocketCommunicator(
        application,
        _ws_url(room.code, sign_player_token(guest1.id, room.code)),
        headers=ORIGIN_HEADER,
    )
    c_guest2 = WebsocketCommunicator(
        application,
        _ws_url(room.code, sign_player_token(guest2.id, room.code)),
        headers=ORIGIN_HEADER,
    )
    c_guest3 = WebsocketCommunicator(
        application,
        _ws_url(room.code, sign_player_token(guest3.id, room.code)),
        headers=ORIGIN_HEADER,
    )

    try:
        assert (await c_host.connect())[0]
        await c_host.receive_json_from()  # snapshot

        assert (await c_guest1.connect())[0]
        await c_guest1.receive_json_from()  # snapshot
        await c_host.receive_json_from()  # player_joined

        assert (await c_guest2.connect())[0]
        await c_guest2.receive_json_from()  # snapshot
        await c_host.receive_json_from()  # player_joined
        await c_guest1.receive_json_from()  # player_joined

        assert (await c_guest3.connect())[0]
        await c_guest3.receive_json_from()  # snapshot
        await c_host.receive_json_from()  # player_joined
        await c_guest1.receive_json_from()  # player_joined
        await c_guest2.receive_json_from()  # player_joined

        # Host disconnects
        await c_host.disconnect()

        # Guests observe presence away
        ev_pres1 = await c_guest1.receive_json_from()
        assert ev_pres1["type"] == "presence"
        assert ev_pres1["payload"]["connected"] is False

        # Wait for grace period expiration (0.05s override)
        ev_left = await c_guest1.receive_json_from(timeout=2.0)
        assert ev_left["type"] == "player_left"
        assert ev_left["payload"]["player_id"] == str(host.id)
        assert ev_left["payload"]["reason"] == "grace_expired"
        assert ev_left["payload"]["new_host_id"] == str(guest1.id)

        # Verify DB state: guest1 is now host, host is no longer host
        updated_room = await _db(lambda: Room.objects.get(id=room.id))
        updated_host = await _db(lambda: Player.objects.get(id=host.id))
        updated_g1 = await _db(lambda: Player.objects.get(id=guest1.id))

        assert updated_host.is_host is False
        assert updated_g1.is_host is True
        assert updated_room.host_id == updated_g1.id

        # New host can now start the game (3 remaining humans meet min_humans=3)
        await c_guest1.send_json_to({"v": 1, "type": "start_game", "payload": {}})
        ev_phase = await c_guest1.receive_json_from(timeout=2.0)
        assert ev_phase["type"] == "phase_changed"
        assert ev_phase["payload"]["phase"] == RoundPhase.ANSWER
    finally:
        await c_guest1.disconnect()
        await c_guest2.disconnect()
        await c_guest3.disconnect()


@pytest.mark.django_db(transaction=True)
def test_120s_empty_room_abandonment() -> None:
    """cleanup_abandoned_rooms abandons empty rooms > 120s and preserves active/recent rooms."""
    now = timezone.now()

    # Room 1: LOBBY, all humans disconnected 150 seconds ago -> SHOULD BE ABANDONED
    r_lobby_abandoned = RoomFactory(status=RoomStatus.LOBBY)
    PlayerFactory(
        room=r_lobby_abandoned,
        connected=False,
        last_seen_at=now - timedelta(seconds=150),
    )

    # Room 2: IN_PROGRESS, all humans disconnected 200 seconds ago -> SHOULD BE ABANDONED
    r_progress_abandoned = RoomFactory(status=RoomStatus.IN_PROGRESS)
    PlayerFactory(
        room=r_progress_abandoned,
        connected=False,
        last_seen_at=now - timedelta(seconds=200),
    )

    # Room 3: Active with connected human -> MUST NOT BE ABANDONED
    r_active = RoomFactory(status=RoomStatus.LOBBY)
    PlayerFactory(room=r_active, connected=True, last_seen_at=now)

    # Room 4: Empty, but disconnected only 30 seconds ago -> MUST NOT BE ABANDONED
    r_recent = RoomFactory(status=RoomStatus.LOBBY)
    PlayerFactory(
        room=r_recent,
        connected=False,
        last_seen_at=now - timedelta(seconds=30),
    )

    abandoned = cleanup_abandoned_rooms(timeout_seconds=120, now=now)

    assert r_lobby_abandoned.code in abandoned
    assert r_progress_abandoned.code in abandoned
    assert r_active.code not in abandoned
    assert r_recent.code not in abandoned

    r_lobby_abandoned.refresh_from_db()
    r_progress_abandoned.refresh_from_db()
    r_active.refresh_from_db()
    r_recent.refresh_from_db()

    assert r_lobby_abandoned.status == RoomStatus.ABANDONED
    assert r_progress_abandoned.status == RoomStatus.ABANDONED
    assert r_active.status == RoomStatus.LOBBY
    assert r_recent.status == RoomStatus.LOBBY

    # Verify room_abandoned event was appended
    event = Event.objects.filter(room=r_lobby_abandoned, type="room_abandoned").first()
    assert event is not None
    assert event.payload["reason"] == "empty_timeout"

    # Test Celery shared_task wrapper
    task_res = cleanup_abandoned_rooms_task(timeout_seconds=120)
    assert isinstance(task_res, list)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_mid_phase_drop_and_reconnect_preserves_state() -> None:
    """Player dropping mid-phase can reconnect, restore fresh snapshot, and continue play."""
    room: Room = await _db(lambda: RoomFactory(config={"min_humans": 3}))
    p1: Player = await _db(lambda: PlayerFactory(room=room, nickname="Player1", is_host=True))
    p2: Player = await _db(lambda: PlayerFactory(room=room, nickname="Player2"))
    p3: Player = await _db(lambda: PlayerFactory(room=room, nickname="Player3"))

    c1 = WebsocketCommunicator(
        application,
        _ws_url(room.code, sign_player_token(p1.id, room.code)),
        headers=ORIGIN_HEADER,
    )
    c2 = WebsocketCommunicator(
        application,
        _ws_url(room.code, sign_player_token(p2.id, room.code)),
        headers=ORIGIN_HEADER,
    )
    c3 = WebsocketCommunicator(
        application,
        _ws_url(room.code, sign_player_token(p3.id, room.code)),
        headers=ORIGIN_HEADER,
    )

    try:
        assert (await c1.connect())[0]
        await c1.receive_json_from()
        assert (await c2.connect())[0]
        await c2.receive_json_from()
        assert (await c3.connect())[0]
        await c3.receive_json_from()

        # Drain lobby events
        while await c1.receive_nothing() is False:
            await c1.receive_json_from()

        # P1 starts game -> ANSWER phase begins
        await c1.send_json_to({"v": 1, "type": "start_game", "payload": {}})
        phase_ev = await c1.receive_json_from()
        assert phase_ev["type"] == "phase_changed"
        assert phase_ev["payload"]["phase"] == RoundPhase.ANSWER

        # P1 submits answer
        await c1.send_json_to({"v": 1, "type": "submit_answer", "payload": {"text": "P1 answer"}})

        # P2 drops connection mid-phase (network loss)
        await c2.disconnect()

        # Room advances to CHAT phase
        round_obj = await _db(lambda: room.rounds.order_by("-game_index", "-number").first())
        await _db(lambda: advance_phase(round_obj.id))

        # P3 sends a message while P2 is offline
        await c3.send_json_to(
            {
                "v": 1,
                "type": "send_message",
                "payload": {"text": "Message while P2 offline", "client_msg_id": str(uuid4())},
            }
        )

        # P2 reconnects with their valid token!
        c2_reconnect = WebsocketCommunicator(
            application,
            _ws_url(room.code, sign_player_token(p2.id, room.code)),
            headers=ORIGIN_HEADER,
        )
        assert (await c2_reconnect.connect())[0]
        reconnect_snap = await c2_reconnect.receive_json_from()

        # Verify snapshot accurately reflects current CHAT state
        assert reconnect_snap["type"] == "room_snapshot"
        payload = reconnect_snap["payload"]
        assert payload["phase"] == RoundPhase.CHAT
        assert payload["round_number"] == 1
        assert len(payload["seats"]) == 4  # 3 humans + 1 bot
        assert payload["my_seat_id"] is not None

        # Verify P3's message is in messages
        message_texts = [m["text"] for m in payload["messages"]]
        assert "Message while P2 offline" in message_texts

        # Drain c1 before testing new message broadcast
        while await c1.receive_nothing() is False:
            await c1.receive_json_from()

        # P2 sends a message now that they are reconnected
        await c2_reconnect.send_json_to(
            {
                "v": 1,
                "type": "send_message",
                "payload": {"text": "I am back!", "client_msg_id": str(uuid4())},
            }
        )

        # P1 receives P2's new message
        msg = await c1.receive_json_from(timeout=2.0)
        assert msg["type"] == "chat_message"
        assert msg["payload"]["text"] == "I am back!"

        await c2_reconnect.disconnect()
    finally:
        await c1.disconnect()
        await c3.disconnect()
