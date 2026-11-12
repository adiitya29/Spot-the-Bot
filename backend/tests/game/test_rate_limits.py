"""Rate-limiter unit tests and Phase 3 consumer integration tests (ANSWER, CHAT, typing)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable

import pytest
from channels.db import database_sync_to_async
from channels.layers import channel_layers
from channels.testing import WebsocketCommunicator
from django.db import connections
from django.test import override_settings

from apps.common.models import Event
from apps.common.redis import get_redis_client
from apps.game.presence import presence_manager
from apps.game.rate_limits import SlidingWindowLimiter
from apps.game.scheduler import DEADLINES_KEY
from apps.rooms.tokens import sign_player_token
from config.asgi import application
from tests.rooms.factories import PlayerFactory, RoomFactory

ORIGIN_HEADER = [(b"origin", b"http://localhost:5173")]


async def _db[T](fn: Callable[[], T]) -> T:
    def _wrapped() -> T:
        try:
            return fn()
        finally:
            connections.close_all()

    return await asyncio.to_thread(_wrapped)


async def _reset_runtime() -> None:
    await presence_manager.reset_all()
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

    def _clear_redis() -> None:
        client = get_redis_client()
        client.delete(DEADLINES_KEY)
        for prefix in ("stb:rl:*", "stb:lock:*"):
            keys = list(client.scan_iter(match=prefix))
            if keys:
                client.delete(*keys)
        client.close()

    await asyncio.to_thread(_clear_redis)


@pytest.fixture(autouse=True)
async def isolate_async_state() -> AsyncIterator[None]:
    """Isolate presence, Redis keys, channel layer locks, and DB sessions per test."""
    await _reset_runtime()
    yield
    await _reset_runtime()
    await database_sync_to_async(connections.close_all)()


def test_sliding_window_limiter_with_fake_clock() -> None:
    """SlidingWindowLimiter blocks bursts past limit and reopens once window expires."""
    now = [100.0]
    limiter = SlidingWindowLimiter(
        max_events=3,
        window_seconds=5.0,
        clock=lambda: now[0],
        redis_client=None,
    )
    # Test pure in-memory limiter via explicit _allow_memory or empty REDIS_URL override
    with override_settings(REDIS_URL=""):
        assert limiter.allow("p1").allowed is True
        now[0] += 0.5
        assert limiter.allow("p1").allowed is True
        now[0] += 0.5
        assert limiter.allow("p1").allowed is True
        blocked = limiter.allow("p1")
        assert blocked.allowed is False
        assert blocked.retry_after_seconds == pytest.approx(4.0, abs=0.05)

        # Slide past first event (+5.1s total from 100.0)
        now[0] = 105.1
        assert limiter.allow("p1").allowed is True


def test_sliding_window_limiter_with_real_redis() -> None:
    """SlidingWindowLimiter enforces exact sliding window in Redis with injected clock."""
    now = [200.0]
    client = get_redis_client()
    key = "stb:rl:unit-test-window"
    client.delete(key)
    try:
        limiter = SlidingWindowLimiter(
            max_events=2,
            window_seconds=4.0,
            clock=lambda: now[0],
            redis_client=client,
        )
        assert limiter.allow(key).allowed is True
        now[0] += 1.0
        assert limiter.allow(key).allowed is True
        blocked = limiter.allow(key)
        assert blocked.allowed is False
        assert blocked.remaining == 0
        assert blocked.retry_after_seconds == pytest.approx(3.0, abs=0.05)

        now[0] = 204.1
        assert limiter.allow(key).allowed is True
    finally:
        client.delete(key)
        client.close()


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
@override_settings(CHAT_RATE_LIMIT_COUNT=2, CHAT_RATE_LIMIT_WINDOW_SECONDS=10.0)
async def test_consumer_answer_chat_typing_rate_limit_and_reconnect() -> None:
    """Multi-client WS test: start_game -> submit_answer -> CHAT -> typing -> rate limit."""
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
            PlayerFactory(room=room, nickname="Carol"),
        ]
    )
    tokens = [sign_player_token(p.id, room.code) for p in players]
    comms = [
        WebsocketCommunicator(
            application,
            f"/ws/rooms/{room.code}/?token={t}",
            headers=ORIGIN_HEADER,
        )
        for t in tokens
    ]
    reconnected_alice: WebsocketCommunicator | None = None

    try:
        for i, comm in enumerate(comms):
            assert (await comm.connect())[0]
            await comm.receive_json_from()  # room_snapshot
            for earlier in comms[:i]:
                await earlier.receive_json_from()  # player_joined

        # Host starts game -> all receive phase_changed(answer) + personalized room_snapshot
        await comms[0].send_json_to({"v": 1, "id": "c1", "type": "start_game", "payload": {}})
        my_seats: list[str] = []
        for c in comms:
            ev_phase = await c.receive_json_from()
            assert ev_phase["type"] == "phase_changed"
            assert ev_phase["payload"]["phase"] == "answer"
            assert "my_seat_id" not in ev_phase["payload"]
            snap = await c.receive_json_from()
            assert snap["type"] == "room_snapshot"
            seat_id = snap["payload"]["my_seat_id"]
            assert seat_id
            my_seats.append(seat_id)

        # Chat rejected during ANSWER
        await comms[0].send_json_to(
            {"v": 1, "id": "c2", "type": "send_message", "payload": {"text": "too early"}}
        )
        err_early = await comms[0].receive_json_from()
        assert err_early["type"] == "error"
        assert err_early["payload"]["code"] == "invalid_phase"

        # All 3 humans submit answers -> triggers answers_revealed + phase_changed(chat)
        await comms[0].send_json_to(
            {"v": 1, "id": "a0", "type": "submit_answer", "payload": {"text": "Cold pizza rules"}}
        )
        await comms[1].send_json_to(
            {"v": 1, "id": "a1", "type": "submit_answer", "payload": {"text": "Naps at 4pm"}}
        )
        await comms[2].send_json_to(
            {"v": 1, "id": "a2", "type": "submit_answer", "payload": {"text": "I never fold socks"}}
        )

        for c in comms:
            ev_rev = await c.receive_json_from()
            assert ev_rev["type"] == "answers_revealed"
            assert len(ev_rev["payload"]["answers"]) == 4  # 3 humans + 1 bot
            assert "is_bot" not in json.dumps(ev_rev)
            ev_chat = await c.receive_json_from()
            assert ev_chat["type"] == "phase_changed"
            assert ev_chat["payload"]["phase"] == "chat"

        # Typing indicator: ephemeral (seq=None), broadcast only to others, omitted from Event table
        await comms[0].send_json_to(
            {"v": 1, "id": "t1", "type": "typing", "payload": {"is_typing": True}}
        )
        for peer in (comms[1], comms[2]):
            ev_typ = await peer.receive_json_from()
            assert ev_typ["type"] == "typing"
            assert ev_typ["seq"] is None
            assert ev_typ["payload"] == {"seat_id": my_seats[0], "is_typing": True}

        # Alice sends 2 allowed chat messages, 3rd hits sliding-window rate limit
        for n in (1, 2):
            await comms[0].send_json_to(
                {
                    "v": 1,
                    "id": f"m{n}",
                    "type": "send_message",
                    "payload": {"text": f"msg #{n}"},
                }
            )
            for c in comms:
                ev_msg = await c.receive_json_from()
                assert ev_msg["type"] == "chat_message"
                assert ev_msg["payload"]["text"] == f"msg #{n}"

        await comms[0].send_json_to(
            {"v": 1, "id": "m3", "type": "send_message", "payload": {"text": "spam!"}}
        )
        err_rl = await comms[0].receive_json_from()
        assert err_rl["type"] == "error"
        assert err_rl["payload"]["code"] == "rate_limited"

        # Alice refreshes mid-CHAT -> snapshot restores topic, answers, messages, my_seat_id
        await comms[0].disconnect()
        reconnected_alice = WebsocketCommunicator(
            application,
            f"/ws/rooms/{room.code}/?token={tokens[0]}",
            headers=ORIGIN_HEADER,
        )
        assert (await reconnected_alice.connect())[0]
        restored = await reconnected_alice.receive_json_from()
        assert restored["type"] == "room_snapshot"
        assert restored["payload"]["phase"] == "chat"
        assert restored["payload"]["my_seat_id"] == my_seats[0]
        assert len(restored["payload"]["answers"]) == 4
        assert [m["text"] for m in restored["payload"]["messages"]] == ["msg #1", "msg #2"]

        # Confirm zero typing events in persistent Event table
        has_typing_event = await _db(
            lambda: Event.objects.filter(room=room, type="typing").exists()
        )
        assert has_typing_event is False
    finally:
        for c in comms:
            await c.disconnect()
        if reconnected_alice is not None:
            await reconnected_alice.disconnect()
