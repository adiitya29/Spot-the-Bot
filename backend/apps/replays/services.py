"""Business services for consented replay generation, solo play, and bot statistics."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db import models, transaction

from apps.game.models import Round, RoundResult
from apps.replays.exporter import export_round_transcript
from apps.replays.models import ReplayCase


def create_replay_case_from_round(
    round_obj: Round,
    *,
    is_approved: bool = True,
    force: bool = False,
) -> ReplayCase | None:
    """Create an anonymized, consented ReplayCase from a completed game round.

    Enforces explicit consent: if room.config['allow_replay_use'] is False,
    replays are NEVER created.
    """
    room = round_obj.room
    allow_replay = bool(room.config.get("allow_replay_use", True))

    # Strict consent check
    if not allow_replay and not force:
        return None

    # Do not duplicate if replay already exists for this round
    existing = ReplayCase.objects.filter(round=round_obj).first()
    if existing:
        return existing

    # Export completely anonymized transcript with bot secrets masked
    anonymized_transcript = export_round_transcript(
        round_obj,
        anonymize=True,
        include_bot_truth=False,
    )

    # Extract ground truth bot identity to store securely in model fields
    bot_seat = round_obj.seats.filter(player__is_bot=True).first()
    bot_alias = bot_seat.alias if bot_seat else ""
    bot_seat_id = str(bot_seat.id) if bot_seat else ""

    result = RoundResult.objects.filter(round=round_obj).first()
    bot_fooled = result.bot_fooled if result else False

    topic_category = round_obj.topic.category if round_obj.topic else "general"
    topic_text = round_obj.topic.text if round_obj.topic else ""

    return ReplayCase.objects.create(
        round=round_obj,
        room_code=room.code,
        topic_category=topic_category,
        topic_text=topic_text,
        transcript=anonymized_transcript,
        bot_alias=bot_alias,
        bot_seat_id=bot_seat_id,
        bot_fooled_original=bot_fooled,
        is_approved=is_approved,
        allow_replay_use=allow_replay,
    )


def record_solo_guess(
    replay_case_id: UUID | str,
    guessed_alias: str,
) -> dict[str, Any]:
    """Record a solo user's guess on a ReplayCase and return accuracy outcome."""
    clean_guess = guessed_alias.strip()

    with transaction.atomic():
        replay = ReplayCase.objects.select_for_update().get(id=replay_case_id)
        is_correct = clean_guess.lower() == replay.bot_alias.strip().lower()

        replay.human_guesses_count += 1
        if is_correct:
            replay.correct_guesses_count += 1
        replay.save(update_fields=["human_guesses_count", "correct_guesses_count"])

    return {
        "correct": is_correct,
        "guessed_alias": clean_guess,
        "bot_alias": replay.bot_alias,
        "human_guesses_count": replay.human_guesses_count,
        "correct_guesses_count": replay.correct_guesses_count,
        "solo_accuracy_rate": replay.solo_accuracy_rate,
        "solo_bot_fooled_rate": replay.solo_bot_fooled_rate,
        "explanation": (
            f"You correctly spotted {replay.bot_alias} as the AI bot!"
            if is_correct
            else f"Fooled! The covert AI was actually {replay.bot_alias}."
        ),
    }


def get_bot_global_stats() -> dict[str, Any]:
    """Calculate aggregate bot deception rates across live rounds and solo replays."""
    total_live_rounds = RoundResult.objects.count()
    bot_fooled_live_count = RoundResult.objects.filter(bot_fooled=True).count()
    live_fooled_rate = (
        round(bot_fooled_live_count / total_live_rounds, 4) if total_live_rounds > 0 else 0.0
    )

    votes_agg = RoundResult.objects.aggregate(
        total_votes_on_bot=models.Sum("votes_for_bot"),
        total_human_voters=models.Sum("human_voters"),
    )
    total_votes_on_bot = votes_agg["total_votes_on_bot"] or 0
    total_human_voters = votes_agg["total_human_voters"] or 0
    human_voter_accuracy = (
        round(total_votes_on_bot / total_human_voters, 4) if total_human_voters > 0 else 0.0
    )

    solo_agg = ReplayCase.objects.aggregate(
        total_guesses=models.Sum("human_guesses_count"),
        total_correct=models.Sum("correct_guesses_count"),
    )
    total_solo_guesses = solo_agg["total_guesses"] or 0
    total_solo_correct = solo_agg["total_correct"] or 0
    solo_fooled_count = total_solo_guesses - total_solo_correct
    solo_fooled_rate = (
        round(solo_fooled_count / total_solo_guesses, 4) if total_solo_guesses > 0 else 0.0
    )

    # Combined total encounters
    total_encounters = total_live_rounds + total_solo_guesses
    combined_fooled = bot_fooled_live_count + solo_fooled_count
    overall_fooled_rate = (
        round(combined_fooled / total_encounters, 4) if total_encounters > 0 else 0.0
    )

    return {
        "live_games": {
            "total_rounds": total_live_rounds,
            "bot_fooled_count": bot_fooled_live_count,
            "bot_fooled_rate": live_fooled_rate,
            "total_votes_on_bot": total_votes_on_bot,
            "total_human_voters": total_human_voters,
            "human_accuracy_rate": human_voter_accuracy,
        },
        "solo_replays": {
            "total_replays_available": ReplayCase.objects.filter(is_approved=True).count(),
            "total_guesses": total_solo_guesses,
            "correct_guesses": total_solo_correct,
            "fooled_guesses": solo_fooled_count,
            "bot_fooled_rate": solo_fooled_rate,
        },
        "overall": {
            "total_encounters": total_encounters,
            "total_fooled": combined_fooled,
            "bot_fooled_rate": overall_fooled_rate,
        },
    }
