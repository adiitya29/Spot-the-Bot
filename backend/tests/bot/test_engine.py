"""Tests for the Bot Engine pipeline, budgets, and timeout fallbacks."""

from __future__ import annotations

import random
from uuid import uuid4

import pytest
from django.test import override_settings

from apps.bot.engine import (
    BotBudgetTracker,
    generate_bot_answer,
    generate_bot_chat_reply,
)
from apps.bot.llm.fake import FakeLLMClient
from apps.bot.stub import STUB_BOT_ANSWERS, STUB_BOT_CHAT_MESSAGES
from apps.game.models import RoundPhase
from apps.game.state_machine import advance_phase, start_game
from tests.rooms.factories import PlayerFactory, RoomFactory


@pytest.mark.django_db(transaction=True)
def test_budget_tracker_enforces_round_and_ip_limits() -> None:
    round_id = uuid4()
    ip = f"10.0.0.{uuid4().int % 200}"

    with override_settings(BOT_MAX_CALLS_PER_ROUND=2, BOT_DAILY_CALLS_PER_IP=3):
        assert BotBudgetTracker.can_make_call(round_id, ip_address=ip) is True
        BotBudgetTracker.record_call(round_id, ip_address=ip)
        assert BotBudgetTracker.can_make_call(round_id, ip_address=ip) is True
        BotBudgetTracker.record_call(round_id, ip_address=ip)
        # Exceeded round limit of 2
        assert BotBudgetTracker.can_make_call(round_id, ip_address=ip) is False


@pytest.mark.django_db(transaction=True)
def test_budget_tracker_honors_bot_enabled_false() -> None:
    round_id = uuid4()
    with override_settings(BOT_ENABLED=False):
        assert BotBudgetTracker.can_make_call(round_id) is False


@pytest.mark.django_db(transaction=True)
def test_generate_bot_answer_uses_llm_and_records_call() -> None:
    room = RoomFactory(config={"min_humans": 3})
    p1 = PlayerFactory(room=room, nickname="P1", is_host=True, connected=True)
    PlayerFactory(room=room, nickname="P2", connected=True)
    PlayerFactory(room=room, nickname="P3", connected=True)

    start_game(room.id, p1.id)
    round_obj = room.rounds.first()
    assert round_obj is not None

    fake_llm = FakeLLMClient(canned_responses=["Pineapple definitely belongs on pizza"])
    answer = generate_bot_answer(round_obj, client=fake_llm)
    assert answer.lower() == "pineapple definitely belongs on pizza"
    assert len(fake_llm.call_history) == 1


@pytest.mark.django_db(transaction=True)
def test_generate_bot_answer_falls_back_to_stub_on_timeout() -> None:
    room = RoomFactory(config={"min_humans": 3})
    p1 = PlayerFactory(room=room, nickname="P1", is_host=True, connected=True)
    PlayerFactory(room=room, nickname="P2", connected=True)
    PlayerFactory(room=room, nickname="P3", connected=True)

    start_game(room.id, p1.id)
    round_obj = room.rounds.first()
    assert round_obj is not None

    # Simulate 8s timeout in LLM
    timeout_llm = FakeLLMClient(should_timeout=True)
    answer = generate_bot_answer(round_obj, client=timeout_llm)
    # Must cleanly fall back to one of the stub answers without crashing
    assert answer in STUB_BOT_ANSWERS


@pytest.mark.django_db(transaction=True)
def test_generate_bot_chat_reply_pipeline() -> None:
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

    fake_llm = FakeLLMClient(
        canned_responses=["Honestly not sure what everyone is talking about lol"]
    )
    # Force reply via direct address
    bot_seat = round_obj.seats.filter(player__is_bot=True).first()
    assert bot_seat is not None

    result = generate_bot_chat_reply(
        round_obj,
        last_trigger_text=f"Hey {bot_seat.alias} what is your take?",
        client=fake_llm,
        rng=random.Random(42),
    )
    assert result is not None
    text, timings = result
    assert "honestly not sure" in text.lower()
    assert timings.total_delay_seconds > 0.0


@pytest.mark.django_db(transaction=True)
def test_generate_bot_chat_reply_falls_back_on_timeout() -> None:
    room = RoomFactory(config={"min_humans": 3})
    p1 = PlayerFactory(room=room, nickname="P1", is_host=True, connected=True)
    PlayerFactory(room=room, nickname="P2", connected=True)
    PlayerFactory(room=room, nickname="P3", connected=True)

    start_game(room.id, p1.id)
    round_obj = room.rounds.first()
    assert round_obj is not None
    advance_phase(round_obj.id)
    round_obj.refresh_from_db()

    bot_seat = round_obj.seats.filter(player__is_bot=True).first()
    assert bot_seat is not None

    timeout_llm = FakeLLMClient(should_timeout=True)
    result = generate_bot_chat_reply(
        round_obj,
        last_trigger_text=f"{bot_seat.alias} hello",
        client=timeout_llm,
        rng=random.Random(42),
    )
    assert result is not None
    text, _ = result
    # Fallback to stub chat message
    assert text in STUB_BOT_CHAT_MESSAGES
