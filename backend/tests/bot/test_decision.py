"""Tests for reply probability, direct address, cooldown, and fair-share pacing."""

from __future__ import annotations

import random
from datetime import timedelta

from django.utils import timezone

from apps.bot.decision import compute_fair_share_factor, should_bot_reply


def test_fair_share_scaling() -> None:
    # 4 participants -> fair share is 25%
    # If bot spoke 50% (5 out of 10) -> scaled down
    assert compute_fair_share_factor(10, 5, 4) == 0.7
    # If bot spoke 5% (1 out of 20) -> scaled up
    assert compute_fair_share_factor(20, 1, 4) == 1.3
    # If bot spoke near fair share (2 out of 8) -> 1.0
    assert compute_fair_share_factor(8, 2, 4) == 1.0


def test_decision_enforces_cooldown() -> None:
    now = timezone.now()
    # Sent message 1 second ago -> should reject immediately
    result = should_bot_reply(
        last_bot_message_at=now - timedelta(seconds=1.0),
        clock=lambda: now,
    )
    assert result is False


def test_decision_direct_mention_high_probability() -> None:
    now = timezone.now()
    # Direct mention with alias "Teal Otter"
    result = should_bot_reply(
        last_trigger_text="Hey Teal Otter what do you think?",
        bot_alias="Teal Otter",
        clock=lambda: now,
        rng=random.Random(42),
    )
    assert result is True


def test_decision_deterministic_with_injected_rng() -> None:
    now = timezone.now()
    r1 = should_bot_reply(
        last_trigger_text="Anyone there?",
        clock=lambda: now,
        rng=random.Random(100),
    )
    r2 = should_bot_reply(
        last_trigger_text="Anyone there?",
        clock=lambda: now,
        rng=random.Random(100),
    )
    assert r1 == r2
