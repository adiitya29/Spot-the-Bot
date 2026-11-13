"""Event-log transcript exporter for model evaluation, replays, and analysis."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from apps.common.models import Event
from apps.game.models import Message, MessageKind, Round, RoundResult, Vote
from apps.rooms.models import Room


def _calculate_metrics(
    messages: list[dict[str, Any]],
    participants: list[dict[str, Any]],
) -> dict[str, Any]:
    """Calculate volume share, word count averages, and latency metrics."""
    total_msgs = len(messages)
    participant_count = max(1, len(participants))
    fair_share = round(1.0 / participant_count, 4)

    human_msgs = [m for m in messages if not m.get("is_bot", False)]
    bot_msgs = [m for m in messages if m.get("is_bot", False)]

    human_words = [m["word_count"] for m in human_msgs]
    bot_words = [m["word_count"] for m in bot_msgs]

    human_latencies = [m["latency_ms"] / 1000.0 for m in human_msgs if m["latency_ms"] > 0]
    bot_latencies = [m["latency_ms"] / 1000.0 for m in bot_msgs if m["latency_ms"] > 0]

    avg_human_word = round(sum(human_words) / max(1, len(human_words)), 2)
    avg_bot_word = round(sum(bot_words) / max(1, len(bot_words)), 2)

    avg_human_latency = round(sum(human_latencies) / max(1, len(human_latencies)), 2)
    avg_bot_latency = round(sum(bot_latencies) / max(1, len(bot_latencies)), 2)

    bot_share = round(len(bot_msgs) / max(1, total_msgs), 4)

    return {
        "total_messages": total_msgs,
        "human_messages": len(human_msgs),
        "bot_messages": len(bot_msgs),
        "bot_share": bot_share,
        "fair_share": fair_share,
        "share_deviation": round(abs(bot_share - fair_share), 4),
        "avg_human_word_count": avg_human_word,
        "avg_bot_word_count": avg_bot_word,
        "avg_human_latency_sec": avg_human_latency,
        "avg_bot_latency_sec": avg_bot_latency,
    }


def export_round_transcript(
    round_obj: Round,
    *,
    anonymize: bool = False,
    include_bot_truth: bool = True,
) -> dict[str, Any]:
    """Export a complete structured transcript of a round from database state."""
    room = round_obj.room
    seats = list(round_obj.seats.select_related("player").order_by("order_index", "id"))
    messages_qs = (
        Message.objects.filter(round=round_obj)
        .select_related("seat__player")
        .order_by("created_at")
    )

    result = RoundResult.objects.filter(round=round_obj).first()
    bot_seat = next((s for s in seats if s.player.is_bot), None)
    bot_seat_id = str(bot_seat.id) if bot_seat else None
    bot_alias = bot_seat.alias if bot_seat else ""

    bot_variant = (round_obj.bot_persona or {}).get("variant") or room.config.get(
        "bot_variant", "baseline_v1"
    )

    participants_data: list[dict[str, Any]] = []
    for idx, seat in enumerate(seats, start=1):
        is_bot = seat.player.is_bot
        nick = f"Participant {idx}" if anonymize else seat.player.nickname
        part: dict[str, Any] = {
            "seat_id": str(seat.id),
            "alias": seat.alias,
            "color_index": seat.color_index,
            "nickname": "Bot" if (is_bot and include_bot_truth) else nick,
        }
        if include_bot_truth:
            part["is_bot"] = is_bot
        participants_data.append(part)

    answers_data: list[dict[str, Any]] = []
    chat_messages: list[dict[str, Any]] = []
    prev_time: datetime | None = None

    for msg in messages_qs:
        if msg.kind == MessageKind.ANSWER:
            answers_data.append(
                {
                    "seat_id": str(msg.seat_id),
                    "alias": msg.seat.alias,
                    "text": msg.text,
                    "submitted_at": msg.created_at.isoformat(),
                }
            )
        elif msg.kind == MessageKind.CHAT:
            latency_ms = 0.0
            if prev_time is not None:
                delta = (msg.created_at - prev_time).total_seconds()
                latency_ms = max(0.0, delta * 1000.0)
            prev_time = msg.created_at

            words = len(msg.text.split())
            chars = len(msg.text)
            entry: dict[str, Any] = {
                "id": str(msg.id),
                "seat_id": str(msg.seat_id),
                "alias": msg.seat.alias,
                "text": msg.text,
                "created_at": msg.created_at.isoformat(),
                "timestamp_ms": int(msg.created_at.timestamp() * 1000),
                "latency_ms": round(latency_ms, 1),
                "word_count": words,
                "char_count": chars,
            }
            if include_bot_truth:
                entry["is_bot"] = msg.seat.player.is_bot
            chat_messages.append(entry)

    votes_data: list[dict[str, Any]] = []
    votes_on_bot = 0
    human_voters = 0
    seat_by_id = {s.id: s for s in seats}

    for vote in Vote.objects.filter(round=round_obj).order_by("id"):
        voter_seat = seat_by_id.get(vote.voter_seat_id)
        target_seat = seat_by_id.get(vote.target_seat_id)
        if not voter_seat or not target_seat:
            continue
        voted_bot = bool(bot_seat and target_seat.id == bot_seat.id)
        if not voter_seat.player.is_bot:
            human_voters += 1
            if voted_bot:
                votes_on_bot += 1
        vote_entry: dict[str, Any] = {
            "voter_alias": voter_seat.alias,
            "target_alias": target_seat.alias,
        }
        if include_bot_truth:
            vote_entry["voted_for_bot"] = voted_bot
            vote_entry["is_bot_voter"] = voter_seat.player.is_bot
        votes_data.append(vote_entry)

    bot_fooled = (votes_on_bot * 2) < human_voters if human_voters > 0 else False
    if result is not None:
        bot_fooled = result.bot_fooled
        votes_on_bot = result.votes_for_bot
        human_voters = result.human_voters

    outcome: dict[str, Any] = {
        "votes_on_bot": votes_on_bot,
        "human_voters": human_voters,
        "bot_fooled": bot_fooled,
        "winner": "bot" if bot_fooled else "humans",
    }
    if include_bot_truth:
        outcome["bot_seat_id"] = bot_seat_id
        outcome["bot_alias"] = bot_alias

    metrics = _calculate_metrics(chat_messages, participants_data)

    return {
        "version": 1,
        "room_id": str(room.id),
        "room_code": room.code,
        "round_id": str(round_obj.id),
        "game_index": round_obj.game_index,
        "round_number": round_obj.number,
        "topic": round_obj.topic.text if round_obj.topic else "",
        "bot_variant": bot_variant,
        "participants": participants_data,
        "answers": answers_data,
        "messages": chat_messages,
        "votes": votes_data,
        "outcome": outcome,
        "metrics": metrics,
    }


def export_from_events(
    events: list[Event],
    *,
    round_id: UUID | str | None = None,
    anonymize: bool = False,
    include_bot_truth: bool = True,
) -> dict[str, Any]:
    """Reconstruct a round transcript purely from an append-only Event log stream."""
    target_round_id = str(round_id) if round_id else None

    room_code = ""
    room_id = ""
    round_number = 1
    topic_text = ""
    participants: dict[str, dict[str, Any]] = {}
    answers: list[dict[str, Any]] = []
    messages: list[dict[str, Any]] = []
    votes: list[dict[str, Any]] = []
    outcome: dict[str, Any] = {}
    bot_seat_id: str | None = None
    bot_alias = ""
    bot_variant = "baseline_v1"

    prev_created_at: datetime | None = None

    for ev in events:
        p = ev.payload or {}
        ev_type = ev.type

        # Check round filtering
        ev_round = str(ev.round_id) if ev.round_id else p.get("round_id")
        if target_round_id and ev_round and str(ev_round) != target_round_id:
            continue

        if ev_type == "phase_changed":
            phase_round_id = p.get("round_id")
            if not target_round_id and phase_round_id:
                target_round_id = str(phase_round_id)
            round_number = p.get("round_number", round_number)
            raw_topic = p.get("topic")
            if isinstance(raw_topic, dict):
                topic_text = raw_topic.get("text", topic_text)
            elif isinstance(raw_topic, str):
                topic_text = raw_topic

            # Register participants from initial phase
            for seat in p.get("seats", []):
                sid = str(seat.get("seat_id") or seat.get("id"))
                if sid not in participants:
                    participants[sid] = {
                        "seat_id": sid,
                        "alias": seat["alias"],
                        "color_index": seat.get("color_index", 0),
                        "nickname": (
                            f"Participant {len(participants) + 1}"
                            if anonymize
                            else seat.get("nickname", "")
                        ),
                    }

        elif ev_type == "answers_revealed":
            for ans in p.get("answers", []):
                sid = ans.get("seat_id")
                answers.append(
                    {
                        "seat_id": sid,
                        "alias": ans.get("alias", ""),
                        "text": ans.get("text", ""),
                        "submitted_at": ev.created_at.isoformat(),
                    }
                )

        elif ev_type == "chat_message":
            latency_ms = 0.0
            if prev_created_at is not None:
                latency_ms = max(0.0, (ev.created_at - prev_created_at).total_seconds() * 1000.0)
            prev_created_at = ev.created_at

            text = p.get("text", "")
            sid = p.get("seat_id")
            msg_entry: dict[str, Any] = {
                "id": str(p.get("id", ev.id)),
                "seat_id": sid,
                "alias": p.get("sender_alias", ""),
                "text": text,
                "created_at": ev.created_at.isoformat(),
                "timestamp_ms": int(ev.created_at.timestamp() * 1000),
                "latency_ms": round(latency_ms, 1),
                "word_count": len(text.split()),
                "char_count": len(text),
            }
            messages.append(msg_entry)

        elif ev_type == "reveal":
            bot_seat_id = str(p.get("bot_seat_id"))
            bot_alias = p.get("bot_alias", "")
            votes_on_bot = 0
            human_voters = 0

            for entry in p.get("tally", []):
                sid = str(entry["seat_id"])
                is_bot = bool(entry.get("is_bot"))
                if sid in participants:
                    participants[sid]["is_bot"] = is_bot
                    if not anonymize:
                        participants[sid]["nickname"] = entry.get("nickname", "")

                voted_target = entry.get("voted_target_seat_id")
                if voted_target:
                    votes.append(
                        {
                            "voter_alias": entry.get("alias", ""),
                            "target_seat_id": str(voted_target),
                            "voted_for_bot": (str(voted_target) == bot_seat_id),
                        }
                    )
                if not is_bot:
                    human_voters += 1
                    if str(voted_target) == bot_seat_id:
                        votes_on_bot += 1

            bot_fooled = (votes_on_bot * 2) < human_voters if human_voters > 0 else False
            outcome = {
                "votes_on_bot": votes_on_bot,
                "human_voters": human_voters,
                "bot_fooled": bot_fooled,
                "winner": "bot" if bot_fooled else "humans",
            }
            if include_bot_truth:
                outcome["bot_seat_id"] = bot_seat_id
                outcome["bot_alias"] = bot_alias

    if events:
        room_id = str(events[0].room_id)
        room_code = events[0].room.code if hasattr(events[0], "room") else ""

    # Tag bot messages if truth is enabled and bot_seat_id is known
    for m in messages:
        if include_bot_truth:
            m["is_bot"] = bool(bot_seat_id and m["seat_id"] == bot_seat_id)

    participant_list = list(participants.values())
    metrics = _calculate_metrics(messages, participant_list)

    return {
        "version": 1,
        "room_id": room_id,
        "room_code": room_code,
        "round_id": target_round_id or "",
        "game_index": 1,
        "round_number": round_number,
        "topic": topic_text,
        "bot_variant": bot_variant,
        "participants": participant_list,
        "answers": answers,
        "messages": messages,
        "votes": votes,
        "outcome": outcome,
        "metrics": metrics,
    }


def export_room_transcript(
    room: Room,
    *,
    anonymize: bool = False,
    include_bot_truth: bool = True,
) -> dict[str, Any]:
    """Export complete multi-round transcript and aggregated stats for an entire room."""
    rounds = list(room.rounds.order_by("game_index", "number"))
    rounds_data = [
        export_round_transcript(
            r,
            anonymize=anonymize,
            include_bot_truth=include_bot_truth,
        )
        for r in rounds
    ]

    total_rounds = len(rounds_data)
    bot_fooled_rounds = sum(1 for rd in rounds_data if rd["outcome"].get("bot_fooled", False))

    bot_survival_rate = round(bot_fooled_rounds / max(1, total_rounds), 4)

    return {
        "version": 1,
        "room_id": str(room.id),
        "room_code": room.code,
        "rounds_played": total_rounds,
        "bot_fooled_rounds": bot_fooled_rounds,
        "bot_survival_rate": bot_survival_rate,
        "rounds": rounds_data,
    }


def transcript_to_json(transcript: dict[str, Any], indent: int = 2) -> str:
    """Serialize a transcript dictionary to a pretty JSON string."""
    return json.dumps(transcript, indent=indent, default=str)


def save_transcript(transcript: dict[str, Any], file_path: str | Path) -> None:
    """Save transcript dictionary to a JSON file on disk."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(transcript, f, indent=2, default=str)
