"""Atomic Redis ZSET phase deadline scheduler and Postgres reconciliation."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import redis
from django.conf import settings

from apps.game.models import Round, RoundPhase

logger = logging.getLogger(__name__)

DEADLINES_KEY = "game:deadlines"
ACTIVE_SCHEDULED_PHASES: tuple[str, ...] = (
    RoundPhase.ANSWER,
    RoundPhase.CHAT,
    RoundPhase.VOTE,
    RoundPhase.REVEAL,
)


def make_deadline_member(round_id: UUID | str, phase: str) -> str:
    """Encode round ID and expected phase into a ZSET member key."""
    return f"{round_id}:{phase}"


def parse_deadline_member(member: str) -> tuple[UUID, str] | None:
    """Decode `round_id:phase` member key, returning None when malformed."""
    raw_id, sep, phase = member.partition(":")
    if not sep or phase not in ACTIVE_SCHEDULED_PHASES:
        return None
    try:
        return UUID(raw_id), phase
    except ValueError:
        return None


def _resolve_redis(redis_client: redis.Redis | None) -> tuple[redis.Redis | None, bool]:
    if redis_client is not None:
        return redis_client, False
    redis_url = getattr(settings, "REDIS_URL", "")
    if not redis_url:
        return None, False
    return redis.Redis.from_url(redis_url, decode_responses=True), True


def schedule_phase_deadline(
    round_id: UUID,
    phase: str,
    ends_at: datetime,
    *,
    redis_client: redis.Redis | None = None,
) -> bool:
    """Insert or update a round phase deadline in Redis ZSET `game:deadlines`."""
    if phase not in ACTIVE_SCHEDULED_PHASES:
        return False
    client, should_close = _resolve_redis(redis_client)
    if client is None:
        return False
    score_ms = int(ends_at.timestamp() * 1000)
    try:
        client.zadd(DEADLINES_KEY, {make_deadline_member(round_id, phase): score_ms})
        return True
    finally:
        if should_close:
            client.close()


def cancel_phase_deadline(
    round_id: UUID,
    phase: str,
    *,
    redis_client: redis.Redis | None = None,
) -> int:
    """Remove a pending phase deadline from `game:deadlines`."""
    client, should_close = _resolve_redis(redis_client)
    if client is None:
        return 0
    try:
        return int(client.zrem(DEADLINES_KEY, make_deadline_member(round_id, phase)))
    finally:
        if should_close:
            client.close()


def reconcile_active_deadlines(
    *,
    redis_client: redis.Redis | None = None,
) -> int:
    """Backfill active Postgres round deadlines into Redis ZSET `game:deadlines`."""
    client, should_close = _resolve_redis(redis_client)
    if client is None:
        return 0

    active_rounds = list(
        Round.objects.filter(phase__in=ACTIVE_SCHEDULED_PHASES).only(
            "id",
            "phase",
            "phase_ends_at",
        )
    )
    try:
        if not active_rounds:
            return 0
        mapping: dict[str, int] = {
            make_deadline_member(r.id, r.phase): int(r.phase_ends_at.timestamp() * 1000)
            for r in active_rounds
        }
        client.zadd(DEADLINES_KEY, mapping)
        return len(mapping)
    finally:
        if should_close:
            client.close()


def claim_due_deadlines(
    *,
    now_ms: int | None = None,
    batch_size: int = 50,
    redis_client: redis.Redis | None = None,
    on_claim: Any | None = None,
) -> int:
    """Claim due `game:deadlines` entries via atomic ZREM and execute transitions."""
    client, should_close = _resolve_redis(redis_client)
    if client is None:
        return 0

    cutoff_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    claimed_count = 0
    try:
        candidates = client.zrangebyscore(
            DEADLINES_KEY,
            "-inf",
            cutoff_ms,
            start=0,
            num=batch_size,
        )
        if not candidates:
            return 0

        from apps.game.state_machine import advance_phase

        tick_now = datetime.fromtimestamp(cutoff_ms / 1000, tz=UTC)
        transition_fn = on_claim or (
            lambda r_id, exp_phase: advance_phase(
                r_id,
                expected_phase=exp_phase,
                reason="timeout",
                clock=(lambda: tick_now) if now_ms is not None else None,
            )
        )

        for member in candidates:
            if int(client.zrem(DEADLINES_KEY, member)) != 1:
                continue
            parsed = parse_deadline_member(str(member))
            if parsed is None:
                logger.warning("Ignoring malformed deadline member: %s", member)
                continue
            round_id, expected_phase = parsed
            try:
                transition_fn(round_id, expected_phase)
            except Exception:
                logger.exception(
                    "Failed executing claimed deadline round=%s phase=%s",
                    round_id,
                    expected_phase,
                )
            claimed_count += 1
        return claimed_count
    finally:
        if should_close:
            client.close()
