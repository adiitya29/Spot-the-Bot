"""Decision engine determining when the bot should reply and pacing fair share."""

from __future__ import annotations

import random
from collections.abc import Callable
from datetime import datetime

from django.utils import timezone

PROB_DIRECT_ADDRESS = 0.95
PROB_GENERAL_MESSAGE = 0.50
PROB_IDLE_TICK = 0.30
MIN_COOLDOWN_SECONDS = 3.0


def compute_fair_share_factor(
    total_messages: int,
    bot_messages: int,
    total_participants: int,
) -> float:
    """Calculate scaling multiplier (0.7x to 1.3x) based on bot's chat volume share."""
    if total_participants <= 1 or total_messages <= 3:
        return 1.0

    fair_share = 1.0 / total_participants
    actual_share = bot_messages / max(1, total_messages)

    if actual_share > (fair_share * 1.5):
        return 0.7
    if actual_share < (fair_share * 0.7):
        return 1.3
    return 1.0


def should_bot_reply(
    *,
    is_idle_tick: bool = False,
    last_trigger_text: str = "",
    bot_alias: str = "",
    last_bot_message_at: datetime | None = None,
    total_messages: int = 0,
    bot_messages: int = 0,
    total_participants: int = 4,
    clock: Callable[[], datetime] | None = None,
    rng: random.Random | None = None,
) -> bool:
    """Evaluate whether the bot should generate a message at this instant."""
    now_fn = clock or timezone.now
    now = now_fn()
    chooser = rng or random.SystemRandom()

    # Enforce minimum cooldown between bot messages
    if last_bot_message_at is not None:
        elapsed = (now - last_bot_message_at).total_seconds()
        if elapsed < MIN_COOLDOWN_SECONDS:
            return False

    # Check for direct address or mention of bot's alias
    is_direct = bool(bot_alias and bot_alias.lower() in last_trigger_text.lower())

    if is_direct:
        base_prob = PROB_DIRECT_ADDRESS
    elif is_idle_tick:
        base_prob = PROB_IDLE_TICK
    else:
        base_prob = PROB_GENERAL_MESSAGE

    scale = compute_fair_share_factor(
        total_messages=total_messages,
        bot_messages=bot_messages,
        total_participants=total_participants,
    )
    final_prob = min(0.98, max(0.05, base_prob * scale))

    return chooser.random() < final_prob
