"""Tests for Phase 8 viral features: consent, anonymization, solo play, cards, and OG tags."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

import pytest
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.game.aliases import assign_round_aliases
from apps.game.models import Message, MessageKind, Round, RoundPhase, RoundResult, RoundSeat, Topic
from apps.replays.cards import generate_share_card_png
from apps.replays.models import ReplayCase
from apps.replays.services import create_replay_case_from_round
from apps.rooms.models import Player, Room


def _create_sample_room_with_round(
    *,
    code: str = "VRAL01",
    allow_replay: bool = True,
    bot_fooled: bool = True,
) -> tuple[Room, Round, RoundSeat]:
    """Helper to build a completed game round with 3 humans, 1 bot, and RoundResult."""
    room = Room.objects.create(
        code=code,
        config={
            "rounds": 1,
            "min_humans": 3,
            "allow_replay_use": allow_replay,
        },
    )
    p1 = Player.objects.create(room=room, nickname="Alice", is_host=True, connected=True)
    p2 = Player.objects.create(room=room, nickname="Bob", connected=True)
    p3 = Player.objects.create(room=room, nickname="Charlie", connected=True)
    bot = Player.objects.create(room=room, nickname="BotPlayer", is_bot=True, connected=True)

    topic = Topic.objects.first() or Topic.objects.create(
        category="funny",
        text="What food combination do you swear by?",
    )
    now = datetime(2026, 11, 14, 12, 0, 0, tzinfo=UTC)
    round_obj = Round.objects.create(
        room=room,
        topic=topic,
        number=1,
        game_index=1,
        phase=RoundPhase.DONE,
        phase_started_at=now - timedelta(minutes=5),
        phase_ends_at=now,
    )

    aliases = assign_round_aliases(4, rng=random.Random(42))
    seats: list[RoundSeat] = []
    bot_seat: RoundSeat | None = None
    for i, p in enumerate([p1, p2, p3, bot]):
        seat = RoundSeat.objects.create(
            round=round_obj,
            player=p,
            alias=aliases[i].alias,
            color_index=aliases[i].color_index,
            order_index=aliases[i].order_index,
        )
        seats.append(seat)
        if p.is_bot:
            bot_seat = seat

    assert bot_seat is not None

    # Answers
    Message.objects.create(
        round=round_obj,
        seat=seats[0],
        kind=MessageKind.ANSWER,
        text="fries in milkshake",
    )
    Message.objects.create(
        round=round_obj,
        seat=bot_seat,
        kind=MessageKind.ANSWER,
        text="peanut butter on burger lol",
    )

    # Chat messages
    Message.objects.create(
        round=round_obj,
        seat=seats[0],
        kind=MessageKind.CHAT,
        text="wait that's actually good",
    )
    Message.objects.create(
        round=round_obj,
        seat=bot_seat,
        kind=MessageKind.CHAT,
        text="nah fr you gotta try it",
    )

    # Round result
    RoundResult.objects.create(
        round=round_obj,
        bot_seat=bot_seat,
        bot_fooled=bot_fooled,
        votes_for_bot=1 if bot_fooled else 3,
        human_voters=3,
    )

    return room, round_obj, bot_seat


@pytest.mark.django_db
def test_consent_enforcement_allow_replay_use_false_never_creates_replays() -> None:
    """When allow_replay_use is False, create_replay_case_from_round returns None."""
    room, round_obj, _ = _create_sample_room_with_round(
        code="NOCON1",
        allow_replay=False,
    )

    replay = create_replay_case_from_round(round_obj)
    assert replay is None
    assert ReplayCase.objects.filter(room_code="NOCON1").count() == 0


@pytest.mark.django_db
def test_consent_enforcement_allow_replay_use_true_creates_anonymized_replay() -> None:
    """When allow_replay_use is True, ReplayCase is created with anonymized transcript."""
    room, round_obj, bot_seat = _create_sample_room_with_round(
        code="YESCON",
        allow_replay=True,
    )

    replay = create_replay_case_from_round(round_obj)
    assert replay is not None
    assert replay.room_code == "YESCON"
    assert replay.bot_alias == bot_seat.alias
    assert replay.bot_fooled_original is True

    # Anonymization checks: Real nicknames must never appear in transcript
    transcript_str = str(replay.transcript)
    assert "Alice" not in transcript_str
    assert "Bob" not in transcript_str
    assert "Charlie" not in transcript_str
    assert "BotPlayer" not in transcript_str

    # Bot secret fields must not be present in public transcript dict
    assert "is_bot" not in transcript_str
    assert replay.transcript.get("bot_alias") is None
    assert replay.transcript.get("bot_seat_id") is None


@pytest.mark.django_db
def test_pre_guess_leak_scanner_replays_endpoints() -> None:
    """GET /api/replays/ and GET /api/replays/<id>/ must NEVER reveal bot_alias or bot_seat_id."""
    room, round_obj, bot_seat = _create_sample_room_with_round(code="LEAK01")
    replay = create_replay_case_from_round(round_obj)
    assert replay is not None

    client = APIClient()

    # 1. Listing endpoint
    resp_list = client.get("/api/replays/")
    assert resp_list.status_code == 200
    list_str = str(resp_list.json())
    assert bot_seat.alias not in list_str
    assert "bot_alias" not in list_str
    assert "bot_seat_id" not in list_str
    assert "is_bot" not in list_str

    # 2. Detail endpoint
    resp_detail = client.get(f"/api/replays/{replay.id}/")
    assert resp_detail.status_code == 200
    detail_data = resp_detail.json()
    detail_str = str(detail_data)

    assert "bot_alias" not in detail_data
    assert "bot_seat_id" not in detail_data
    assert "is_bot" not in detail_str
    assert "Alice" not in detail_str

    # Participants must list all 4 aliases for solo guessing without revealing bot identity
    participants = detail_data["transcript"]["participants"]
    assert len(participants) == 4
    for p in participants:
        assert "is_bot" not in p


@pytest.mark.django_db
def test_solo_guess_endpoint_scoring_and_accuracy() -> None:
    """POST /api/replays/<id>/guess/ evaluates guess, increments counters, and computes accuracy."""
    room, round_obj, bot_seat = _create_sample_room_with_round(code="SOLO01")
    replay = create_replay_case_from_round(round_obj)
    assert replay is not None

    client = APIClient()

    # Wrong guess
    resp_wrong = client.post(
        f"/api/replays/{replay.id}/guess/",
        {"alias": "Wrong Alias"},
        format="json",
    )
    assert resp_wrong.status_code == 200
    data_wrong = resp_wrong.json()
    assert data_wrong["correct"] is False
    assert data_wrong["bot_alias"] == bot_seat.alias
    assert data_wrong["human_guesses_count"] == 1
    assert data_wrong["correct_guesses_count"] == 0
    assert data_wrong["solo_bot_fooled_rate"] == 1.0

    # Correct guess
    resp_correct = client.post(
        f"/api/replays/{replay.id}/guess/",
        {"alias": bot_seat.alias},
        format="json",
    )
    assert resp_correct.status_code == 200
    data_correct = resp_correct.json()
    assert data_correct["correct"] is True
    assert data_correct["human_guesses_count"] == 2
    assert data_correct["correct_guesses_count"] == 1
    assert data_correct["solo_accuracy_rate"] == 0.5


@pytest.mark.django_db
def test_pillow_share_card_generation_and_endpoint() -> None:
    """Pillow PNG card generation returns valid PNG bytes and GET /api/share/<code>.png works."""
    room, _, _ = _create_sample_room_with_round(code="CARD01", bot_fooled=True)

    # Direct card generation
    png_bytes = generate_share_card_png(room)
    assert len(png_bytes) > 1000
    # Standard PNG magic signature: \x89PNG\r\n\x1a\n
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")

    # Via REST endpoint
    client = APIClient()
    resp = client.get(f"/api/share/{room.code}.png")
    assert resp.status_code == 200
    assert resp["Content-Type"] == "image/png"
    assert resp["Cache-Control"] == "public, max-age=3600"
    assert resp.content.startswith(b"\x89PNG\r\n\x1a\n")

    # Non-existent room returns 404
    resp_404 = client.get("/api/share/NONEXS.png")
    assert resp_404.status_code == 404


@pytest.mark.django_db
def test_opengraph_server_rendered_html_view() -> None:
    """GET /s/<room_code>/ serves server-rendered HTML with full Open Graph and Twitter tags."""
    room, _, _ = _create_sample_room_with_round(code="OGTAG1")

    client = APIClient()
    resp = client.get(f"/s/{room.code}/")
    assert resp.status_code == 200
    assert "text/html" in resp["Content-Type"]

    html = resp.content.decode("utf-8")
    assert '<meta property="og:site_name" content="Spot the Bot">' in html
    expected_title = (
        f'<meta property="og:title" content="Spot the Bot — Room #{room.code} Match Results">'
    )
    assert expected_title in html
    assert f"/api/share/{room.code}.png" in html
    assert '<meta name="twitter:card" content="summary_large_image">' in html
    assert "Play Spot the Bot with Friends" in html


@pytest.mark.django_db
def test_bot_global_stats_endpoint() -> None:
    """GET /api/stats/bot/ aggregates live games, solo replays, and overall deception metrics."""
    room1, r1, _ = _create_sample_room_with_round(code="STAT01", bot_fooled=True)
    room2, r2, _ = _create_sample_room_with_round(code="STAT02", bot_fooled=False)

    rep1 = create_replay_case_from_round(r1)
    assert rep1 is not None
    rep1.human_guesses_count = 10
    rep1.correct_guesses_count = 3  # 7 fooled
    rep1.save()

    client = APIClient()
    resp = client.get("/api/stats/bot/")
    assert resp.status_code == 200
    stats = resp.json()

    assert stats["live_games"]["total_rounds"] >= 2
    assert stats["live_games"]["bot_fooled_count"] >= 1
    assert 0.0 <= stats["live_games"]["bot_fooled_rate"] <= 1.0

    assert stats["solo_replays"]["total_guesses"] >= 10
    assert stats["solo_replays"]["correct_guesses"] >= 3
    assert stats["solo_replays"]["bot_fooled_rate"] == 0.7


@pytest.mark.django_db
def test_delete_room_data_management_command() -> None:
    """delete_room_data prunes rooms older than retention window while keeping fresh rooms."""
    old_time = timezone_now_minus(days=10)
    fresh_time = timezone_now_minus(days=2)

    old_room = Room.objects.create(code="OLD001")
    Room.objects.filter(id=old_room.id).update(created_at=old_time)

    fresh_room = Room.objects.create(code="NEW001")
    Room.objects.filter(id=fresh_room.id).update(created_at=fresh_time)

    # Dry run should delete nothing
    call_command("delete_room_data", older_than_days=7, dry_run=True)
    assert Room.objects.filter(code="OLD001").exists()
    assert Room.objects.filter(code="NEW001").exists()

    # Actual prune
    call_command("delete_room_data", older_than_days=7)
    assert not Room.objects.filter(code="OLD001").exists()
    assert Room.objects.filter(code="NEW001").exists()


def timezone_now_minus(*, days: int) -> datetime:
    return datetime.now(tz=UTC) - timedelta(days=days)
