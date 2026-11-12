"""Tests for atomic Redis ZSET scheduler claim, contention, and Postgres recovery."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from django.core.management import call_command

from apps.common.redis import get_redis_client
from apps.game.models import Round, RoundPhase
from apps.game.scheduler import (
    DEADLINES_KEY,
    claim_due_deadlines,
    make_deadline_member,
    reconcile_active_deadlines,
    schedule_phase_deadline,
)
from apps.game.state_machine import start_game
from tests.rooms.factories import PlayerFactory, RoomFactory


@pytest.fixture(autouse=True)
def reset_deadlines_zset() -> None:
    """Ensure game:deadlines starts and ends clean for every test."""
    client = get_redis_client()
    client.delete(DEADLINES_KEY)
    yield
    client.delete(DEADLINES_KEY)
    client.close()


@pytest.mark.django_db(transaction=True)
def test_scheduler_claims_only_due_deadlines_atomically() -> None:
    """Due entries are claimed at most once via ZREM; future deadlines stay queued."""
    base_time = datetime(2026, 11, 12, 14, 0, 0, tzinfo=UTC)
    room = RoomFactory(
        config={
            "rounds": 3,
            "phase_durations": {"answer": 20, "chat": 90, "vote": 30, "reveal": 10},
            "min_humans": 3,
            "allow_replay_use": False,
        }
    )
    host = PlayerFactory(room=room, nickname="Alice", is_host=True, connected=True)
    PlayerFactory(room=room, nickname="Bob", connected=True)
    PlayerFactory(room=room, nickname="Carol", connected=True)

    start_game(room.id, host.id, clock=lambda: base_time, rng=random.Random(9))
    round_obj = Round.objects.get(room=room, number=1)

    # Before deadline -> 0 claims
    before_ms = int((base_time + timedelta(seconds=19)).timestamp() * 1000)
    assert claim_due_deadlines(now_ms=before_ms) == 0
    round_obj.refresh_from_db()
    assert round_obj.phase == RoundPhase.ANSWER

    # At/after deadline -> claimed once and moved to CHAT + queued :chat
    due_ms = int((base_time + timedelta(seconds=21)).timestamp() * 1000)
    assert claim_due_deadlines(now_ms=due_ms) == 1
    round_obj.refresh_from_db()
    assert round_obj.phase == RoundPhase.CHAT

    # Second immediate poll sees nothing due (:chat is at +90s)
    assert claim_due_deadlines(now_ms=due_ms) == 0


@pytest.mark.django_db
def test_scheduler_skips_if_zrem_loses_race_and_recovers_after_flush() -> None:
    """Simulate losing atomic ZREM race, then verify Postgres->Redis reconciliation."""
    base_time = datetime(2026, 11, 12, 15, 0, 0, tzinfo=UTC)
    room = RoomFactory()
    host = PlayerFactory(room=room, nickname="Host", is_host=True, connected=True)
    PlayerFactory(room=room, nickname="Bob", connected=True)
    PlayerFactory(room=room, nickname="Carol", connected=True)
    PlayerFactory(room=room, nickname="Dana", connected=True)

    start_game(room.id, host.id, clock=lambda: base_time, rng=random.Random(11))
    round_obj = Round.objects.get(room=room, number=1)

    redis_client = get_redis_client()
    member = make_deadline_member(round_obj.id, RoundPhase.ANSWER)
    schedule_phase_deadline(round_obj.id, RoundPhase.ANSWER, base_time + timedelta(seconds=45))

    # Wipe Redis ZSET completely (simulating Redis restart/eviction)
    redis_client.delete(DEADLINES_KEY)
    assert redis_client.zcard(DEADLINES_KEY) == 0

    # Reconcile recovers active round deadline from Postgres
    recovered = reconcile_active_deadlines(redis_client=redis_client)
    assert recovered >= 1
    assert redis_client.zscore(DEADLINES_KEY, member) is not None

    # Inject an already-consumed member check where another worker raced first
    calls: list[tuple[UUID, str]] = []

    class RacingRedis:
        def zrangebyscore(self, *args: object, **kwargs: object) -> list[str]:
            return [member]

        def zrem(self, *args: object, **kwargs: object) -> int:
            return 0  # lost race to another scheduler process

    claimed = claim_due_deadlines(
        now_ms=int((base_time + timedelta(seconds=60)).timestamp() * 1000),
        redis_client=RacingRedis(),  # type: ignore[arg-type]
        on_claim=lambda r_id, phase: calls.append((r_id, phase)),
    )
    assert claimed == 0
    assert calls == []
    redis_client.close()


@pytest.mark.django_db(transaction=True)
def test_run_scheduler_once_command_advances_expired_round() -> None:
    """manage.py run_scheduler --once reconciles DB rounds and advances expired phase."""
    past = datetime.now(UTC) - timedelta(seconds=100)
    room = RoomFactory(
        config={
            "rounds": 3,
            "phase_durations": {"answer": 10, "chat": 60, "vote": 30, "reveal": 10},
            "min_humans": 3,
            "allow_replay_use": False,
        }
    )
    host = PlayerFactory(room=room, nickname="Alice", is_host=True, connected=True)
    PlayerFactory(room=room, nickname="Bob", connected=True)
    PlayerFactory(room=room, nickname="Carol", connected=True)

    start_game(room.id, host.id, clock=lambda: past, rng=random.Random(3))
    round_obj = Round.objects.get(room=room, number=1)
    assert round_obj.phase == RoundPhase.ANSWER

    # Even if Redis missed the entry, --once reconciles first and claims it
    client = get_redis_client()
    client.delete(DEADLINES_KEY)
    client.close()

    call_command("run_scheduler", "--once")

    round_obj.refresh_from_db()
    assert round_obj.phase == RoundPhase.CHAT

