"""Unit tests for the Phase 3 game state machine with injected clock and RNG."""

from __future__ import annotations

import json
import random
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from apps.common.models import Event
from apps.common.redis import get_redis_client
from apps.game.models import Message, MessageKind, Round, RoundPhase
from apps.game.scheduler import DEADLINES_KEY, make_deadline_member
from apps.game.state_machine import (
    GameTransitionError,
    advance_phase,
    build_room_snapshot_payload,
    mark_ready_to_vote,
    send_chat_message,
    start_game,
    submit_answer,
)
from apps.rooms.models import RoomStatus
from tests.rooms.factories import PlayerFactory, RoomFactory


def _clear_game_redis_keys() -> None:
    client = get_redis_client()
    client.delete(DEADLINES_KEY)
    for prefix in ("stb:rl:*", "stb:lock:*"):
        keys = list(client.scan_iter(match=prefix))
        if keys:
            client.delete(*keys)
    client.close()


@pytest.fixture(autouse=True)
def clean_redis_game_keys() -> Iterator[None]:
    """Remove deadline, lock, and rate-limit Redis keys around unit tests."""
    _clear_game_redis_keys()
    yield
    _clear_game_redis_keys()


@pytest.mark.django_db(transaction=True)
def test_state_machine_full_answer_chat_transitions_with_injected_clock() -> None:
    """start_game -> submit_answer -> ANSWER->CHAT->VOTE->DONE with deterministic timestamps."""
    base_time = datetime(2026, 11, 12, 12, 0, 0, tzinfo=UTC)
    now_holder = [base_time]
    clock = lambda: now_holder[0]  # noqa: E731
    rng = random.Random(101)

    room = RoomFactory(
        config={
            "rounds": 3,
            "phase_durations": {"answer": 45, "chat": 120, "vote": 30, "reveal": 12},
            "min_humans": 3,
            "allow_replay_use": False,
        }
    )
    host = PlayerFactory(room=room, nickname="Alice", is_host=True, connected=True)
    bob = PlayerFactory(room=room, nickname="Bob", connected=True)
    carol = PlayerFactory(room=room, nickname="Carol", connected=True)

    # Non-host cannot start
    with pytest.raises(GameTransitionError, match="host"):
        start_game(room.id, bob.id, clock=clock, rng=rng)

    env = start_game(room.id, host.id, clock=clock, rng=rng)
    assert env["type"] == "phase_changed"
    assert env["payload"]["phase"] == "answer"
    assert env["payload"]["round_number"] == 1
    assert env["payload"]["ends_at"] == int((base_time + timedelta(seconds=45)).timestamp() * 1000)
    assert len(env["payload"]["seats"]) == 4  # 3 humans + 1 covert bot
    assert "is_bot" not in json.dumps(env)
    assert "my_seat_id" not in env["payload"]

    room.refresh_from_db()
    assert room.status == RoomStatus.IN_PROGRESS
    round_obj = Round.objects.get(room=room, number=1)
    assert round_obj.phase == RoundPhase.ANSWER

    # Snapshot includes recipient my_seat_id without revealing other player IDs or bot
    _, host_snap = build_room_snapshot_payload(room.id, host.id)
    assert host_snap["phase"] == "answer"
    assert host_snap["my_seat_id"] is not None
    assert host_snap["has_answered"] is False
    assert "is_bot" not in json.dumps(host_snap)

    # Control chars stripped; empty & >280 rejected; duplicate rejected
    with pytest.raises(GameTransitionError) as exc_empty:
        submit_answer(room.id, host.id, "\n\t  ", clock=clock)
    assert exc_empty.value.code == "empty_text"

    with pytest.raises(GameTransitionError) as exc_long:
        submit_answer(room.id, host.id, "a" * 281, clock=clock)
    assert exc_long.value.code == "text_too_long"

    res_h = submit_answer(room.id, host.id, "Pineapples\nbelong elsewhere\x00", clock=clock)
    assert res_h["all_answered"] is False

    with pytest.raises(GameTransitionError) as exc_dup:
        submit_answer(room.id, host.id, "Second answer", clock=clock)
    assert exc_dup.value.code == "already_answered"

    # Submitting remaining humans triggers early transition ANSWER -> CHAT including bot answer
    now_holder[0] = base_time + timedelta(seconds=10)
    submit_answer(room.id, bob.id, "Honestly iced coffee in winter", clock=clock, rng=rng)
    res_c = submit_answer(room.id, carol.id, "Voice notes need captions", clock=clock, rng=rng)
    assert res_c["all_answered"] is True

    round_obj.refresh_from_db()
    assert round_obj.phase == RoundPhase.CHAT
    assert round_obj.phase_ends_at == now_holder[0] + timedelta(seconds=120)
    assert Message.objects.filter(round=round_obj, kind=MessageKind.ANSWER).count() == 4

    # Chat messaging + client_msg_id deduplication
    client_msg_uuid = str(uuid4())
    chat_env1 = send_chat_message(
        room.id,
        host.id,
        "No way Coral Duck actually believes that",
        client_msg_id=client_msg_uuid,
        bypass_rate_limit=True,
    )
    chat_env2 = send_chat_message(
        room.id,
        host.id,
        "No way Coral Duck actually believes that",
        client_msg_id=client_msg_uuid,
        bypass_rate_limit=True,
    )
    assert chat_env1["seq"] == 4
    assert chat_env2["seq"] is None
    assert Message.objects.filter(round=round_obj, kind=MessageKind.CHAT).count() == 1

    # Ready-to-vote by all humans transitions CHAT -> VOTE
    now_holder[0] = base_time + timedelta(seconds=50)
    assert mark_ready_to_vote(room.id, host.id, clock=clock) is False
    assert mark_ready_to_vote(room.id, bob.id, clock=clock) is False
    assert mark_ready_to_vote(room.id, carol.id, clock=clock) is True

    round_obj.refresh_from_db()
    assert round_obj.phase == RoundPhase.VOTE

    # Advancing VOTE reaches Phase 3 DONE stub cleanly
    now_holder[0] = base_time + timedelta(seconds=80)
    done_res = advance_phase(round_obj.id, expected_phase=RoundPhase.VOTE, clock=clock)
    assert done_res is not None
    assert done_res["new_phase"] == RoundPhase.DONE
    room.refresh_from_db()
    assert room.status == RoomStatus.FINISHED


@pytest.mark.django_db(transaction=True)
def test_advance_phase_double_delivery_is_idempotent() -> None:
    """Delivering the same ANSWER->CHAT deadline twice only transitions and logs once."""
    now = datetime(2026, 11, 12, 13, 0, 0, tzinfo=UTC)
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

    start_game(room.id, host.id, clock=clock, rng=random.Random(7))
    round_obj = Round.objects.get(room=room, number=1)

    first = advance_phase(
        round_obj.id,
        expected_phase=RoundPhase.ANSWER,
        reason="timeout",
        clock=clock,
    )
    assert first is not None
    assert first["new_phase"] == RoundPhase.CHAT
    seqs_after_first = list(Event.objects.filter(room=room).values_list("seq", flat=True))
    assert seqs_after_first == [1, 2, 3]  # phase(answer), answers_revealed, phase(chat)

    # Duplicate delivery with stale expected_phase=ANSWER must no-op cleanly
    second = advance_phase(
        round_obj.id,
        expected_phase=RoundPhase.ANSWER,
        reason="duplicate_timeout",
        clock=clock,
    )
    assert second is None
    assert list(Event.objects.filter(room=room).values_list("seq", flat=True)) == [1, 2, 3]

    # Redis deadline moved from :answer to :chat
    redis_client = get_redis_client()
    assert redis_client.zscore(DEADLINES_KEY, make_deadline_member(round_obj.id, "answer")) is None
    assert (
        redis_client.zscore(DEADLINES_KEY, make_deadline_member(round_obj.id, "chat")) is not None
    )
    redis_client.close()
