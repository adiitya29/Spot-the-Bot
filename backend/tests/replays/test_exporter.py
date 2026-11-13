"""Tests for transcript exporter from models and append-only Event logs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from apps.common.models import Event
from apps.game.models import RoundPhase
from apps.game.state_machine import advance_phase, cast_vote, send_chat_message, start_game
from apps.replays.exporter import (
    export_from_events,
    export_room_transcript,
    export_round_transcript,
    save_transcript,
    transcript_to_json,
)
from tests.rooms.factories import PlayerFactory, RoomFactory


@pytest.mark.django_db(transaction=True)
def test_export_round_transcript_with_bot_truth() -> None:
    room = RoomFactory(config={"min_humans": 3, "bot_variant": "terse_casual"})
    p1 = PlayerFactory(room=room, nickname="Alice", is_host=True, connected=True)
    p2 = PlayerFactory(room=room, nickname="Bob", connected=True)
    p3 = PlayerFactory(room=room, nickname="Charlie", connected=True)

    start_game(room.id, p1.id)
    round_obj = room.rounds.first()
    assert round_obj is not None

    # Advance to CHAT (bot answer generated automatically)
    advance_phase(round_obj.id)
    round_obj.refresh_from_db()
    assert round_obj.phase == RoundPhase.CHAT

    # Human send chat message
    p1_seat = round_obj.seats.get(player=p1)
    send_chat_message(room.id, p1.id, "Hey everyone how are we doing today?")

    # Advance to VOTE
    advance_phase(round_obj.id)
    round_obj.refresh_from_db()
    assert round_obj.phase == RoundPhase.VOTE

    # Cast votes: P1 and P2 vote for P3 (not bot), P3 votes for P1 -> bot fooled!
    p3_seat = round_obj.seats.get(player=p3)
    cast_vote(room.id, p1.id, str(p3_seat.id))
    cast_vote(room.id, p2.id, str(p3_seat.id))
    cast_vote(room.id, p3.id, str(p1_seat.id))

    round_obj.refresh_from_db()
    assert round_obj.phase == RoundPhase.REVEAL

    # Export transcript
    transcript = export_round_transcript(round_obj, include_bot_truth=True)

    assert transcript["version"] == 1
    assert transcript["room_code"] == room.code
    assert transcript["bot_variant"] == "terse_casual"
    assert len(transcript["participants"]) == 4

    bot_part = next(p for p in transcript["participants"] if p.get("is_bot") is True)
    assert bot_part["nickname"] == "Bot"

    assert len(transcript["answers"]) >= 1
    assert len(transcript["messages"]) >= 1

    msg = transcript["messages"][0]
    assert "word_count" in msg
    assert "char_count" in msg
    assert "latency_ms" in msg
    assert "is_bot" in msg

    # Outcome verification
    assert transcript["outcome"]["bot_fooled"] is True
    assert transcript["outcome"]["winner"] == "bot"
    assert transcript["outcome"]["bot_seat_id"] is not None

    # Metrics verification
    metrics = transcript["metrics"]
    assert metrics["total_messages"] >= 1
    assert metrics["fair_share"] == 0.25
    assert "avg_human_word_count" in metrics


@pytest.mark.django_db(transaction=True)
def test_export_round_transcript_anonymized_and_hidden_truth() -> None:
    room = RoomFactory(config={"min_humans": 3})
    p1 = PlayerFactory(room=room, nickname="RealNameAlice", is_host=True, connected=True)
    PlayerFactory(room=room, nickname="RealNameBob", connected=True)
    PlayerFactory(room=room, nickname="RealNameCharlie", connected=True)

    start_game(room.id, p1.id)
    round_obj = room.rounds.first()
    assert round_obj is not None

    transcript = export_round_transcript(round_obj, anonymize=True, include_bot_truth=False)

    for p in transcript["participants"]:
        assert "is_bot" not in p
        assert p["nickname"].startswith("Participant ")
        assert "RealName" not in p["nickname"]

    assert "bot_seat_id" not in transcript["outcome"]
    assert "bot_alias" not in transcript["outcome"]


@pytest.mark.django_db(transaction=True)
def test_export_from_events_reconstruction() -> None:
    room = RoomFactory(config={"min_humans": 3})
    p1 = PlayerFactory(room=room, nickname="Alice", is_host=True, connected=True)
    p2 = PlayerFactory(room=room, nickname="Bob", connected=True)
    p3 = PlayerFactory(room=room, nickname="Charlie", connected=True)

    start_game(room.id, p1.id)
    round_obj = room.rounds.first()
    assert round_obj is not None

    advance_phase(round_obj.id)
    round_obj.refresh_from_db()

    p1_seat = round_obj.seats.get(player=p1)
    send_chat_message(room.id, p1.id, "Testing event reconstruction")

    advance_phase(round_obj.id)
    p2_seat = round_obj.seats.get(player=p2)
    p3_seat = round_obj.seats.get(player=p3)
    cast_vote(room.id, p1.id, str(p2_seat.id))
    cast_vote(room.id, p2.id, str(p3_seat.id))
    cast_vote(room.id, p3.id, str(p1_seat.id))

    events = list(Event.objects.filter(room=room).order_by("seq"))
    assert len(events) > 5

    transcript = export_from_events(events, round_id=round_obj.id, include_bot_truth=True)

    assert transcript["version"] == 1
    assert transcript["round_id"] == str(round_obj.id)
    assert len(transcript["participants"]) == 4
    assert len(transcript["messages"]) >= 1
    assert transcript["outcome"]["human_voters"] == 3


@pytest.mark.django_db(transaction=True)
def test_export_room_transcript_aggregation() -> None:
    room = RoomFactory(config={"min_humans": 3})
    p1 = PlayerFactory(room=room, nickname="Alice", is_host=True, connected=True)
    PlayerFactory(room=room, nickname="Bob", connected=True)
    PlayerFactory(room=room, nickname="Charlie", connected=True)

    start_game(room.id, p1.id)
    room_transcript = export_room_transcript(room)

    assert room_transcript["room_id"] == str(room.id)
    assert room_transcript["rounds_played"] == 1
    assert "bot_survival_rate" in room_transcript


def test_transcript_serialization_and_save() -> None:
    sample_data = {
        "version": 1,
        "room_id": "test-room",
        "timestamp": datetime.now(UTC),
    }
    json_str = transcript_to_json(sample_data)
    parsed = json.loads(json_str)
    assert parsed["version"] == 1

    with TemporaryDirectory() as tmp_dir:
        tmp_file = Path(tmp_dir) / "transcript.json"
        save_transcript(sample_data, tmp_file)
        assert tmp_file.exists()
        loaded = json.loads(tmp_file.read_text(encoding="utf-8"))
        assert loaded["version"] == 1
