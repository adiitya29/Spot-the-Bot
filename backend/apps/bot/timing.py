"""Human-like typing speed, reading latency, and dispatch timing calculations."""

from __future__ import annotations

import random
from dataclasses import dataclass

READ_TIME_MIN = 0.6
READ_TIME_MAX = 1.8
CPM_MIN = 180
CPM_MAX = 320
TOTAL_DELAY_MIN = 1.5
TOTAL_DELAY_MAX = 15.0


@dataclass(frozen=True)
class BotScheduleTimings:
    read_delay_seconds: float
    typing_duration_seconds: float
    total_delay_seconds: float


def compute_bot_timings(
    trigger_text_length: int,
    bot_reply_text: str,
    *,
    rng: random.Random | None = None,
) -> BotScheduleTimings:
    """Calculate natural reading latency and typing duration for a reply."""
    chooser = rng or random.SystemRandom()

    # Reading latency: scales with incoming message length
    base_read = 0.5 + (trigger_text_length * 0.015)
    read_delay = min(READ_TIME_MAX, max(READ_TIME_MIN, base_read))
    read_jitter = chooser.uniform(-0.15, 0.15)
    read_delay = max(READ_TIME_MIN, read_delay + read_jitter)

    # Typing duration: based on human characters per minute (180 - 320 cpm)
    cpm = chooser.uniform(CPM_MIN, CPM_MAX)
    chars_per_sec = cpm / 60.0
    reply_len = max(1, len(bot_reply_text))
    raw_type_sec = reply_len / chars_per_sec

    # Add 10% typing jitter
    type_jitter = chooser.uniform(-0.1, 0.1) * raw_type_sec
    typing_duration = max(0.8, raw_type_sec + type_jitter)

    # Total delay clamped to realistic party gaming window
    total_delay = read_delay + typing_duration
    total_delay = min(TOTAL_DELAY_MAX, max(TOTAL_DELAY_MIN, total_delay))

    # Re-normalize if clamped
    if total_delay == TOTAL_DELAY_MAX and (read_delay + typing_duration) > TOTAL_DELAY_MAX:
        typing_duration = TOTAL_DELAY_MAX - read_delay

    return BotScheduleTimings(
        read_delay_seconds=round(read_delay, 2),
        typing_duration_seconds=round(typing_duration, 2),
        total_delay_seconds=round(total_delay, 2),
    )
