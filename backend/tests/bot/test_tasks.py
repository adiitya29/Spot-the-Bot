"""Tests for Celery bot tasks, typing dispatch, and scheduled message execution."""

from __future__ import annotations

import pytest

from apps.bot.tasks import (
    bot_idle_tick,
    bot_send_chat_message,
    bot_send_typing,
    bot_trigger_on_message,
)
from apps.common.models import Event
from apps.game.models import Message, RoundPhase
from apps.game.state_machine import advance_phase, start_game
from tests.rooms.factories import PlayerFactory, RoomFactory


@pytest.mark.django_db(transaction=True)
def test_bot_send_typing_runs_without_db_side_effects() -> None:
    room = RoomFactory()
    bot_player = PlayerFactory(room=room, nickname="BotP", is_bot=True)
    initial_event_count = Event.objects.filter(room=room).count()

    # Calling typing does not create Event rows
    bot_send_typing(str(room.id), str(bot_player.id), True)
    assert Event.objects.filter(room=room).count() == initial_event_count


@pytest.mark.django_db(transaction=True)
def test_bot_send_chat_message_creates_message_and_event() -> None:
    room = RoomFactory(config={"min_humans": 3})
    p1 = PlayerFactory(room=room, nickname="P1", is_host=True, connected=True)
    PlayerFactory(room=room, nickname="P2", connected=True)
    PlayerFactory(room=room, nickname="P3", connected=True)

    start_game(room.id, p1.id)
    round_obj = room.rounds.first()
    assert round_obj is not None
    advance_phase(round_obj.id)
    round_obj.refresh_from_db()
    assert round_obj.phase == RoundPhase.CHAT

    bot_seat = round_obj.seats.filter(player__is_bot=True).first()
    assert bot_seat is not None

    env = bot_send_chat_message(
        str(room.id),
        str(round_obj.id),
        str(bot_seat.id),
        "Hey everyone, checking in!",
    )
    assert env is not None
    assert env["type"] == "chat_message"
    assert env["payload"]["text"] == "Hey everyone, checking in!"

    # Verify Message and Event created in DB
    msg = Message.objects.filter(
        round=round_obj, seat=bot_seat, text="Hey everyone, checking in!"
    ).first()
    assert msg is not None
    assert msg.meta.get("source") == "bot_engine_v1"

    ev = Event.objects.filter(room=room, type="chat_message").last()
    assert ev is not None
    assert ev.payload["text"] == "Hey everyone, checking in!"


@pytest.mark.django_db(transaction=True)
def test_bot_trigger_on_message_task_execution() -> None:
    room = RoomFactory(config={"min_humans": 3})
    p1 = PlayerFactory(room=room, nickname="P1", is_host=True, connected=True)
    PlayerFactory(room=room, nickname="P2", connected=True)
    PlayerFactory(room=room, nickname="P3", connected=True)

    start_game(room.id, p1.id)
    round_obj = room.rounds.first()
    assert round_obj is not None
    advance_phase(round_obj.id)

    # Calling task directly
    res = bot_trigger_on_message(str(round_obj.id), trigger_text="what do you think?")
    # Returns True or False depending on decision
    assert isinstance(res, bool)


@pytest.mark.django_db(transaction=True)
def test_bot_idle_tick_task_execution() -> None:
    room = RoomFactory(config={"min_humans": 3})
    p1 = PlayerFactory(room=room, nickname="P1", is_host=True, connected=True)
    PlayerFactory(room=room, nickname="P2", connected=True)
    PlayerFactory(room=room, nickname="P3", connected=True)

    start_game(room.id, p1.id)
    round_obj = room.rounds.first()
    assert round_obj is not None
    advance_phase(round_obj.id)

    res = bot_idle_tick(str(round_obj.id))
    assert isinstance(res, bool)
