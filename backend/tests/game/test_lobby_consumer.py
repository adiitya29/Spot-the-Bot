"""Phase 2 WebSocket lobby consumer, presence grace period, auth, and Event log tests."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime

import pytest
from channels.db import database_sync_to_async
from channels.layers import channel_layers
from channels.testing import WebsocketCommunicator
from django.db import connections
from django.test import override_settings
from freezegun import freeze_time

from apps.common.models import Event
from apps.game.presence import presence_manager
from apps.rooms.models import RoomStatus
from apps.rooms.tokens import sign_player_token
from config.asgi import application
from tests.rooms.factories import PlayerFactory, RoomFactory

ORIGIN_HEADER = [(b"origin", b"http://localhost:5173")]


async def _db[T](fn: Callable[[], T]) -> T:
    """Execute sync ORM work in a thread and close thread-local DB connections immediately."""

    def _wrapped() -> T:
        try:
            return fn()
        finally:
            connections.close_all()

    return await asyncio.to_thread(_wrapped)


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


def _ws_url(room_code: str, token: str | None = None) -> str:
    if token is None:
        return f"/ws/rooms/{room_code}/"
    return f"/ws/rooms/{room_code}/?token={token}"


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_four_clients_join_presence_host_readiness_and_events() -> None:
    """Four tabs join in real time, receive snapshots, track seq Events, and validate start."""
    room = await _db(
        lambda: RoomFactory(
            config={
                "rounds": 3,
                "phase_durations": {"answer": 45, "chat": 120, "vote": 30, "reveal": 12},
                "min_humans": 3,
                "allow_replay_use": False,
            }
        )
    )
    players = await _db(
        lambda: [
            PlayerFactory(room=room, nickname="Alice", is_host=True),
            PlayerFactory(room=room, nickname="Bob"),
            PlayerFactory(room=room, nickname="Charlie"),
            PlayerFactory(room=room, nickname="Dana"),
        ]
    )
    comms = [
        WebsocketCommunicator(
            application,
            _ws_url(room.code, sign_player_token(p.id, room.code)),
            headers=ORIGIN_HEADER,
        )
        for p in players
    ]

    try:
        # 1st player connects (host)
        ok, _ = await comms[0].connect()
        assert ok
        snap0 = await comms[0].receive_json_from()
        assert snap0["type"] == "room_snapshot"
        assert snap0["seq"] == 1
        assert snap0["payload"]["can_start"] is False
        assert snap0["payload"]["my_player_id"] == str(players[0].id)
        assert len(snap0["payload"]["roster"]) == 1
        assert "is_bot" not in json.dumps(snap0)

        # Host cannot start with only 1 player connected
        await comms[0].send_json_to({"v": 1, "id": "m1", "type": "start_game", "payload": {}})
        err_few = await comms[0].receive_json_from()
        assert err_few["type"] == "error"
        assert err_few["payload"]["code"] == "not_enough_players"

        # 2nd player connects
        ok, _ = await comms[1].connect()
        assert ok
        snap1 = await comms[1].receive_json_from()
        assert snap1["seq"] == 2
        assert len(snap1["payload"]["roster"]) == 2
        join1 = await comms[0].receive_json_from()
        assert join1["type"] == "player_joined"
        assert join1["seq"] == 2
        assert join1["payload"]["player"]["nickname"] == "Bob"
        assert join1["payload"]["can_start"] is False

        # Non-host cannot start
        await comms[1].send_json_to({"v": 1, "id": "m2", "type": "start_game", "payload": {}})
        err_host = await comms[1].receive_json_from()
        assert err_host["payload"]["code"] == "not_host"

        # 3rd player connects -> hits min_humans=3, can_start flips True
        ok, _ = await comms[2].connect()
        assert ok
        snap2 = await comms[2].receive_json_from()
        assert snap2["seq"] == 3
        assert snap2["payload"]["can_start"] is True
        for c in (comms[0], comms[1]):
            ev = await c.receive_json_from()
            assert ev["type"] == "player_joined"
            assert ev["seq"] == 3
            assert ev["payload"]["can_start"] is True

        # 4th player connects
        ok, _ = await comms[3].connect()
        assert ok
        snap3 = await comms[3].receive_json_from()
        assert snap3["seq"] == 4
        assert len(snap3["payload"]["roster"]) == 4
        for c in (comms[0], comms[1], comms[2]):
            ev = await c.receive_json_from()
            assert ev["type"] == "player_joined"
            assert ev["seq"] == 4
            assert ev["payload"]["player"]["nickname"] == "Dana"

        # Ping -> pong
        await comms[0].send_json_to({"v": 1, "id": "p1", "type": "ping", "payload": {}})
        pong = await comms[0].receive_json_from()
        assert pong["type"] == "pong"
        assert isinstance(pong["payload"]["server_time"], int)

        # Host start validation now passes readiness check (reaches Phase 3 stub)
        await comms[0].send_json_to({"v": 1, "id": "m3", "type": "start_game", "payload": {}})
        start_ack = await comms[0].receive_json_from()
        assert start_ack["payload"]["code"] == "game_start_pending_phase3"

        # Event log recorded seq 1..4 strictly sequentially
        seqs = await _db(
            lambda: list(Event.objects.filter(room=room).values_list("seq", flat=True))
        )
        assert seqs == [1, 2, 3, 4]
    finally:
        for c in comms:
            await c.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_refresh_within_grace_restores_lobby_without_player_left() -> None:
    """Refreshing a tab emits presence offline/online and restores full snapshot."""
    room = await _db(RoomFactory)
    host = await _db(lambda: PlayerFactory(room=room, nickname="Host", is_host=True))
    guest = await _db(lambda: PlayerFactory(room=room, nickname="Guest"))

    c_host = WebsocketCommunicator(
        application,
        _ws_url(room.code, sign_player_token(host.id, room.code)),
        headers=ORIGIN_HEADER,
    )
    c_guest = WebsocketCommunicator(
        application,
        _ws_url(room.code, sign_player_token(guest.id, room.code)),
        headers=ORIGIN_HEADER,
    )
    c_guest_refreshed = WebsocketCommunicator(
        application,
        _ws_url(room.code, sign_player_token(guest.id, room.code)),
        headers=ORIGIN_HEADER,
    )

    try:
        assert (await c_host.connect())[0]
        await c_host.receive_json_from()

        assert (await c_guest.connect())[0]
        await c_guest.receive_json_from()
        ev_join = await c_host.receive_json_from()
        assert ev_join["type"] == "player_joined"

        # Guest disconnects (simulating page refresh)
        await c_guest.disconnect()
        ev_away = await c_host.receive_json_from()
        assert ev_away["type"] == "presence"
        assert ev_away["payload"]["player_id"] == str(guest.id)
        assert ev_away["payload"]["connected"] is False

        # Guest reconnects quickly within 30s grace period
        assert (await c_guest_refreshed.connect())[0]
        snap_restored = await c_guest_refreshed.receive_json_from()
        assert snap_restored["type"] == "room_snapshot"
        assert len(snap_restored["payload"]["roster"]) == 2
        assert all(p["connected"] is True for p in snap_restored["payload"]["roster"])

        ev_back = await c_host.receive_json_from()
        assert ev_back["type"] == "presence"
        assert ev_back["payload"]["player_id"] == str(guest.id)
        assert ev_back["payload"]["connected"] is True
    finally:
        await c_host.disconnect()
        await c_guest_refreshed.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@override_settings(PRESENCE_GRACE_SECONDS=0.05)
async def test_disconnect_past_grace_period_emits_player_left() -> None:
    """When a player stays disconnected past grace period, player_left is broadcast."""
    room = await _db(RoomFactory)
    host = await _db(lambda: PlayerFactory(room=room, nickname="Host", is_host=True))
    guest = await _db(lambda: PlayerFactory(room=room, nickname="Leaver"))

    c_host = WebsocketCommunicator(
        application,
        _ws_url(room.code, sign_player_token(host.id, room.code)),
        headers=ORIGIN_HEADER,
    )
    c_guest = WebsocketCommunicator(
        application,
        _ws_url(room.code, sign_player_token(guest.id, room.code)),
        headers=ORIGIN_HEADER,
    )

    try:
        assert (await c_host.connect())[0]
        await c_host.receive_json_from()
        assert (await c_guest.connect())[0]
        await c_guest.receive_json_from()
        await c_host.receive_json_from()

        await c_guest.disconnect()
        ev_away = await c_host.receive_json_from()
        assert ev_away["type"] == "presence"
        assert ev_away["payload"]["connected"] is False

        ev_left = await c_host.receive_json_from(timeout=2.0)
        assert ev_left["type"] == "player_left"
        assert ev_left["payload"]["player_id"] == str(guest.id)
        assert ev_left["payload"]["nickname"] == "Leaver"
        assert ev_left["payload"]["reason"] == "grace_expired"
    finally:
        await c_host.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_duplicate_tab_latest_connection_wins() -> None:
    """Opening a second socket for the same player closes the old tab cleanly with 4001."""
    room = await _db(RoomFactory)
    player = await _db(lambda: PlayerFactory(room=room, nickname="Tabs", is_host=True))
    token = sign_player_token(player.id, room.code)

    tab1 = WebsocketCommunicator(application, _ws_url(room.code, token), headers=ORIGIN_HEADER)
    tab2 = WebsocketCommunicator(application, _ws_url(room.code, token), headers=ORIGIN_HEADER)

    try:
        assert (await tab1.connect())[0]
        await tab1.receive_json_from()

        assert (await tab2.connect())[0]
        snap2 = await tab2.receive_json_from()
        assert snap2["type"] == "room_snapshot"

        close_frame = await tab1.receive_output(timeout=2.0)
        assert close_frame["type"] == "websocket.close"
        assert close_frame["code"] == 4001

        await _db(player.refresh_from_db)
        assert player.connected is True
    finally:
        await tab1.disconnect()
        await tab2.disconnect()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_rejects_invalid_token_wrong_room_bot_abandoned_and_bad_origin() -> None:
    """Rejects missing/invalid/expired tokens, wrong room, bot token, abandoned room, and Origin."""
    room_a = await _db(RoomFactory)
    room_b = await _db(RoomFactory)
    player_a = await _db(lambda: PlayerFactory(room=room_a, nickname="Alice"))
    bot_a = await _db(lambda: PlayerFactory(room=room_a, nickname="CovertBot", is_bot=True))
    abandoned = await _db(lambda: RoomFactory(status=RoomStatus.ABANDONED))
    abandoned_player = await _db(lambda: PlayerFactory(room=abandoned, nickname="Ghost"))

    valid_token = sign_player_token(player_a.id, room_a.code)

    # Disallowed Origin
    bad_origin = WebsocketCommunicator(
        application,
        _ws_url(room_a.code, valid_token),
        headers=[(b"origin", b"http://evil.example")],
    )
    assert not (await bad_origin.connect())[0]

    # Missing token
    no_token = WebsocketCommunicator(application, _ws_url(room_a.code), headers=ORIGIN_HEADER)
    assert not (await no_token.connect())[0]

    # Tampered token
    bad_token = WebsocketCommunicator(
        application,
        _ws_url(room_a.code, f"{valid_token}tamper"),
        headers=ORIGIN_HEADER,
    )
    assert not (await bad_token.connect())[0]

    # Wrong room code
    wrong_room = WebsocketCommunicator(
        application,
        _ws_url(room_b.code, valid_token),
        headers=ORIGIN_HEADER,
    )
    assert not (await wrong_room.connect())[0]

    # Bot token
    bot_comm = WebsocketCommunicator(
        application,
        _ws_url(room_a.code, sign_player_token(bot_a.id, room_a.code)),
        headers=ORIGIN_HEADER,
    )
    assert not (await bot_comm.connect())[0]

    # Abandoned room
    abandoned_comm = WebsocketCommunicator(
        application,
        _ws_url(abandoned.code, sign_player_token(abandoned_player.id, abandoned.code)),
        headers=ORIGIN_HEADER,
    )
    assert not (await abandoned_comm.connect())[0]

    # Expired token (> 24h)
    with freeze_time(datetime(2026, 11, 10, 0, 0, 0, tzinfo=UTC)):
        old_token = sign_player_token(player_a.id, room_a.code)
    expired_comm = WebsocketCommunicator(
        application,
        _ws_url(room_a.code, old_token),
        headers=ORIGIN_HEADER,
    )
    assert not (await expired_comm.connect())[0]


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_rejects_oversized_and_malformed_frames() -> None:
    """Enforces 2 KB frame limit and valid JSON v1 envelope."""
    room = await _db(RoomFactory)
    player = await _db(lambda: PlayerFactory(room=room, nickname="Checker"))
    comm = WebsocketCommunicator(
        application,
        _ws_url(room.code, sign_player_token(player.id, room.code)),
        headers=ORIGIN_HEADER,
    )

    try:
        assert (await comm.connect())[0]
        await comm.receive_json_from()

        await comm.send_to(text_data="x" * 2500)
        err_size = await comm.receive_json_from()
        assert err_size["type"] == "error"
        assert err_size["payload"]["code"] == "payload_too_large"

        await comm.send_to(text_data="{not-json")
        err_json = await comm.receive_json_from()
        assert err_json["payload"]["code"] == "invalid_json"

        await comm.send_json_to({"v": 99, "type": "ping", "payload": {}})
        err_env = await comm.receive_json_from()
        assert err_env["payload"]["code"] == "invalid_envelope"
    finally:
        await comm.disconnect()
