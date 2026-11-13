"""Celery tasks for room lifecycle, maintenance, and abandoned room cleanup."""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta

from celery import shared_task
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.common.events import append_event
from apps.game.scheduler import cancel_phase_deadline
from apps.rooms.models import Room, RoomStatus


def cleanup_abandoned_rooms(
    timeout_seconds: int = 120,
    *,
    now: datetime | None = None,
) -> list[str]:
    """Find empty rooms (no connected humans for >= timeout_seconds) and transition to ABANDONED.

    Returns the list of room codes that were abandoned.
    """
    current_time = now or timezone.now()
    cutoff = current_time - timedelta(seconds=timeout_seconds)
    abandoned_codes: list[str] = []

    candidates = Room.objects.filter(status__in=[RoomStatus.LOBBY, RoomStatus.IN_PROGRESS])

    for room in candidates:
        with transaction.atomic():
            locked_room = (
                Room.objects.select_for_update()
                .filter(id=room.id, status__in=[RoomStatus.LOBBY, RoomStatus.IN_PROGRESS])
                .first()
            )
            if locked_room is None:
                continue

            # Check if any human is currently connected
            connected_humans = locked_room.players.filter(is_bot=False, connected=True).count()
            if connected_humans > 0:
                continue

            # Determine when the room became empty:
            # 1. Most recent last_seen_at among humans in this room
            # 2. Or room.created_at if no human ever had last_seen_at recorded
            most_recent_seen: datetime | None = (
                locked_room.players.filter(is_bot=False)
                .aggregate(latest=Max("last_seen_at"))
                .get("latest")
            )
            empty_since = most_recent_seen or locked_room.created_at

            if empty_since <= cutoff:
                locked_room.status = RoomStatus.ABANDONED
                locked_room.save(update_fields=["status"])
                append_event(
                    locked_room.id,
                    "room_abandoned",
                    {
                        "reason": "empty_timeout",
                        "empty_seconds": timeout_seconds,
                    },
                )
                abandoned_codes.append(locked_room.code)

                # If the room was in progress, cancel any pending scheduled phase deadline
                latest_round = locked_room.rounds.order_by("-game_index", "-number").first()
                if latest_round is not None:
                    with contextlib.suppress(Exception):
                        cancel_phase_deadline(latest_round.id, latest_round.phase)

    return abandoned_codes


@shared_task(name="apps.rooms.tasks.cleanup_abandoned_rooms_task")
def cleanup_abandoned_rooms_task(timeout_seconds: int = 120) -> list[str]:
    """Periodic Celery beat task to clean up empty abandoned rooms."""
    return cleanup_abandoned_rooms(timeout_seconds=timeout_seconds)
