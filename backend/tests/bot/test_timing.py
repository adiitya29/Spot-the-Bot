"""Tests for human reaction, typing duration, and schedule delays."""

from __future__ import annotations

import random

from apps.bot.timing import (
    READ_TIME_MAX,
    READ_TIME_MIN,
    TOTAL_DELAY_MAX,
    TOTAL_DELAY_MIN,
    compute_bot_timings,
)


def test_timing_calculation_within_bounds() -> None:
    timings = compute_bot_timings(
        trigger_text_length=50,
        bot_reply_text="Honestly yeah that sounds pretty good lol",
        rng=random.Random(42),
    )
    assert READ_TIME_MIN <= timings.read_delay_seconds <= READ_TIME_MAX
    assert timings.typing_duration_seconds > 0.5
    assert TOTAL_DELAY_MIN <= timings.total_delay_seconds <= TOTAL_DELAY_MAX


def test_timing_scales_with_longer_messages() -> None:
    short_reply = compute_bot_timings(
        trigger_text_length=10,
        bot_reply_text="yea",
        rng=random.Random(10),
    )
    long_reply = compute_bot_timings(
        trigger_text_length=10,
        bot_reply_text=(
            "I genuinely believe that this is the best possible choice anyone could make here."
        ),
        rng=random.Random(10),
    )
    assert long_reply.typing_duration_seconds > short_reply.typing_duration_seconds


def test_timing_deterministic_with_rng() -> None:
    t1 = compute_bot_timings(30, "sample text", rng=random.Random(99))
    t2 = compute_bot_timings(30, "sample text", rng=random.Random(99))
    assert t1 == t2
