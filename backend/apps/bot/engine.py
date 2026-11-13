"""Core bot engine coordinating LLM completions, style adaptation, timing, and budgets."""

from __future__ import annotations

import contextlib
import random
from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from django.conf import settings
from django.utils import timezone

from apps.bot.decision import should_bot_reply
from apps.bot.filter import check_content_safety
from apps.bot.llm.base import LLMClient, LLMError, LLMTimeoutError
from apps.bot.llm.provider import get_llm_client
from apps.bot.persona import generate_persona
from apps.bot.postprocess import postprocess_bot_message
from apps.bot.profiler import compute_style_profile, should_recompute_profile
from apps.bot.prompt import (
    build_bot_answer_prompt,
    build_bot_chat_prompt,
    build_bot_system_prompt,
)
from apps.bot.stub import pick_stub_answer, pick_stub_chat_message
from apps.bot.timing import BotScheduleTimings, compute_bot_timings
from apps.common.redis import get_redis_client
from apps.game.models import Message, MessageKind, Round, RoundPhase, RoundSeat


class BotBudgetTracker:
    """Track and enforce per-round and daily IP call budgets."""

    @staticmethod
    def _round_key(round_id: UUID) -> str:
        return f"stb:bot:calls:round:{round_id}"

    @staticmethod
    def _ip_key(ip_address: str, date_str: str) -> str:
        return f"stb:bot:calls:ip:{ip_address}:{date_str}"

    @classmethod
    def can_make_call(
        cls,
        round_id: UUID,
        *,
        ip_address: str | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> bool:
        if not getattr(settings, "BOT_ENABLED", True):
            return False

        max_round = int(getattr(settings, "BOT_MAX_CALLS_PER_ROUND", 25))
        max_daily = int(getattr(settings, "BOT_DAILY_CALLS_PER_IP", 200))

        try:
            r = get_redis_client()
            current_round_calls = int(r.get(cls._round_key(round_id)) or 0)
            if current_round_calls >= max_round:
                return False

            if ip_address:
                now_fn = clock or timezone.now
                date_str = now_fn().strftime("%Y-%m-%d")
                current_ip_calls = int(r.get(cls._ip_key(ip_address, date_str)) or 0)
                if current_ip_calls >= max_daily:
                    return False
        except Exception:
            # If Redis check fails, fail-open up to in-memory limits in dev
            pass

        return True

    @classmethod
    def record_call(
        cls,
        round_id: UUID,
        *,
        ip_address: str | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        with contextlib.suppress(Exception):
            r = get_redis_client()
            rkey = cls._round_key(round_id)
            r.incr(rkey)
            r.expire(rkey, 7200)

            if ip_address:
                now_fn = clock or timezone.now
                date_str = now_fn().strftime("%Y-%m-%d")
                ikey = cls._ip_key(ip_address, date_str)
                r.incr(ikey)
                r.expire(ikey, 86400 * 2)


def get_bot_seat(round_obj: Round) -> RoundSeat | None:
    """Return the RoundSeat assigned to the covert AI bot in this round."""
    return round_obj.seats.filter(player__is_bot=True).first()


def generate_bot_answer(
    round_obj: Round,
    *,
    client: LLMClient | None = None,
    rng: random.Random | None = None,
) -> str:
    """Generate a persona-driven opening answer for the round, falling back to stub on failure."""
    if not BotBudgetTracker.can_make_call(round_obj.id):
        return pick_stub_answer(round_obj, rng=rng)

    bot_seat = get_bot_seat(round_obj)
    bot_alias = bot_seat.alias if bot_seat else "Secret Player"

    # Ensure round has a persona
    persona = round_obj.bot_persona
    if not persona:
        persona = generate_persona(round_obj.topic.text, rng=rng)
        round_obj.bot_persona = persona
        round_obj.save(update_fields=["bot_persona"])

    llm = client or get_llm_client()
    system_prompt = build_bot_system_prompt(
        persona=persona,
        style_profile={},
        bot_alias=bot_alias,
    )
    user_prompt = build_bot_answer_prompt(
        topic_text=round_obj.topic.text,
        persona=persona,
        bot_alias=bot_alias,
    )

    try:
        raw_output = llm.complete_sync(user_prompt, system_prompt=system_prompt, timeout=8.0)
        res = postprocess_bot_message(raw_output, allow_typos=False, rng=rng)
        if res.has_leak or not res.text:
            return pick_stub_answer(round_obj, rng=rng)
        BotBudgetTracker.record_call(round_obj.id)
        return res.text
    except (LLMError, LLMTimeoutError, Exception):
        return pick_stub_answer(round_obj, rng=rng)


def generate_bot_chat_reply(
    round_obj: Round,
    *,
    last_trigger_text: str = "",
    is_idle_tick: bool = False,
    client: LLMClient | None = None,
    rng: random.Random | None = None,
    clock: Callable[[], datetime] | None = None,
) -> tuple[str, BotScheduleTimings] | None:
    """Evaluate chat state, generate humanized reply, and compute typing timings."""
    if round_obj.phase != RoundPhase.CHAT:
        round_obj.refresh_from_db()
    if round_obj.phase != RoundPhase.CHAT:
        return None

    if not BotBudgetTracker.can_make_call(round_obj.id, clock=clock):
        return None

    bot_seat = get_bot_seat(round_obj)
    if bot_seat is None:
        return None

    bot_alias = bot_seat.alias

    # Inbound safety check on trigger
    if last_trigger_text:
        check = check_content_safety(last_trigger_text)
        if not check.allowed:
            return None

    # Retrieve messages and stats
    messages = list(
        Message.objects.filter(round=round_obj, kind=MessageKind.CHAT)
        .select_related("seat__player")
        .order_by("created_at")
    )
    total_messages = len(messages)
    bot_messages = sum(1 for m in messages if m.seat.player.is_bot)
    human_texts = [m.text for m in messages if not m.seat.player.is_bot]

    last_bot_msg = next((m for m in reversed(messages) if m.seat.player.is_bot), None)
    last_bot_at = last_bot_msg.created_at if last_bot_msg else None

    total_seats = round_obj.seats.count()

    should_reply = should_bot_reply(
        is_idle_tick=is_idle_tick,
        last_trigger_text=last_trigger_text,
        bot_alias=bot_alias,
        last_bot_message_at=last_bot_at,
        total_messages=total_messages,
        bot_messages=bot_messages,
        total_participants=total_seats or 4,
        clock=clock,
        rng=rng,
    )
    if not should_reply:
        return None

    # Adapt style profile
    current_style = round_obj.style_profile or {}
    last_analyzed = current_style.get("message_count", 0)
    if should_recompute_profile(last_analyzed, len(human_texts)):
        current_style = compute_style_profile(human_texts)
        round_obj.style_profile = current_style
        round_obj.save(update_fields=["style_profile"])

    persona = round_obj.bot_persona or generate_persona(round_obj.topic.text, rng=rng)

    transcript = [(m.seat.alias, m.text) for m in messages[-20:]]
    if last_trigger_text and (not transcript or transcript[-1][1] != last_trigger_text):
        transcript.append(("Player", last_trigger_text))

    system_prompt = build_bot_system_prompt(
        persona=persona,
        style_profile=current_style,
        bot_alias=bot_alias,
    )
    user_prompt = build_bot_chat_prompt(
        topic_text=round_obj.topic.text,
        recent_messages=transcript,
        bot_alias=bot_alias,
    )

    llm = client or get_llm_client()
    reply_text: str = ""

    try:
        raw_reply = llm.complete_sync(user_prompt, system_prompt=system_prompt, timeout=8.0)
        res = postprocess_bot_message(
            raw_reply,
            style_profile=current_style,
            allow_typos=True,
            rng=rng,
        )
        if res.has_leak or not res.text:
            # Fallback on leak
            reply_text = pick_stub_chat_message(round_obj, rng=rng)
        else:
            reply_text = res.text
        BotBudgetTracker.record_call(round_obj.id, clock=clock)
    except (LLMError, LLMTimeoutError, Exception):
        reply_text = pick_stub_chat_message(round_obj, rng=rng)

    timings = compute_bot_timings(
        len(last_trigger_text),
        reply_text,
        rng=rng,
    )
    return reply_text, timings
