"""Authoritative game state machine covering start_game, ANSWER, CHAT, and transitions."""

from __future__ import annotations

import contextlib
import logging
import random
import unicodedata
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.common.events import append_event, build_envelope, utc_now_ms
from apps.common.locks import room_lock
from apps.game.aliases import assign_round_aliases
from apps.game.models import (
    Message,
    MessageKind,
    Round,
    RoundPhase,
    RoundResult,
    RoundSeat,
    Topic,
    Vote,
)
from apps.game.rate_limits import check_chat_rate_limit
from apps.game.scheduler import cancel_phase_deadline, schedule_phase_deadline
from apps.game.scoring import (
    build_game_over_payload,
    build_reveal_payload,
    finalize_round_scores,
)
from apps.rooms.models import DEFAULT_PHASE_DURATIONS, Player, Room, RoomStatus
from scripts.seed_topics import ensure_topics_seeded

logger = logging.getLogger(__name__)

MAX_GAME_TEXT_LENGTH = 280


class GameTransitionError(Exception):
    """Domain error raised when a game command is invalid for the current state."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def sanitize_game_text(raw: str) -> str:
    """Strip control characters and outer whitespace from answer/chat text."""
    normalized = raw.replace("\r", " ").replace("\n", " ").replace("\t", " ")
    cleaned = "".join(ch for ch in normalized if unicodedata.category(ch) not in {"Cc", "Cf"})
    return cleaned.strip()


def validate_game_text(raw: Any, *, field_label: str = "Message") -> str:
    """Validate answer/chat input (1-280 chars after sanitization)."""
    if not isinstance(raw, str):
        raise GameTransitionError("invalid_payload", f"{field_label} must be a string.")
    cleaned = sanitize_game_text(raw)
    if not cleaned:
        raise GameTransitionError("empty_text", f"{field_label} cannot be empty.")
    if len(cleaned) > MAX_GAME_TEXT_LENGTH:
        raise GameTransitionError(
            "text_too_long",
            f"{field_label} must be at most {MAX_GAME_TEXT_LENGTH} characters.",
        )
    return cleaned


def _phase_duration_seconds(room: Room, phase: str) -> int:
    durations = room.config.get("phase_durations") or {}
    default_val = DEFAULT_PHASE_DURATIONS.get(phase, 30)
    return int(durations.get(phase, default_val))


def _serialize_lobby_player(player: Player) -> dict[str, Any]:
    return {
        "id": str(player.id),
        "nickname": player.nickname,
        "is_host": player.is_host,
        "connected": player.connected,
        "score": player.score,
    }


def serialize_topic(topic: Topic) -> dict[str, Any]:
    """Serialize Topic publicly."""
    return {
        "id": topic.id,
        "text": topic.text,
        "category": topic.category,
    }


def serialize_seat(seat: RoundSeat) -> dict[str, Any]:
    """Serialize RoundSeat publicly (never includes player_id or is_bot)."""
    return {
        "seat_id": str(seat.id),
        "alias": seat.alias,
        "color_index": seat.color_index,
    }


def serialize_answer(msg: Message) -> dict[str, Any]:
    """Serialize an opening ANSWER message publicly without meta/player_id."""
    return {
        "seat_id": str(msg.seat_id),
        "alias": msg.seat.alias,
        "color_index": msg.seat.color_index,
        "text": msg.text,
    }


def serialize_chat_message(msg: Message, *, round_id: UUID) -> dict[str, Any]:
    """Serialize a CHAT message publicly without meta/player_id."""
    return {
        "id": msg.id,
        "round_id": str(round_id),
        "seat_id": str(msg.seat_id),
        "alias": msg.seat.alias,
        "color_index": msg.seat.color_index,
        "text": msg.text,
        "client_msg_id": str(msg.client_msg_id) if msg.client_msg_id else None,
        "created_at": int(msg.created_at.timestamp() * 1000),
    }


def _select_topic(
    room: Room,
    *,
    game_index: int,
    rng: random.Random | None = None,
) -> Topic:
    if not Topic.objects.filter(active=True).exists():
        ensure_topics_seeded()

    used_topic_ids = set(
        Round.objects.filter(room=room, game_index=game_index).values_list("topic_id", flat=True)
    )
    candidates = list(Topic.objects.filter(active=True).exclude(id__in=used_topic_ids))
    if not candidates:
        candidates = list(Topic.objects.filter(active=True))
    if not candidates:
        raise GameTransitionError("no_topics", "No active topics configured.")
    chooser = rng or random.SystemRandom()
    return chooser.choice(candidates)


def _group_send_room(room_code: str, message: dict[str, Any]) -> None:
    layer = get_channel_layer()
    if layer is None:
        return
    try:
        async_to_sync(layer.group_send)(f"room_{room_code}", message)
    except Exception:
        logger.exception("Failed dispatching WS message to room=%s", room_code)


def _phase_changed_payload(
    room: Room,
    round_obj: Round,
    seats: list[RoundSeat],
    *,
    now: datetime,
) -> dict[str, Any]:
    return {
        "round_id": str(round_obj.id),
        "game_index": round_obj.game_index,
        "round_number": round_obj.number,
        "total_rounds": int(room.config.get("rounds", 3)),
        "phase": round_obj.phase,
        "ends_at": int(round_obj.phase_ends_at.timestamp() * 1000),
        "server_time": int(now.timestamp() * 1000),
        "topic": serialize_topic(round_obj.topic),
        "seats": [serialize_seat(seat) for seat in seats],
    }


def _ensure_bot_answer_before_chat(round_obj: Round, *, rng: random.Random | None = None) -> None:
    bot_seat = round_obj.seats.select_related("player").filter(player__is_bot=True).first()
    if bot_seat is None:
        return
    if Message.objects.filter(round=round_obj, seat=bot_seat, kind=MessageKind.ANSWER).exists():
        return
    from apps.bot.engine import generate_bot_answer

    text = generate_bot_answer(round_obj, rng=rng)
    Message.objects.create(
        round=round_obj,
        seat=bot_seat,
        text=text,
        kind=MessageKind.ANSWER,
        meta={"source": "bot_engine_v1"},
    )
    bot_seat.has_answered = True
    bot_seat.save(update_fields=["has_answered"])


def _get_or_create_bot_player(room: Room) -> Player:
    bot_player = room.players.filter(is_bot=True).first()
    if bot_player is None:
        bot_player = Player.objects.create(
            room=room,
            nickname="Bot",
            is_bot=True,
            is_host=False,
            connected=True,
        )
    return bot_player


def _create_round_with_seats(
    room: Room,
    *,
    game_index: int,
    round_number: int,
    current_now: datetime,
    humans: list[Player] | None = None,
    rng: random.Random | None = None,
) -> tuple[Round, list[RoundSeat], datetime]:
    """Create a new Round in ANSWER phase with shuffled per-round human + bot seats."""
    human_list = (
        humans
        if humans is not None
        else list(room.players.filter(is_bot=False, connected=True).order_by("joined_at"))
    )
    if not human_list:
        human_list = list(room.players.filter(is_bot=False).order_by("joined_at"))

    bot_player = _get_or_create_bot_player(room)
    topic = _select_topic(room, game_index=game_index, rng=rng)
    answer_seconds = _phase_duration_seconds(room, RoundPhase.ANSWER)
    ends_at = current_now + timedelta(seconds=answer_seconds)

    from apps.bot.persona import generate_persona

    persona = generate_persona(topic.text, rng=rng)

    round_obj = Round.objects.create(
        room=room,
        game_index=game_index,
        number=round_number,
        topic=topic,
        phase=RoundPhase.ANSWER,
        phase_started_at=current_now,
        phase_ends_at=ends_at,
        bot_persona=persona,
    )

    participants: list[Player] = [*human_list, bot_player]
    aliases = assign_round_aliases(len(participants), rng=rng)
    seats_to_create = [
        RoundSeat(
            round=round_obj,
            player=participant,
            alias=assigned.alias,
            color_index=assigned.color_index,
            order_index=assigned.order_index,
        )
        for participant, assigned in zip(participants, aliases, strict=True)
    ]
    RoundSeat.objects.bulk_create(seats_to_create)
    seats = list(round_obj.seats.order_by("order_index", "id"))
    return round_obj, seats, ends_at


def start_game(
    room_id: UUID,
    triggered_by_player_id: UUID,
    *,
    clock: Callable[[], datetime] | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Transition a room from LOBBY to Round 1 ANSWER phase."""
    now_fn = clock or timezone.now
    current_now = now_fn()

    with room_lock(room_id), transaction.atomic():
        room = Room.objects.select_for_update().get(id=room_id)
        if room.status != RoomStatus.LOBBY:
            raise GameTransitionError("invalid_phase", "Game has already started.")

        host = Player.objects.filter(
            id=triggered_by_player_id,
            room=room,
            is_bot=False,
        ).first()
        if host is None or not host.is_host:
            raise GameTransitionError("not_host", "Only the room host can start the game.")

        connected_humans = list(
            room.players.filter(is_bot=False, connected=True).order_by("joined_at")
        )
        if len(connected_humans) < room.min_humans:
            raise GameTransitionError(
                "not_enough_players",
                f"Need at least {room.min_humans} connected players to start.",
            )

        last_game_index = (
            room.rounds.order_by("-game_index").values_list("game_index", flat=True).first() or 0
        )
        game_index = last_game_index + 1

        room.status = RoomStatus.IN_PROGRESS
        room.started_at = current_now
        room.finished_at = None
        room.save(update_fields=["status", "started_at", "finished_at"])

        round_obj, seats, ends_at = _create_round_with_seats(
            room,
            game_index=game_index,
            round_number=1,
            current_now=current_now,
            humans=connected_humans,
            rng=rng,
        )

        payload = _phase_changed_payload(room, round_obj, seats, now=current_now)
        event = append_event(room.id, "phase_changed", payload, round_id=round_obj.id)
        envelope = build_envelope("phase_changed", payload, seq=event.seq)

        def _after_commit() -> None:
            schedule_phase_deadline(round_obj.id, RoundPhase.ANSWER, ends_at)
            _group_send_room(
                room.code,
                {
                    "type": "room.round_started",
                    "envelope": envelope,
                },
            )

        transaction.on_commit(_after_commit)
        return envelope


def submit_answer(
    room_id: UUID,
    player_id: UUID,
    raw_text: Any,
    *,
    clock: Callable[[], datetime] | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Persist a player's answer during ANSWER; advance early to CHAT if all humans answered."""
    cleaned = validate_game_text(raw_text, field_label="Answer")
    now_fn = clock or timezone.now
    current_now = now_fn()

    should_advance = False
    round_id: UUID

    with room_lock(room_id), transaction.atomic():
        room = Room.objects.select_for_update().get(id=room_id)
        if room.status != RoomStatus.IN_PROGRESS:
            raise GameTransitionError("invalid_phase", "Room is not in an active round.")

        round_obj = (
            Round.objects.select_for_update()
            .filter(room=room)
            .order_by("-game_index", "-number")
            .first()
        )
        if round_obj is None or round_obj.phase != RoundPhase.ANSWER:
            raise GameTransitionError("invalid_phase", "Answer submission is closed.")

        seat = (
            RoundSeat.objects.select_for_update()
            .filter(
                round=round_obj,
                player_id=player_id,
                player__is_bot=False,
            )
            .first()
        )
        if seat is None:
            raise GameTransitionError("not_seated", "You are not seated in this round.")

        if (
            seat.has_answered
            or Message.objects.filter(
                round=round_obj,
                seat=seat,
                kind=MessageKind.ANSWER,
            ).exists()
        ):
            raise GameTransitionError("already_answered", "You already submitted an answer.")

        try:
            Message.objects.create(
                round=round_obj,
                seat=seat,
                text=cleaned,
                kind=MessageKind.ANSWER,
            )
        except IntegrityError as exc:
            raise GameTransitionError(
                "already_answered",
                "You already submitted an answer.",
            ) from exc

        seat.has_answered = True
        seat.save(update_fields=["has_answered"])

        unanswered_humans = round_obj.seats.filter(
            player__is_bot=False,
            has_answered=False,
        ).exists()
        should_advance = not unanswered_humans
        round_id = round_obj.id

    if should_advance:
        advance_phase(
            round_id,
            expected_phase=RoundPhase.ANSWER,
            reason="all_answered",
            clock=lambda: current_now,
            rng=rng,
        )

    return {"round_id": str(round_id), "seat_id": str(seat.id), "all_answered": should_advance}


def send_chat_message(
    room_id: UUID,
    player_id: UUID,
    raw_text: Any,
    *,
    client_msg_id: str | None = None,
    bypass_rate_limit: bool = False,
) -> dict[str, Any]:
    """Validate, rate-limit, deduplicate, persist, and broadcast a CHAT message."""
    cleaned = validate_game_text(raw_text, field_label="Message")

    parsed_client_id: UUID | None = None
    if client_msg_id is not None:
        if not isinstance(client_msg_id, str):
            raise GameTransitionError("invalid_client_id", "Invalid client_msg_id.")
        try:
            parsed_client_id = UUID(client_msg_id)
        except ValueError as exc:
            raise GameTransitionError("invalid_client_id", "Invalid client_msg_id.") from exc

    with room_lock(room_id), transaction.atomic():
        room = Room.objects.select_for_update().get(id=room_id)
        if room.status != RoomStatus.IN_PROGRESS:
            raise GameTransitionError("invalid_phase", "Room is not in an active round.")

        round_obj = (
            Round.objects.select_for_update()
            .filter(room=room)
            .order_by("-game_index", "-number")
            .first()
        )
        if round_obj is None or round_obj.phase != RoundPhase.CHAT:
            raise GameTransitionError("invalid_phase", "Chat is only open during the CHAT phase.")

        seat = (
            RoundSeat.objects.select_related("player")
            .filter(round=round_obj, player_id=player_id, player__is_bot=False)
            .first()
        )
        if seat is None:
            raise GameTransitionError("not_seated", "You are not seated in this round.")

        if parsed_client_id is not None:
            existing = Message.objects.filter(
                seat=seat,
                client_msg_id=parsed_client_id,
            ).first()
            if existing is not None:
                return build_envelope(
                    "chat_message",
                    serialize_chat_message(existing, round_id=round_obj.id),
                    seq=None,
                )

        if not bypass_rate_limit:
            rate_result = check_chat_rate_limit(room_id, player_id)
            if not rate_result.allowed:
                raise GameTransitionError(
                    "rate_limited",
                    "You're sending messages too fast. Slow down a bit.",
                )

        try:
            msg = Message.objects.create(
                round=round_obj,
                seat=seat,
                text=cleaned,
                kind=MessageKind.CHAT,
                client_msg_id=parsed_client_id,
            )
        except IntegrityError:
            if parsed_client_id is not None:
                existing = Message.objects.filter(
                    seat=seat,
                    client_msg_id=parsed_client_id,
                ).first()
                if existing is not None:
                    return build_envelope(
                        "chat_message",
                        serialize_chat_message(existing, round_id=round_obj.id),
                        seq=None,
                    )
            raise
        payload = serialize_chat_message(msg, round_id=round_obj.id)
        event = append_event(room.id, "chat_message", payload, round_id=round_obj.id)
        envelope = build_envelope("chat_message", payload, seq=event.seq)

        def _after_commit() -> None:
            _group_send_room(
                room.code,
                {
                    "type": "room.event",
                    "sender_channel": "",
                    "envelope": envelope,
                },
            )
            if not seat.player.is_bot:
                with contextlib.suppress(Exception):
                    from apps.bot.tasks import bot_trigger_on_message

                    bot_trigger_on_message.delay(str(round_obj.id), cleaned)

        transaction.on_commit(_after_commit)
        return envelope


def mark_ready_to_vote(
    room_id: UUID,
    player_id: UUID,
    *,
    clock: Callable[[], datetime] | None = None,
    rng: random.Random | None = None,
) -> bool:
    """Mark a human seat ready to vote in CHAT; advance early to VOTE if all humans are ready."""
    now_fn = clock or timezone.now
    current_now = now_fn()
    should_advance = False
    round_id: UUID

    with room_lock(room_id), transaction.atomic():
        room = Room.objects.select_for_update().get(id=room_id)
        round_obj = (
            Round.objects.select_for_update()
            .filter(room=room)
            .order_by("-game_index", "-number")
            .first()
        )
        if room.status != RoomStatus.IN_PROGRESS or round_obj is None:
            raise GameTransitionError("invalid_phase", "Room is not in an active round.")
        if round_obj.phase != RoundPhase.CHAT:
            raise GameTransitionError("invalid_phase", "Ready-to-vote is only open during CHAT.")

        seat = (
            RoundSeat.objects.select_for_update()
            .filter(
                round=round_obj,
                player_id=player_id,
                player__is_bot=False,
            )
            .first()
        )
        if seat is None:
            raise GameTransitionError("not_seated", "You are not seated in this round.")

        if not seat.ready_to_vote:
            seat.ready_to_vote = True
            seat.save(update_fields=["ready_to_vote"])

        waiting = round_obj.seats.filter(player__is_bot=False, ready_to_vote=False).exists()
        should_advance = not waiting
        round_id = round_obj.id

    if should_advance:
        advance_phase(
            round_id,
            expected_phase=RoundPhase.CHAT,
            reason="all_ready",
            clock=lambda: current_now,
            rng=rng,
        )
    return should_advance


def cast_vote(
    room_id: UUID,
    player_id: UUID,
    raw_target_seat_id: Any,
    *,
    clock: Callable[[], datetime] | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Cast a human ballot during VOTE; advance early to REVEAL when all humans vote."""
    if not isinstance(raw_target_seat_id, str):
        raise GameTransitionError("invalid_target", "A valid target seat ID is required.")
    try:
        target_seat_uuid = UUID(raw_target_seat_id)
    except ValueError as exc:
        raise GameTransitionError("invalid_target", "Invalid target seat ID.") from exc

    now_fn = clock or timezone.now
    current_now = now_fn()
    should_advance = False
    round_id: UUID

    with room_lock(room_id), transaction.atomic():
        room = Room.objects.select_for_update().get(id=room_id)
        round_obj = (
            Round.objects.select_for_update()
            .filter(room=room)
            .order_by("-game_index", "-number")
            .first()
        )
        if room.status != RoomStatus.IN_PROGRESS or round_obj is None:
            raise GameTransitionError("invalid_phase", "Room is not in an active round.")
        if round_obj.phase != RoundPhase.VOTE:
            raise GameTransitionError("invalid_phase", "Voting is only open during the VOTE phase.")

        voter_seat = (
            RoundSeat.objects.select_for_update()
            .filter(
                round=round_obj,
                player_id=player_id,
                player__is_bot=False,
            )
            .first()
        )
        if voter_seat is None:
            raise GameTransitionError("not_seated", "You are not seated in this round.")

        target_seat = RoundSeat.objects.filter(round=round_obj, id=target_seat_uuid).first()
        if target_seat is None:
            raise GameTransitionError("invalid_target", "Selected player is not in this round.")

        if target_seat.id == voter_seat.id:
            raise GameTransitionError("self_vote", "You cannot vote for yourself.")

        if Vote.objects.filter(round=round_obj, voter_seat=voter_seat).exists():
            raise GameTransitionError("already_voted", "You have already locked in your vote.")

        try:
            Vote.objects.create(
                round=round_obj,
                voter_seat=voter_seat,
                target_seat=target_seat,
            )
        except IntegrityError as exc:
            raise GameTransitionError(
                "already_voted",
                "You have already locked in your vote.",
            ) from exc

        votes_cast = Vote.objects.filter(
            round=round_obj,
            voter_seat__player__is_bot=False,
        ).count()
        total_humans = round_obj.seats.filter(player__is_bot=False).count()
        should_advance = votes_cast >= total_humans
        round_id = round_obj.id

        progress_payload = {
            "round_id": str(round_obj.id),
            "votes_cast": votes_cast,
            "total_humans": total_humans,
        }
        event = append_event(room.id, "vote_progress", progress_payload, round_id=round_obj.id)
        envelope = build_envelope("vote_progress", progress_payload, seq=event.seq)

        def _after_commit() -> None:
            _group_send_room(
                room.code,
                {
                    "type": "room.event",
                    "sender_channel": "",
                    "envelope": envelope,
                },
            )

        transaction.on_commit(_after_commit)

    if should_advance:
        advance_phase(
            round_id,
            expected_phase=RoundPhase.VOTE,
            reason="all_voted",
            clock=lambda: current_now,
            rng=rng,
        )

    return {
        "votes_cast": votes_cast,
        "total_humans": total_humans,
        "all_voted": should_advance,
        "envelope": envelope,
    }


def play_again(
    room_id: UUID,
    triggered_by_player_id: UUID,
    *,
    clock: Callable[[], datetime] | None = None,
) -> dict[str, Any]:
    """Reset a FINISHED room back to LOBBY for a fresh rematch while preserving history."""
    now_fn = clock or timezone.now
    current_now = now_fn()

    with room_lock(room_id), transaction.atomic():
        room = Room.objects.select_for_update().get(id=room_id)
        if room.status != RoomStatus.FINISHED:
            raise GameTransitionError(
                "invalid_phase",
                "You can only play again after the current game finishes.",
            )

        host = Player.objects.filter(
            id=triggered_by_player_id,
            room=room,
            is_bot=False,
        ).first()
        if host is None or not host.is_host:
            raise GameTransitionError("not_host", "Only the room host can start a new game.")

        last_game_index = (
            room.rounds.order_by("-game_index").values_list("game_index", flat=True).first() or 0
        )

        room.status = RoomStatus.LOBBY
        room.started_at = None
        room.finished_at = None
        room.save(update_fields=["status", "started_at", "finished_at"])

        Player.objects.filter(room=room).update(score=0)

        payload = {
            "round_id": None,
            "game_index": last_game_index,
            "round_number": 0,
            "total_rounds": int(room.config.get("rounds", 3)),
            "phase": "lobby",
            "ends_at": None,
            "server_time": int(current_now.timestamp() * 1000),
            "topic": None,
            "seats": [],
        }
        event = append_event(room.id, "phase_changed", payload)
        envelope = build_envelope("phase_changed", payload, seq=event.seq)

        def _after_commit() -> None:
            _group_send_room(
                room.code,
                {
                    "type": "room.round_started",
                    "envelope": envelope,
                },
            )

        transaction.on_commit(_after_commit)
        return envelope


def advance_phase(
    round_id: UUID,
    *,
    expected_phase: str | None = None,
    reason: str = "timeout",
    clock: Callable[[], datetime] | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any] | None:
    """Advance an active Round idempotently to its next phase.

    Returns the emitted envelopes when a transition occurs, or None if `expected_phase`
    no longer matches (safe idempotent double-delivery handling).
    """
    now_fn = clock or timezone.now
    current_now = now_fn()

    round_lookup = Round.objects.filter(id=round_id).values("room_id").first()
    if round_lookup is None:
        return None
    room_id: UUID = round_lookup["room_id"]

    with room_lock(room_id), transaction.atomic():
        room = Room.objects.select_for_update().get(id=room_id)
        round_obj = (
            Round.objects.select_for_update()
            .select_related("topic")
            .filter(id=round_id, room=room)
            .first()
        )
        if round_obj is None:
            return None
        if expected_phase is not None and round_obj.phase != expected_phase:
            return None

        seats = list(round_obj.seats.order_by("order_index", "id"))
        emitted: list[dict[str, Any]] = []
        dispatches: list[dict[str, Any]] = []
        old_phase = round_obj.phase
        new_phase_value: str = round_obj.phase
        next_deadline: tuple[UUID, str, datetime] | None = None

        if round_obj.phase == RoundPhase.ANSWER:
            _ensure_bot_answer_before_chat(round_obj, rng=rng)
            answer_msgs = list(
                Message.objects.select_related("seat")
                .filter(round=round_obj, kind=MessageKind.ANSWER)
                .order_by("seat__order_index", "seat_id")
            )
            answers_payload = {
                "round_id": str(round_obj.id),
                "answers": [serialize_answer(msg) for msg in answer_msgs],
            }
            ev_answers = append_event(
                room.id,
                "answers_revealed",
                answers_payload,
                round_id=round_obj.id,
            )
            env_answers = build_envelope("answers_revealed", answers_payload, seq=ev_answers.seq)
            emitted.append(env_answers)
            dispatches.append({"type": "room.event", "sender_channel": "", "envelope": env_answers})

            chat_seconds = _phase_duration_seconds(room, RoundPhase.CHAT)
            ends_at = current_now + timedelta(seconds=chat_seconds)
            round_obj.phase = RoundPhase.CHAT
            round_obj.answers_revealed_at = current_now
            round_obj.phase_started_at = current_now
            round_obj.phase_ends_at = ends_at
            round_obj.save(
                update_fields=[
                    "phase",
                    "answers_revealed_at",
                    "phase_started_at",
                    "phase_ends_at",
                ]
            )
            phase_payload = _phase_changed_payload(room, round_obj, seats, now=current_now)
            ev_phase = append_event(
                room.id,
                "phase_changed",
                phase_payload,
                round_id=round_obj.id,
            )
            env_phase = build_envelope("phase_changed", phase_payload, seq=ev_phase.seq)
            emitted.append(env_phase)
            dispatches.append({"type": "room.event", "sender_channel": "", "envelope": env_phase})
            new_phase_value = RoundPhase.CHAT
            next_deadline = (round_obj.id, RoundPhase.CHAT, ends_at)

        elif round_obj.phase == RoundPhase.CHAT:
            vote_seconds = _phase_duration_seconds(room, RoundPhase.VOTE)
            ends_at = current_now + timedelta(seconds=vote_seconds)
            round_obj.phase = RoundPhase.VOTE
            round_obj.phase_started_at = current_now
            round_obj.phase_ends_at = ends_at
            round_obj.save(update_fields=["phase", "phase_started_at", "phase_ends_at"])

            phase_payload = _phase_changed_payload(room, round_obj, seats, now=current_now)
            ev_phase = append_event(
                room.id,
                "phase_changed",
                phase_payload,
                round_id=round_obj.id,
            )
            env_phase = build_envelope("phase_changed", phase_payload, seq=ev_phase.seq)
            emitted.append(env_phase)
            dispatches.append({"type": "room.event", "sender_channel": "", "envelope": env_phase})
            new_phase_value = RoundPhase.VOTE
            next_deadline = (round_obj.id, RoundPhase.VOTE, ends_at)

        elif round_obj.phase == RoundPhase.VOTE:
            reveal_payload = finalize_round_scores(round_obj)
            reveal_seconds = _phase_duration_seconds(room, RoundPhase.REVEAL)
            ends_at = current_now + timedelta(seconds=reveal_seconds)
            round_obj.phase = RoundPhase.REVEAL
            round_obj.phase_started_at = current_now
            round_obj.phase_ends_at = ends_at
            round_obj.save(update_fields=["phase", "phase_started_at", "phase_ends_at"])

            ev_reveal = append_event(
                room.id,
                "reveal",
                reveal_payload,
                round_id=round_obj.id,
            )
            env_reveal = build_envelope("reveal", reveal_payload, seq=ev_reveal.seq)
            emitted.append(env_reveal)
            dispatches.append({"type": "room.event", "sender_channel": "", "envelope": env_reveal})

            phase_payload = _phase_changed_payload(room, round_obj, seats, now=current_now)
            ev_phase = append_event(
                room.id,
                "phase_changed",
                phase_payload,
                round_id=round_obj.id,
            )
            env_phase = build_envelope("phase_changed", phase_payload, seq=ev_phase.seq)
            emitted.append(env_phase)
            dispatches.append({"type": "room.event", "sender_channel": "", "envelope": env_phase})
            new_phase_value = RoundPhase.REVEAL
            next_deadline = (round_obj.id, RoundPhase.REVEAL, ends_at)

        elif round_obj.phase == RoundPhase.REVEAL:
            round_obj.phase = RoundPhase.DONE
            round_obj.phase_ends_at = current_now
            round_obj.save(update_fields=["phase", "phase_ends_at"])

            total_rounds = int(room.config.get("rounds", 3))
            if round_obj.number < total_rounds:
                next_round, next_seats, ends_at = _create_round_with_seats(
                    room,
                    game_index=round_obj.game_index,
                    round_number=round_obj.number + 1,
                    current_now=current_now,
                    rng=rng,
                )
                phase_payload = _phase_changed_payload(
                    room, next_round, next_seats, now=current_now
                )
                ev_phase = append_event(
                    room.id,
                    "phase_changed",
                    phase_payload,
                    round_id=next_round.id,
                )
                env_phase = build_envelope("phase_changed", phase_payload, seq=ev_phase.seq)
                emitted.append(env_phase)
                dispatches.append({"type": "room.round_started", "envelope": env_phase})
                new_phase_value = RoundPhase.ANSWER
                next_deadline = (next_round.id, RoundPhase.ANSWER, ends_at)
            else:
                room.status = RoomStatus.FINISHED
                room.finished_at = current_now
                room.save(update_fields=["status", "finished_at"])

                phase_payload = _phase_changed_payload(room, round_obj, seats, now=current_now)
                ev_phase = append_event(
                    room.id,
                    "phase_changed",
                    phase_payload,
                    round_id=round_obj.id,
                )
                env_phase = build_envelope("phase_changed", phase_payload, seq=ev_phase.seq)
                emitted.append(env_phase)
                dispatches.append(
                    {"type": "room.event", "sender_channel": "", "envelope": env_phase}
                )

                game_over_payload = build_game_over_payload(room, game_index=round_obj.game_index)
                ev_over = append_event(
                    room.id,
                    "game_over",
                    game_over_payload,
                    round_id=round_obj.id,
                )
                env_over = build_envelope("game_over", game_over_payload, seq=ev_over.seq)
                emitted.append(env_over)
                dispatches.append(
                    {"type": "room.event", "sender_channel": "", "envelope": env_over}
                )
                new_phase_value = RoundPhase.DONE
        else:
            return None

        def _after_commit() -> None:
            cancel_phase_deadline(round_obj.id, old_phase)
            if next_deadline is not None:
                schedule_phase_deadline(next_deadline[0], next_deadline[1], next_deadline[2])
            for dispatch_msg in dispatches:
                _group_send_room(room.code, dispatch_msg)

        transaction.on_commit(_after_commit)
        logger.debug(
            "Advanced room=%s round=%s %s -> %s (%s)",
            room.code,
            round_obj.id,
            old_phase,
            new_phase_value,
            reason,
        )
        return {"new_phase": new_phase_value, "envelopes": emitted}


def get_active_seat_for_player(room_id: UUID, player_id: UUID) -> tuple[Round, RoundSeat] | None:
    """Return active (Round, RoundSeat) for player in an in-progress room, if any."""
    round_obj = (
        Round.objects.filter(room_id=room_id, room__status=RoomStatus.IN_PROGRESS)
        .order_by("-game_index", "-number")
        .first()
    )
    if round_obj is None:
        return None
    seat = RoundSeat.objects.filter(round=round_obj, player_id=player_id).first()
    if seat is None:
        return None
    return round_obj, seat


def build_room_snapshot_payload(
    room_id: UUID,
    player_id: UUID,
    *,
    present_ids: set[str] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Build unicast room_snapshot `(seq, payload)` including only recipient's `my_seat_id`."""
    room = Room.objects.get(id=room_id)
    humans_qs = room.players.filter(is_bot=False)
    if room.status == RoomStatus.LOBBY and present_ids is not None:
        humans_qs = humans_qs.filter(id__in=set(present_ids) | {str(player_id)})

    roster = [_serialize_lobby_player(p) for p in humans_qs]
    connected_count = room.players.filter(is_bot=False, connected=True).count()
    can_start = room.status == RoomStatus.LOBBY and connected_count >= room.min_humans

    payload: dict[str, Any] = {
        "code": room.code,
        "status": room.status,
        "phase": "lobby" if room.status == RoomStatus.LOBBY else room.status,
        "min_humans": room.min_humans,
        "capacity": int(getattr(settings, "MAX_HUMANS_DEFAULT", 7)),
        "allow_replay_use": room.allow_replay_use,
        "can_start": can_start,
        "my_player_id": str(player_id),
        "server_time": utc_now_ms(),
        "roster": roster,
    }

    if room.status != RoomStatus.LOBBY:
        active_round = (
            Round.objects.select_related("topic")
            .filter(room=room)
            .order_by("-game_index", "-number")
            .first()
        )
        if active_round is not None:
            seats = list(active_round.seats.order_by("order_index", "id"))
            my_seat = next((s for s in seats if s.player_id == player_id), None)
            my_answer_msg = (
                Message.objects.filter(
                    round=active_round,
                    seat=my_seat,
                    kind=MessageKind.ANSWER,
                ).first()
                if my_seat is not None
                else None
            )
            answers: list[dict[str, Any]] = []
            if active_round.phase != RoundPhase.ANSWER:
                answers = [
                    serialize_answer(m)
                    for m in Message.objects.select_related("seat")
                    .filter(round=active_round, kind=MessageKind.ANSWER)
                    .order_by("seat__order_index", "seat_id")
                ]
            messages = [
                serialize_chat_message(m, round_id=active_round.id)
                for m in Message.objects.select_related("seat")
                .filter(round=active_round, kind=MessageKind.CHAT)
                .order_by("id")
            ]

            total_humans = active_round.seats.filter(player__is_bot=False).count()
            votes_cast = Vote.objects.filter(
                round=active_round,
                voter_seat__player__is_bot=False,
            ).count()
            my_vote = (
                Vote.objects.filter(round=active_round, voter_seat=my_seat).first()
                if my_seat is not None
                else None
            )

            reveal_payload: dict[str, Any] | None = None
            if (
                active_round.phase in {RoundPhase.REVEAL, RoundPhase.DONE}
                and RoundResult.objects.filter(round=active_round).exists()
            ):
                reveal_payload = build_reveal_payload(active_round)

            game_over_payload: dict[str, Any] | None = None
            if room.status == RoomStatus.FINISHED:
                game_over_payload = build_game_over_payload(
                    room,
                    game_index=active_round.game_index,
                )

            payload.update(
                {
                    "phase": active_round.phase,
                    "round_id": str(active_round.id),
                    "round_number": active_round.number,
                    "total_rounds": int(room.config.get("rounds", 3)),
                    "ends_at": int(active_round.phase_ends_at.timestamp() * 1000),
                    "topic": serialize_topic(active_round.topic),
                    "seats": [serialize_seat(s) for s in seats],
                    "my_seat_id": str(my_seat.id) if my_seat is not None else None,
                    "has_answered": bool(my_seat and my_seat.has_answered),
                    "my_answer": my_answer_msg.text if my_answer_msg is not None else None,
                    "ready_to_vote": bool(my_seat and my_seat.ready_to_vote),
                    "answers": answers,
                    "messages": messages,
                    "votes_cast": votes_cast,
                    "total_humans": total_humans,
                    "my_vote_target_seat_id": (
                        str(my_vote.target_seat_id) if my_vote is not None else None
                    ),
                    "reveal": reveal_payload,
                    "game_over": game_over_payload,
                }
            )

    return room.last_seq, payload
