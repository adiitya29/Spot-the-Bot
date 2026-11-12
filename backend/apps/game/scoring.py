"""Vote resolution, scoring (+100 per bot spot), Reveal, and Game Over payloads."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from django.db.models import F

from apps.game.models import Round, RoundResult, RoundSeat, Vote
from apps.rooms.models import Player, Room

POINTS_FOR_SPOTTING_BOT = 100


def compute_bot_fooled(votes_for_bot: int, human_voters: int) -> bool:
    """Return True when strictly less than half of casting humans spotted the bot."""
    if human_voters <= 0:
        return False
    return (votes_for_bot * 2) < human_voters


def build_leaderboard(
    room: Room,
    *,
    round_points_by_player_id: dict[UUID, int] | None = None,
) -> list[dict[str, Any]]:
    """Return human players sorted by descending total score and join order."""
    humans = list(room.players.filter(is_bot=False).order_by("-score", "joined_at"))
    entries: list[dict[str, Any]] = []
    for idx, player in enumerate(humans, start=1):
        entry: dict[str, Any] = {
            "rank": idx,
            "player_id": str(player.id),
            "nickname": player.nickname,
            "is_host": player.is_host,
            "connected": player.connected,
            "score": player.score,
        }
        if round_points_by_player_id is not None:
            entry["round_points"] = round_points_by_player_id.get(player.id, 0)
        entries.append(entry)
    return entries


def build_reveal_payload(
    round_obj: Round,
    *,
    round_points_by_player_id: dict[UUID, int] | None = None,
) -> dict[str, Any]:
    """Serialize REVEAL payload with bot identity, per-seat tallies, and leaderboard."""
    room = round_obj.room
    result = round_obj.result
    seats = list(round_obj.seats.select_related("player").order_by("order_index", "id"))
    votes = list(Vote.objects.filter(round=round_obj).order_by("id"))

    voters_by_target: dict[UUID, list[str]] = {seat.id: [] for seat in seats}
    target_by_voter: dict[UUID, UUID] = {}
    for vote in votes:
        voters_by_target.setdefault(vote.target_seat_id, []).append(str(vote.voter_seat_id))
        target_by_voter[vote.voter_seat_id] = vote.target_seat_id

    if round_points_by_player_id is None:
        round_points_by_player_id = {}
        for seat in seats:
            if seat.player.is_bot:
                continue
            voted_target = target_by_voter.get(seat.id)
            round_points_by_player_id[seat.player_id] = (
                POINTS_FOR_SPOTTING_BOT if voted_target == result.bot_seat_id else 0
            )

    tally: list[dict[str, Any]] = []
    for seat in seats:
        voter_seat_ids = voters_by_target.get(seat.id, [])
        voted_target_id = target_by_voter.get(seat.id)
        is_bot_seat = seat.player.is_bot
        tally.append(
            {
                "seat_id": str(seat.id),
                "alias": seat.alias,
                "color_index": seat.color_index,
                "is_bot": is_bot_seat,
                "player_id": None if is_bot_seat else str(seat.player_id),
                "nickname": "Bot" if is_bot_seat else seat.player.nickname,
                "votes_received": len(voter_seat_ids),
                "voter_seat_ids": voter_seat_ids,
                "voted_target_seat_id": str(voted_target_id) if voted_target_id else None,
                "round_points": (
                    0 if is_bot_seat else round_points_by_player_id.get(seat.player_id, 0)
                ),
                "total_score": None if is_bot_seat else seat.player.score,
            }
        )

    return {
        "round_id": str(round_obj.id),
        "round_number": round_obj.number,
        "total_rounds": int(room.config.get("rounds", 3)),
        "bot_seat_id": str(result.bot_seat_id),
        "bot_alias": result.bot_seat.alias,
        "votes_for_bot": result.votes_for_bot,
        "human_voters": result.human_voters,
        "bot_fooled": result.bot_fooled,
        "tally": tally,
        "leaderboard": build_leaderboard(room, round_points_by_player_id=round_points_by_player_id),
    }


def finalize_round_scores(round_obj: Round) -> dict[str, Any]:
    """Tally votes, award +100 points to correct humans, and persist RoundResult once."""
    existing = RoundResult.objects.filter(round=round_obj).select_related("bot_seat").first()
    if existing is not None:
        return build_reveal_payload(round_obj)

    bot_seat = (
        RoundSeat.objects.select_related("player")
        .filter(round=round_obj, player__is_bot=True)
        .first()
    )
    if bot_seat is None:
        raise ValueError(f"Round {round_obj.id} has no bot seat.")

    human_votes = list(
        Vote.objects.filter(round=round_obj, voter_seat__player__is_bot=False)
        .select_related("voter_seat")
        .order_by("id")
    )
    human_voters = len(human_votes)
    winning_player_ids = [
        vote.voter_seat.player_id for vote in human_votes if vote.target_seat_id == bot_seat.id
    ]
    votes_for_bot = len(winning_player_ids)
    bot_fooled = compute_bot_fooled(votes_for_bot, human_voters)

    if winning_player_ids:
        Player.objects.filter(id__in=winning_player_ids).update(
            score=F("score") + POINTS_FOR_SPOTTING_BOT
        )

    RoundResult.objects.create(
        round=round_obj,
        bot_seat=bot_seat,
        votes_for_bot=votes_for_bot,
        human_voters=human_voters,
        bot_fooled=bot_fooled,
    )

    round_points_by_player_id: dict[UUID, int] = {
        pid: POINTS_FOR_SPOTTING_BOT for pid in winning_player_ids
    }
    return build_reveal_payload(round_obj, round_points_by_player_id=round_points_by_player_id)


def build_game_over_payload(room: Room, *, game_index: int) -> dict[str, Any]:
    """Build final Game Over payload with overall leaderboard and round summaries."""
    rounds = list(
        Round.objects.filter(room=room, game_index=game_index)
        .select_related("topic")
        .order_by("number")
    )
    results_by_round_id = {
        res.round_id: res
        for res in RoundResult.objects.filter(round__in=rounds).select_related("bot_seat")
    }

    rounds_summary: list[dict[str, Any]] = []
    bot_fooled_count = 0
    for round_obj in rounds:
        result = results_by_round_id.get(round_obj.id)
        if result is not None and result.bot_fooled:
            bot_fooled_count += 1
        rounds_summary.append(
            {
                "round_number": round_obj.number,
                "topic_text": round_obj.topic.text,
                "topic_category": round_obj.topic.category,
                "bot_alias": result.bot_seat.alias if result is not None else "",
                "votes_for_bot": result.votes_for_bot if result is not None else 0,
                "human_voters": result.human_voters if result is not None else 0,
                "bot_fooled": result.bot_fooled if result is not None else False,
            }
        )

    return {
        "game_index": game_index,
        "total_rounds": len(rounds),
        "bot_fooled_count": bot_fooled_count,
        "leaderboard": build_leaderboard(room),
        "rounds_summary": rounds_summary,
    }
