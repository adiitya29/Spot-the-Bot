"""Canned Phase 4 stub bot responses for ANSWER and CHAT phases."""

from __future__ import annotations

import random
from typing import Any
from uuid import UUID, uuid4

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import transaction

from apps.common.events import append_event, build_envelope
from apps.common.locks import room_lock
from apps.game.models import Message, MessageKind, Round, RoundPhase
from apps.rooms.models import Room, RoomStatus

STUB_BOT_ANSWERS: tuple[str, ...] = (
    "Honestly depends on the day, could go either way tbh",
    "I think about this way too much and still have no solid excuse lol",
    "Not gonna lie I am lowkey guilty of this exact thing",
    "Wait why does everyone suddenly have strong feelings about this",
    "Probably overthinking it again but my gut says yes",
    "I tried doing it once and immediately regretted every second",
)

STUB_BOT_CHAT_MESSAGES: tuple[str, ...] = (
    "wait some of these answers are way too confident lol",
    "idk why but one answer feels suspiciously polite",
    "okay who wrote that one, confess right now",
    "honestly that could totally be a real person or a very tired bot",
    "nah i feel like the quietest person here is hiding something",
    "im tearing apart every single word right now ngl",
)


def pick_stub_answer(
    round_obj: Round | None = None,
    *,
    rng: random.Random | None = None,
) -> str:
    """Pick a deterministic or random canned opening answer for the bot."""
    chooser = rng or random.SystemRandom()
    if round_obj is not None:
        existing_texts = set(
            Message.objects.filter(round=round_obj, kind=MessageKind.ANSWER).values_list(
                "text", flat=True
            )
        )
        unused = [text for text in STUB_BOT_ANSWERS if text not in existing_texts]
        if unused:
            return chooser.choice(unused)
    return chooser.choice(STUB_BOT_ANSWERS)


def pick_stub_chat_message(
    round_obj: Round | None = None,
    *,
    rng: random.Random | None = None,
) -> str:
    """Pick a canned chat line not yet posted by the stub bot in the round."""
    chooser = rng or random.SystemRandom()
    if round_obj is not None:
        used_texts = set(
            Message.objects.filter(
                round=round_obj,
                kind=MessageKind.CHAT,
                seat__player__is_bot=True,
            ).values_list("text", flat=True)
        )
        unused = [line for line in STUB_BOT_CHAT_MESSAGES if line not in used_texts]
        if unused:
            return chooser.choice(unused)
    return chooser.choice(STUB_BOT_CHAT_MESSAGES)


def post_stub_chat_message(
    round_id: UUID,
    *,
    rng: random.Random | None = None,
) -> dict[str, Any] | None:
    """Post one canned stub bot chat message if the round is actively in CHAT."""
    lookup = Round.objects.filter(id=round_id).values("room_id").first()
    if lookup is None:
        return None
    room_id: UUID = lookup["room_id"]

    with room_lock(room_id), transaction.atomic():
        room = Room.objects.select_for_update().get(id=room_id)
        round_obj = Round.objects.select_for_update().filter(id=round_id, room=room).first()
        if (
            round_obj is None
            or room.status != RoomStatus.IN_PROGRESS
            or round_obj.phase != RoundPhase.CHAT
        ):
            return None

        bot_seat = round_obj.seats.select_related("player").filter(player__is_bot=True).first()
        if bot_seat is None:
            return None

        text = pick_stub_chat_message(round_obj, rng=rng)
        msg = Message.objects.create(
            round=round_obj,
            seat=bot_seat,
            text=text,
            kind=MessageKind.CHAT,
            client_msg_id=uuid4(),
            meta={"source": "phase4_stub"},
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
            layer = get_channel_layer()
            if layer is None:
                return
            async_to_sync(layer.group_send)(
                f"room_{room.code}",
                {
                    "type": "room.event",
                    "sender_channel": "",
                    "envelope": envelope,
                },
            )

        transaction.on_commit(_after_commit)
        return envelope
