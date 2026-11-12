"""Security test suite ensuring zero pre-REVEAL leakage of bot identity or metadata."""

from __future__ import annotations

import asyncio
import json
import random
from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from channels.db import database_sync_to_async
from channels.layers import channel_layers
from channels.testing import WebsocketCommunicator
from django.db import connections
from django.test import Client

from apps.bot.stub import post_stub_chat_message
from apps.common.redis import get_redis_client
from apps.game.models import Round, RoundPhase
from apps.game.presence import presence_manager
from apps.game.scheduler import DEADLINES_KEY
from apps.game.state_machine import advance_phase
from config.asgi import application
from tests.rooms.factories import PlayerFactory

ORIGIN_HEADER = [(b"origin", b"http://localhost:5173")]

FORBIDDEN_PRE_REVEAL_KEYS = frozenset(
    {
        "is_bot",
        "meta",
        "bot_persona",
        "style_profile",
        "bot_seat_id",
        "bot_alias",
    }
)

FORBIDDEN_SEAT_KEYS = frozenset({"player_id", "nickname", "is_host", "is_bot", "meta"})


async def _db[T](fn: Callable[[], T]) -> T:
    def _wrapped() -> T:
        try:
            return fn()
        finally:
            connections.close_all()

    return await asyncio.to_thread(_wrapped)


def _clear_redis_keys() -> None:
    client = get_redis_client()
    client.delete(DEADLINES_KEY)
    for prefix in ("stb:rl:*", "stb:lock:*"):
        keys = list(client.scan_iter(match=prefix))
        if keys:
            client.delete(*keys)
    client.close()


@pytest.fixture(autouse=True)
async def isolate_security_env() -> AsyncIterator[None]:
    """Reset Channels layer, presence, Redis, and DB connections around security tests."""
    await presence_manager.reset_all()
    for alias in list(channel_layers.backends.keys()):
        layer = channel_layers.backends.pop(alias)
        flush = getattr(layer, "flush", None)
        if flush is not None:
            await flush()
    await asyncio.to_thread(_clear_redis_keys)
    yield
    await presence_manager.reset_all()
    await asyncio.to_thread(_clear_redis_keys)
    await database_sync_to_async(connections.close_all)()


def scan_payload_for_leaks(
    data: Any,
    *,
    bot_player_id: str | None = None,
    bot_nickname: str = "Bot",
    path: str = "root",
    allow_reveal_keys: bool = False,
) -> list[str]:
    """Recursively scan any JSON structure for forbidden keys, bot IDs, or seat->player mappings."""
    findings: list[str] = []
    forbidden_keys = (
        frozenset({"meta", "bot_persona", "style_profile"})
        if allow_reveal_keys
        else FORBIDDEN_PRE_REVEAL_KEYS
    )

    if isinstance(data, dict):
        for key, value in data.items():
            key_path = f"{path}.{key}"
            if key in forbidden_keys:
                findings.append(f"Forbidden key '{key}' at {key_path}")
            if not allow_reveal_keys and key == "seats" and isinstance(value, list):
                for idx, seat in enumerate(value):
                    if isinstance(seat, dict):
                        bad = set(seat.keys()) & FORBIDDEN_SEAT_KEYS
                        if bad:
                            findings.append(
                                f"Forbidden seat identity key(s) {sorted(bad)} at {key_path}[{idx}]"
                            )
            if not allow_reveal_keys and key in {"answers", "messages"} and isinstance(value, list):
                for idx, item in enumerate(value):
                    if isinstance(item, dict):
                        bad = set(item.keys()) & FORBIDDEN_SEAT_KEYS
                        if bad:
                            findings.append(
                                f"Forbidden player key(s) {sorted(bad)} at {key_path}[{idx}]"
                            )
            findings.extend(
                scan_payload_for_leaks(
                    value,
                    bot_player_id=bot_player_id,
                    bot_nickname=bot_nickname,
                    path=key_path,
                    allow_reveal_keys=allow_reveal_keys,
                )
            )
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            findings.extend(
                scan_payload_for_leaks(
                    item,
                    bot_player_id=bot_player_id,
                    bot_nickname=bot_nickname,
                    path=f"{path}[{idx}]",
                    allow_reveal_keys=allow_reveal_keys,
                )
            )
    elif isinstance(data, str):
        if bot_player_id and bot_player_id in data:
            findings.append(f"Bot player ID '{bot_player_id}' leaked in value at {path}")
        if not allow_reveal_keys and path.endswith(".nickname") and data == bot_nickname:
            findings.append(f"Bot nickname '{bot_nickname}' leaked at {path}")

    return findings


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_no_bot_leak_across_all_endpoints_and_pre_reveal_ws_frames() -> None:
    """Scan all REST responses and every pre-REVEAL WS frame for bot identity leaks."""
    http = Client()
    create_resp = await _db(
        lambda: http.post(
            "/api/rooms/",
            data=json.dumps(
                {
                    "nickname": "HostAlice",
                    "config": {
                        "min_humans": 3,
                        "rounds": 3,
                        "phase_durations": {"answer": 30, "chat": 60, "vote": 30, "reveal": 10},
                    },
                }
            ),
            content_type="application/json",
        )
    )
    assert create_resp.status_code == 201
    create_data = create_resp.json()
    assert scan_payload_for_leaks(create_data) == []

    code = create_data["code"]
    join_bob = await _db(
        lambda: http.post(
            f"/api/rooms/{code}/join/",
            data=json.dumps({"nickname": "PlayerBob"}),
            content_type="application/json",
        )
    )
    join_carol = await _db(
        lambda: http.post(
            f"/api/rooms/{code}/join/",
            data=json.dumps({"nickname": "PlayerCarol"}),
            content_type="application/json",
        )
    )
    assert join_bob.status_code == 200
    assert join_carol.status_code == 200
    assert scan_payload_for_leaks(join_bob.json()) == []
    assert scan_payload_for_leaks(join_carol.json()) == []

    tokens = [
        create_data["player_token"],
        join_bob.json()["player_token"],
        join_carol.json()["player_token"],
    ]
    comms = [
        WebsocketCommunicator(
            application,
            f"/ws/rooms/{code}/?token={token}",
            headers=ORIGIN_HEADER,
        )
        for token in tokens
    ]
    reconnected: WebsocketCommunicator | None = None

    try:
        pre_reveal_frames: list[dict[str, Any]] = []
        for idx, comm in enumerate(comms):
            assert (await comm.connect())[0]
            pre_reveal_frames.append(await comm.receive_json_from())  # room_snapshot
            for earlier in comms[:idx]:
                pre_reveal_frames.append(await earlier.receive_json_from())  # player_joined

        # Host starts game -> ANSWER phase
        await comms[0].send_json_to({"v": 1, "id": "sg", "type": "start_game", "payload": {}})
        my_seats: list[str] = []
        for c in comms:
            pre_reveal_frames.append(await c.receive_json_from())  # phase_changed(answer)
            snap = await c.receive_json_from()  # room_snapshot(answer)
            my_seats.append(snap["payload"]["my_seat_id"])
            pre_reveal_frames.append(snap)

        # Look up covert bot Player now that start_game created it
        bot_player = await _db(
            lambda: PlayerFactory._meta.model.objects.get(room__code=code, is_bot=True)
        )
        bot_player_id = str(bot_player.id)

        # Check REST GET /api/rooms/{code}/ during active game
        detail_resp = await _db(lambda: http.get(f"/api/rooms/{code}/"))
        assert detail_resp.status_code == 200
        assert (
            scan_payload_for_leaks(
                detail_resp.json(),
                bot_player_id=bot_player_id,
                bot_nickname=bot_player.nickname,
            )
            == []
        )

        # ANSWER submissions -> answers_revealed + phase_changed(chat)
        for idx, c in enumerate(comms):
            await c.send_json_to(
                {
                    "v": 1,
                    "id": f"ans{idx}",
                    "type": "submit_answer",
                    "payload": {"text": f"Human answer {idx}"},
                }
            )
        for c in comms:
            pre_reveal_frames.append(await c.receive_json_from())  # answers_revealed
            pre_reveal_frames.append(await c.receive_json_from())  # phase_changed(chat)

        # Human chat + typing + Stub bot chat during CHAT
        await comms[0].send_json_to(
            {"v": 1, "id": "typ", "type": "typing", "payload": {"is_typing": True}}
        )
        for peer in (comms[1], comms[2]):
            pre_reveal_frames.append(await peer.receive_json_from())  # typing

        await comms[0].send_json_to(
            {"v": 1, "id": "ch0", "type": "send_message", "payload": {"text": "Suspicious!"}}
        )
        for c in comms:
            pre_reveal_frames.append(await c.receive_json_from())  # human chat_message

        round_id = await _db(lambda: Round.objects.get(room__code=code, number=1).id)
        await database_sync_to_async(post_stub_chat_message)(round_id, rng=random.Random(12))
        for c in comms:
            pre_reveal_frames.append(await c.receive_json_from())  # stub bot chat_message

        # Ready to vote -> VOTE phase
        for idx, c in enumerate(comms):
            await c.send_json_to(
                {"v": 1, "id": f"rtv{idx}", "type": "ready_to_vote", "payload": {}}
            )
        for c in comms:
            pre_reveal_frames.append(await c.receive_json_from())  # phase_changed(vote)

        # Partial votes (2/3) -> vote_progress + mid-VOTE reconnect snapshot
        await comms[0].send_json_to(
            {"v": 1, "id": "v0", "type": "cast_vote", "payload": {"target_seat_id": my_seats[1]}}
        )
        for c in comms:
            pre_reveal_frames.append(await c.receive_json_from())  # vote_progress

        await comms[1].disconnect()
        reconnected = WebsocketCommunicator(
            application,
            f"/ws/rooms/{code}/?token={tokens[1]}",
            headers=ORIGIN_HEADER,
        )
        assert (await reconnected.connect())[0]
        vote_snap = await reconnected.receive_json_from()
        assert vote_snap["payload"]["phase"] == "vote"
        pre_reveal_frames.append(vote_snap)

        # Assert zero leaks across ALL collected pre-REVEAL frames
        assert len(pre_reveal_frames) >= 20
        for idx, frame in enumerate(pre_reveal_frames):
            leaks = scan_payload_for_leaks(
                frame,
                bot_player_id=bot_player_id,
                bot_nickname=bot_player.nickname,
                path=f"frame[{idx}]({frame.get('type')})",
            )
            assert leaks == [], f"Leaks detected: {leaks}"

        # Advance VOTE -> REVEAL and verify Message.meta still never leaks even during REVEAL
        reveal_res = await database_sync_to_async(advance_phase)(
            round_id, expected_phase=RoundPhase.VOTE
        )
        assert reveal_res is not None
        for env in reveal_res["envelopes"]:
            assert (
                scan_payload_for_leaks(
                    env,
                    bot_player_id=bot_player_id,
                    allow_reveal_keys=True,
                )
                == []
            )
    finally:
        for c in comms:
            await c.disconnect()
        if reconnected is not None:
            await reconnected.disconnect()
