"""Append-only Event log writer and WebSocket protocol envelope helpers."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from django.db import transaction

from apps.common.models import Event
from apps.rooms.models import Room

PROTOCOL_VERSION = 1


def utc_now_ms() -> int:
    """Return current UTC epoch timestamp in milliseconds."""
    return int(time.time() * 1000)


def build_envelope(
    event_type: str,
    payload: dict[str, Any],
    *,
    seq: int | None = None,
) -> dict[str, Any]:
    """Construct a standard v1 WebSocket server-to-client envelope."""
    return {
        "v": PROTOCOL_VERSION,
        "seq": seq,
        "type": event_type,
        "payload": payload,
    }


def append_event(
    room_id: UUID,
    event_type: str,
    payload: dict[str, Any],
) -> Event:
    """Atomically increment Room.last_seq and append a persistent Event row."""
    with transaction.atomic():
        room = Room.objects.select_for_update().get(id=room_id)
        next_seq = room.last_seq + 1
        room.last_seq = next_seq
        room.save(update_fields=["last_seq"])
        return Event.objects.create(
            room=room,
            seq=next_seq,
            type=event_type,
            payload=payload,
        )
