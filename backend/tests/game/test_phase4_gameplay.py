"""Phase 4 unit & WS tests: voting, constraints, +100 scoring, 3-round loop, play_again."""

from __future__ import annotations

import asyncio
import json
import random
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta

import pytest
from channels.db import database_sync_to_async
from channels.layers import channel_layers
from channels.testing import WebsocketCommunicator
from django.db import IntegrityError, connections, transaction

from apps.bot.stub import pick_stub_answer, pick_stub_chat_message, post_stub_chat_message
from apps.common.redis import get_redis_client
from apps.game.models import Message, MessageKind, Round, RoundPhase, RoundResult, Vote
from apps.game.presence import presence_manager
from apps.game.scheduler import DEADLINES_KEY
from apps.game.state_machine import (
    GameTransitionError,
    advance_phase,
    build_room_snapshot_payload,
    cast_vote,
    mark_ready_to_vote,
    play_again,
    start_game,
    submit_answer,
)
from apps.rooms.models import RoomStatus
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


def _clear_redis_keys() -> None:
    client = get_redis_client()
    client.delete(DEADLINES_KEY)
    for prefix in ("stb:rl:*", "stb:lock:*"):
        keys = list(client.scan_iter(match=prefix))
        if keys:
            client.delete(*keys)
    client.close()


@pytest.fixture
def clean_redis() -> AsyncIterator[None]:
    """Ensure Redis keys are cleared before and after sync tests."""
    _clear_redis_keys()
    yield
    _clear_redis_keys()


@pytest.mark.django_db(transaction=True)
def test_vote_db_constraints_reject_self_vote_and_double_vote(clean_redis: None) -> None:
    """Postgres CheckConstraint & UniqueConstraint reject self-vote and double-vote."""
    now = datetime(2026, 11, 12, 14, 0, 0, tzinfo=UTC)
    clock = lambda: now  # noqa: E731
    rng = random.Random(42)

    room = RoomFactory(
        config={
            "rounds": 3,
            "phase_durations": {"answer": 30, "chat": 60, "vote": 30, "reveal": 10},
            "min_humans": 3,
            "allow_replay_use": False,
        }
    )
    host = PlayerFactory(room=room, nickname="Alice", is_host=True, connected=True)
    bob = PlayerFactory(room=room, nickname="Bob", connected=True)
    carol = PlayerFactory(room=room, nickname="Carol", connected=True)

    start_game(room.id, host.id, clock=clock, rng=rng)
    round_obj = Round.objects.get(room=room, number=1)
    advance_phase(round_obj.id, expected_phase=RoundPhase.ANSWER, clock=clock, rng=rng)
    advance_phase(round_obj.id, expected_phase=RoundPhase.CHAT, clock=clock, rng=rng)

    alice_seat = round_obj.seats.get(player=host)
    bob_seat = round_obj.seats.get(player=bob)
    carol_seat = round_obj.seats.get(player=carol)

    # Domain errors via cast_vote
    with pytest.raises(GameTransitionError) as exc_self:
        cast_vote(room.id, host.id, str(alice_seat.id), clock=clock)
    assert exc_self.value.code == "self_vote"

    with pytest.raises(GameTransitionError) as exc_bad:
        cast_vote(room.id, host.id, "not-a-uuid", clock=clock)
    assert exc_bad.value.code == "invalid_target"

    # Direct DB constraint: self-vote rejected by prevent_self_vote CheckConstraint
    with pytest.raises(IntegrityError), transaction.atomic():
        Vote.objects.create(round=round_obj, voter_seat=alice_seat, target_seat=alice_seat)

    # Valid vote succeeds
    res = cast_vote(room.id, host.id, str(bob_seat.id), clock=clock)
    assert res["votes_cast"] == 1
    assert res["all_voted"] is False

    # Domain double-vote rejected
    with pytest.raises(GameTransitionError) as exc_dup:
        cast_vote(room.id, host.id, str(carol_seat.id), clock=clock)
    assert exc_dup.value.code == "already_voted"

    # Direct DB constraint: double-vote rejected by unique_vote_per_voter_per_round
    with pytest.raises(IntegrityError), transaction.atomic():
        Vote.objects.create(round=round_obj, voter_seat=alice_seat, target_seat=carol_seat)


@pytest.mark.django_db(transaction=True)
def test_full_three_round_game_scoring_and_play_again(clean_redis: None) -> None:
    """Complete 3-round game -> +100 scoring -> RoundResult -> DONE -> play_again Game 2."""
    now_holder = [datetime(2026, 11, 12, 15, 0, 0, tzinfo=UTC)]
    clock = lambda: now_holder[0]  # noqa: E731
    rng = random.Random(2026)

    room = RoomFactory(
        config={
            "rounds": 3,
            "phase_durations": {"answer": 30, "chat": 60, "vote": 30, "reveal": 10},
            "min_humans": 3,
            "allow_replay_use": False,
        }
    )
    host = PlayerFactory(room=room, nickname="Alice", is_host=True, connected=True)
    bob = PlayerFactory(room=room, nickname="Bob", connected=True)
    carol = PlayerFactory(room=room, nickname="Carol", connected=True)

    start_game(room.id, host.id, clock=clock, rng=rng)
    seen_topic_ids: list[int] = []
    seen_alias_sets: list[list[str]] = []

    for expected_round_num in (1, 2, 3):
        round_obj = Round.objects.get(room=room, game_index=1, number=expected_round_num)
        seen_topic_ids.append(round_obj.topic_id)
        seen_alias_sets.append(
            list(round_obj.seats.order_by("order_index").values_list("alias", flat=True))
        )
        assert round_obj.phase == RoundPhase.ANSWER

        submit_answer(room.id, host.id, f"Human A r{expected_round_num}", clock=clock, rng=rng)
        submit_answer(room.id, bob.id, f"Human B r{expected_round_num}", clock=clock, rng=rng)
        res_ans = submit_answer(
            room.id, carol.id, f"Human C r{expected_round_num}", clock=clock, rng=rng
        )
        assert res_ans["all_answered"] is True

        round_obj.refresh_from_db()
        assert round_obj.phase == RoundPhase.CHAT
        assert post_stub_chat_message(round_obj.id, rng=rng) is not None

        mark_ready_to_vote(room.id, host.id, clock=clock, rng=rng)
        mark_ready_to_vote(room.id, bob.id, clock=clock, rng=rng)
        assert mark_ready_to_vote(room.id, carol.id, clock=clock, rng=rng) is True

        round_obj.refresh_from_db()
        assert round_obj.phase == RoundPhase.VOTE

        bot_seat = round_obj.seats.get(player__is_bot=True)
        alice_seat = round_obj.seats.get(player=host)
        bob_seat = round_obj.seats.get(player=bob)

        # Round 1: only Alice spots bot (1/3 -> bot_fooled=True)
        # Round 2 & 3: Alice + Bob spot bot (2/3 -> bot_fooled=False)
        cast_vote(room.id, host.id, str(bot_seat.id), clock=clock, rng=rng)
        if expected_round_num == 1:
            cast_vote(room.id, bob.id, str(alice_seat.id), clock=clock, rng=rng)
            last_vote = cast_vote(room.id, carol.id, str(bob_seat.id), clock=clock, rng=rng)
        else:
            cast_vote(room.id, bob.id, str(bot_seat.id), clock=clock, rng=rng)
            last_vote = cast_vote(room.id, carol.id, str(alice_seat.id), clock=clock, rng=rng)

        assert last_vote["all_voted"] is True
        round_obj.refresh_from_db()
        assert round_obj.phase == RoundPhase.REVEAL

        result = RoundResult.objects.get(round=round_obj)
        assert result.human_voters == 3
        if expected_round_num == 1:
            assert result.votes_for_bot == 1
            assert result.bot_fooled is True
        else:
            assert result.votes_for_bot == 2
            assert result.bot_fooled is False

        # Snapshot during REVEAL contains reveal payload + updated roster scores
        _, snap = build_room_snapshot_payload(room.id, host.id)
        assert snap["phase"] == "reveal"
        assert snap["reveal"]["bot_seat_id"] == str(bot_seat.id)

        # Advance past REVEAL
        now_holder[0] += timedelta(seconds=12)
        adv = advance_phase(round_obj.id, expected_phase=RoundPhase.REVEAL, clock=clock, rng=rng)
        assert adv is not None
        if expected_round_num < 3:
            assert adv["new_phase"] == RoundPhase.ANSWER
        else:
            assert adv["new_phase"] == RoundPhase.DONE
            assert [e["type"] for e in adv["envelopes"]] == ["phase_changed", "game_over"]

    # 3 distinct topics, distinct alias shuffles & cumulative scores (+100 per bot catch)
    assert len(set(seen_topic_ids)) == 3
    assert len({tuple(aliases) for aliases in seen_alias_sets}) == 3
    host.refresh_from_db()
    bob.refresh_from_db()
    carol.refresh_from_db()
    assert host.score == 300
    assert bob.score == 200
    assert carol.score == 0

    room.refresh_from_db()
    assert room.status == RoomStatus.FINISHED

    # Snapshot during DONE includes game_over
    _, done_snap = build_room_snapshot_payload(room.id, host.id)
    assert done_snap["phase"] == "done"
    assert done_snap["game_over"]["bot_fooled_count"] == 1
    assert done_snap["game_over"]["total_rounds"] == 3
    assert done_snap["game_over"]["leaderboard"][0]["nickname"] == "Alice"
    assert done_snap["game_over"]["leaderboard"][0]["score"] == 300

    # Non-host cannot trigger play_again
    with pytest.raises(GameTransitionError) as exc_non_host:
        play_again(room.id, bob.id, clock=clock)
    assert exc_non_host.value.code == "not_host"

    # Host triggers play_again -> LOBBY with scores reset, Game 1 history preserved
    play_again_env = play_again(room.id, host.id, clock=clock)
    assert play_again_env["type"] == "phase_changed"
    assert play_again_env["payload"]["phase"] == "lobby"

    room.refresh_from_db()
    assert room.status == RoomStatus.LOBBY
    host.refresh_from_db()
    bob.refresh_from_db()
    assert host.score == 0
    assert bob.score == 0
    assert Round.objects.filter(room=room, game_index=1).count() == 3

    # Start Game 2 cleanly
    start_game(room.id, host.id, clock=clock, rng=rng)
    assert Round.objects.filter(room=room, game_index=2, number=1).exists()


@pytest.mark.django_db(transaction=True)
def test_stub_bot_determinism_and_phase_guard(clean_redis: None) -> None:
    """Stub bot selects deterministically and only posts chat during active CHAT phase."""
    a1 = pick_stub_answer(rng=random.Random(99))
    a2 = pick_stub_answer(rng=random.Random(99))
    c1 = pick_stub_chat_message(rng=random.Random(99))
    c2 = pick_stub_chat_message(rng=random.Random(99))
    assert a1 == a2
    assert c1 == c2

    now = datetime(2026, 11, 12, 16, 0, 0, tzinfo=UTC)
    clock = lambda: now  # noqa: E731
    room = RoomFactory(
        config={
            "rounds": 3,
            "phase_durations": {"answer": 30, "chat": 60, "vote": 30, "reveal": 10},
            "min_humans": 3,
            "allow_replay_use": False,
        }
    )
    host = PlayerFactory(room=room, nickname="Alice", is_host=True, connected=True)
    PlayerFactory(room=room, nickname="Bob", connected=True)
    PlayerFactory(room=room, nickname="Carol", connected=True)
    start_game(room.id, host.id, clock=clock, rng=random.Random(5))
    round_obj = Round.objects.get(room=room, number=1)

    # Guarded during ANSWER phase
    assert post_stub_chat_message(round_obj.id, rng=random.Random(5)) is None
    assert Message.objects.filter(round=round_obj, kind=MessageKind.CHAT).count() == 0

    # Allowed during CHAT phase and hides meta
    advance_phase(round_obj.id, expected_phase=RoundPhase.ANSWER, clock=clock, rng=random.Random(5))
    env = post_stub_chat_message(round_obj.id, rng=random.Random(5))
    assert env is not None
    assert env["type"] == "chat_message"
    assert "meta" not in env["payload"]
    assert "is_bot" not in json.dumps(env)


@pytest.mark.asyncio
@pytest.mark.django_db(transaction=True)
async def test_ws_vote_reveal_game_over_and_play_again() -> None:
    """Multi-client WebSocket flow across VOTE -> REVEAL -> DONE -> play_again."""
    await presence_manager.reset_all()
    for alias in list(channel_layers.backends.keys()):
        layer = channel_layers.backends.pop(alias)
        flush = getattr(layer, "flush", None)
        if flush is not None:
            await flush()
    await asyncio.to_thread(_clear_redis_keys)

    room = await _db(
        lambda: RoomFactory(
            config={
                "rounds": 1,
                "phase_durations": {"answer": 30, "chat": 60, "vote": 30, "reveal": 10},
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
    comms = [
        WebsocketCommunicator(
            application,
            f"/ws/rooms/{room.code}/?token={sign_player_token(p.id, room.code)}",
            headers=ORIGIN_HEADER,
        )
        for p in players
    ]

    try:
        for idx, comm in enumerate(comms):
            assert (await comm.connect())[0]
            await comm.receive_json_from()
            for earlier in comms[:idx]:
                await earlier.receive_json_from()

        await comms[0].send_json_to({"v": 1, "id": "s1", "type": "start_game", "payload": {}})
        my_seats: list[str] = []
        seats_list: list[dict[str, object]] = []
        for c in comms:
            await c.receive_json_from()  # phase_changed(answer)
            snap = await c.receive_json_from()  # room_snapshot
            my_seats.append(snap["payload"]["my_seat_id"])
            seats_list = snap["payload"]["seats"]

        for idx, c in enumerate(comms):
            await c.send_json_to(
                {
                    "v": 1,
                    "id": f"a{idx}",
                    "type": "submit_answer",
                    "payload": {"text": f"Ans {idx}"},
                }
            )
        for c in comms:
            await c.receive_json_from()  # answers_revealed
            await c.receive_json_from()  # phase_changed(chat)

        for idx, c in enumerate(comms):
            await c.send_json_to({"v": 1, "id": f"r{idx}", "type": "ready_to_vote", "payload": {}})
        for c in comms:
            ev = await c.receive_json_from()
            assert ev["type"] == "phase_changed"
            assert ev["payload"]["phase"] == "vote"

        bot_seat_id = await _db(
            lambda: str(Round.objects.get(room=room, number=1).seats.get(player__is_bot=True).id)
        )
        assert any(s["seat_id"] == bot_seat_id for s in seats_list)

        # All 3 humans vote for the bot via WebSocket
        for idx, c in enumerate(comms):
            await c.send_json_to(
                {
                    "v": 1,
                    "id": f"v{idx}",
                    "type": "cast_vote",
                    "payload": {"target_seat_id": bot_seat_id},
                }
            )
            for peer in comms:
                vp = await peer.receive_json_from()
                assert vp["type"] == "vote_progress"

        for c in comms:
            rev = await c.receive_json_from()
            assert rev["type"] == "reveal"
            assert rev["payload"]["bot_seat_id"] == bot_seat_id
            assert rev["payload"]["votes_for_bot"] == 3
            assert rev["payload"]["bot_fooled"] is False
            ph = await c.receive_json_from()
            assert ph["type"] == "phase_changed"
            assert ph["payload"]["phase"] == "reveal"

        # Advance REVEAL -> DONE & game_over
        round_id = await _db(lambda: Round.objects.get(room=room, number=1).id)
        await database_sync_to_async(advance_phase)(round_id, expected_phase=RoundPhase.REVEAL)
        for c in comms:
            ph_done = await c.receive_json_from()
            assert ph_done["type"] == "phase_changed"
            assert ph_done["payload"]["phase"] == "done"
            ev_over = await c.receive_json_from()
            assert ev_over["type"] == "game_over"
            assert ev_over["payload"]["leaderboard"][0]["score"] == 100

        # Host sends play_again -> all tabs return to lobby
        await comms[0].send_json_to({"v": 1, "id": "pa1", "type": "play_again", "payload": {}})
        for c in comms:
            ev_lobby = await c.receive_json_from()
            assert ev_lobby["type"] == "phase_changed"
            assert ev_lobby["payload"]["phase"] == "lobby"
            snap_lobby = await c.receive_json_from()
            assert snap_lobby["type"] == "room_snapshot"
            assert snap_lobby["payload"]["phase"] == "lobby"
            assert all(p["score"] == 0 for p in snap_lobby["payload"]["roster"])
    finally:
        for c in comms:
            await c.disconnect()
        await presence_manager.reset_all()
        await asyncio.to_thread(_clear_redis_keys)
        await database_sync_to_async(connections.close_all)()
