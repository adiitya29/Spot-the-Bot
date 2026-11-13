"""Celery tasks and dispatch workers for bot timing, typing indicators, and replies."""

from __future__ import annotations

import contextlib
from typing import Any
from uuid import UUID, uuid4

from asgiref.sync import async_to_sync
from celery import shared_task
from channels.layers import get_channel_layer
from django.db import transaction

from apps.bot.engine import generate_bot_chat_reply
from apps.common.events import append_event, build_envelope
from apps.common.locks import room_lock
from apps.game.models import Message, MessageKind, Round, RoundPhase, RoundSeat
from apps.rooms.models import Room, RoomStatus


def _send_room_ws(room_code: str, envelope: dict[str, Any]) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    with contextlib.suppress(Exception):
        async_to_sync(layer.group_send)(
            f"room_{room_code}",
            {
                "type": "room.event",
                "sender_channel": "",
                "envelope": envelope,
            },
        )


@shared_task(name="apps.bot.tasks.bot_send_typing")
def bot_send_typing(room_id_str: str, seat_id_str: str, is_typing: bool) -> None:
    """Send ephemeral typing indicator for the bot over WebSocket (no DB event)."""
    room = Room.objects.filter(id=UUID(room_id_str)).first()
    if room is None:
        return
    envelope = build_envelope(
        "typing",
        {"seat_id": seat_id_str, "is_typing": is_typing},
        seq=None,
    )
    _send_room_ws(room.code, envelope)


@shared_task(name="apps.bot.tasks.bot_send_chat_message")
def bot_send_chat_message(
    room_id_str: str,
    round_id_str: str,
    seat_id_str: str,
    text: str,
) -> dict[str, Any] | None:
    """Post bot message if the round is actively in CHAT phase."""
    room_id = UUID(room_id_str)
    round_id = UUID(round_id_str)
    seat_id = UUID(seat_id_str)

    with room_lock(room_id), transaction.atomic():
        room = Room.objects.select_for_update().filter(id=room_id).first()
        round_obj = Round.objects.select_for_update().filter(id=round_id, room=room).first()
        if (
            room is None
            or round_obj is None
            or room.status != RoomStatus.IN_PROGRESS
            or round_obj.phase != RoundPhase.CHAT
        ):
            return None

        bot_seat = RoundSeat.objects.filter(id=seat_id, round=round_obj).first()
        if bot_seat is None:
            return None

        msg = Message.objects.create(
            round=round_obj,
            seat=bot_seat,
            text=text,
            kind=MessageKind.CHAT,
            client_msg_id=uuid4(),
            meta={"source": "bot_engine_v1"},
        )
        payload = {
            "id": msg.id,
            "round_id": str(round_obj.id),
            "seat_id": str(bot_seat.id),
            "alias": bot_seat.alias,
            "color_index": bot_seat.color_index,
            "text": msg.text,
            "client_msg_id": str(msg.client_msg_id),
            "created_at": int(msg.created_at.timestamp() * 1000),
        }
        event = append_event(room.id, "chat_message", payload, round_id=round_obj.id)
        envelope = build_envelope("chat_message", payload, seq=event.seq)

        def _after_commit() -> None:
            # Turn off typing before sending message
            bot_send_typing(str(room.id), str(bot_seat.id), False)
            _send_room_ws(room.code, envelope)

        transaction.on_commit(_after_commit)
        return envelope


@shared_task(name="apps.bot.tasks.bot_trigger_on_message")
def bot_trigger_on_message(
    round_id_str: str,
    trigger_text: str = "",
    *,
    is_idle_tick: bool = False,
) -> bool:
    """Evaluate whether bot replies to a human message or idle tick, scheduling delayed delivery."""
    round_id = UUID(round_id_str)
    round_obj = Round.objects.select_related("room", "topic").filter(id=round_id).first()
    if (
        round_obj is None
        or round_obj.room.status != RoomStatus.IN_PROGRESS
        or round_obj.phase != RoundPhase.CHAT
    ):
        return False

    bot_seat = round_obj.seats.filter(player__is_bot=True).first()
    if bot_seat is None:
        return False

    reply_data = generate_bot_chat_reply(
        round_obj,
        last_trigger_text=trigger_text,
        is_idle_tick=is_idle_tick,
    )
    if reply_data is None:
        return False

    text, timings = reply_data

    # Schedule typing on and chat message delivery via Celery ETA or countdown
    bot_send_typing.apply_async(
        args=[str(round_obj.room_id), str(bot_seat.id), True],
        countdown=timings.read_delay_seconds,
    )
    bot_send_chat_message.apply_async(
        args=[str(round_obj.room_id), str(round_obj.id), str(bot_seat.id), text],
        countdown=timings.total_delay_seconds,
    )
    return True


@shared_task(name="apps.bot.tasks.bot_idle_tick")
def bot_idle_tick(round_id_str: str) -> bool:
    """Trigger periodic idle evaluation during CHAT phase."""
    return bot_trigger_on_message(round_id_str, is_idle_tick=True)
