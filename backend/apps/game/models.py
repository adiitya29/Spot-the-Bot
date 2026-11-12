"""Game models for topics, rounds, per-round anonymous seats, and messages."""

from __future__ import annotations

import uuid

from django.db import models
from django.db.models import F, Q


class TopicCategory(models.TextChoices):
    """Supported topic prompt categories."""

    FUNNY = "funny", "Funny"
    OPINION = "opinion", "Opinion"
    STORY = "story", "Story"


class Topic(models.Model):
    """Prompt shown to all players at the start of a round."""

    text = models.CharField(max_length=240, unique=True)
    category = models.CharField(
        max_length=20,
        choices=TopicCategory.choices,
        db_index=True,
    )
    active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return f"Topic({self.category}: {self.text[:40]})"


class RoundPhase(models.TextChoices):
    """Server-authoritative phases for each game round."""

    ANSWER = "answer", "Answer"
    CHAT = "chat", "Chat"
    VOTE = "vote", "Vote"
    REVEAL = "reveal", "Reveal"
    DONE = "done", "Done"


class Round(models.Model):
    """Single round within a room's game session."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey("rooms.Room", on_delete=models.CASCADE, related_name="rounds")
    game_index = models.PositiveIntegerField(default=1)
    number = models.PositiveIntegerField()
    topic = models.ForeignKey(Topic, on_delete=models.PROTECT, related_name="rounds")
    phase = models.CharField(
        max_length=16,
        choices=RoundPhase.choices,
        default=RoundPhase.ANSWER,
        db_index=True,
    )
    phase_started_at = models.DateTimeField()
    phase_ends_at = models.DateTimeField()
    answers_revealed_at = models.DateTimeField(null=True, blank=True)
    bot_persona = models.JSONField(default=dict)
    style_profile = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["game_index", "number"]
        constraints = [
            models.UniqueConstraint(
                fields=["room", "game_index", "number"],
                name="unique_round_number_per_game",
            ),
        ]

    def __str__(self) -> str:
        return f"Round(room={self.room_id}, g={self.game_index}, n={self.number}, {self.phase})"


class RoundSeat(models.Model):
    """Anonymous per-round participant seat hiding real nickname and bot identity."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="seats")
    player = models.ForeignKey(
        "rooms.Player",
        on_delete=models.CASCADE,
        related_name="round_seats",
    )
    alias = models.CharField(max_length=40)
    color_index = models.PositiveSmallIntegerField()
    order_index = models.PositiveSmallIntegerField(default=0)
    has_answered = models.BooleanField(default=False)
    ready_to_vote = models.BooleanField(default=False)

    class Meta:
        ordering = ["order_index", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["round", "player"],
                name="unique_seat_player_per_round",
            ),
            models.UniqueConstraint(
                fields=["round", "alias"],
                name="unique_seat_alias_per_round",
            ),
            models.UniqueConstraint(
                fields=["round", "color_index"],
                name="unique_seat_color_per_round",
            ),
        ]

    def __str__(self) -> str:
        return f"RoundSeat({self.alias}, round={self.round_id})"


class MessageKind(models.TextChoices):
    """Classification of participant messages within a round."""

    ANSWER = "answer", "Answer"
    CHAT = "chat", "Chat"


class Message(models.Model):
    """Opening answer or chat message authored by a RoundSeat."""

    id = models.BigAutoField(primary_key=True)
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="messages")
    seat = models.ForeignKey(RoundSeat, on_delete=models.CASCADE, related_name="messages")
    text = models.CharField(max_length=280)
    kind = models.CharField(max_length=16, choices=MessageKind.choices, db_index=True)
    client_msg_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    meta = models.JSONField(default=dict)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["seat", "client_msg_id"],
                condition=Q(client_msg_id__isnull=False),
                name="unique_client_msg_per_seat",
            ),
            models.UniqueConstraint(
                fields=["round", "seat"],
                condition=Q(kind=MessageKind.ANSWER),
                name="unique_answer_per_seat_per_round",
            ),
        ]

    def __str__(self) -> str:
        return f"Message({self.kind}, id={self.id}, seat={self.seat_id})"


class Vote(models.Model):
    """Secret ballot cast by one human RoundSeat during the VOTE phase."""

    id = models.BigAutoField(primary_key=True)
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="votes")
    voter_seat = models.ForeignKey(
        RoundSeat,
        on_delete=models.CASCADE,
        related_name="votes_cast",
    )
    target_seat = models.ForeignKey(
        RoundSeat,
        on_delete=models.CASCADE,
        related_name="votes_received",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["round", "voter_seat"],
                name="unique_vote_per_voter_per_round",
            ),
            models.CheckConstraint(
                condition=~Q(voter_seat=F("target_seat")),
                name="prevent_self_vote",
            ),
        ]

    def __str__(self) -> str:
        return f"Vote(round={self.round_id}, voter={self.voter_seat_id} -> {self.target_seat_id})"


class RoundResult(models.Model):
    """Finalized vote outcome and bot-survival record created on REVEAL."""

    round = models.OneToOneField(
        Round,
        on_delete=models.CASCADE,
        related_name="result",
        primary_key=True,
    )
    bot_seat = models.ForeignKey(
        RoundSeat,
        on_delete=models.PROTECT,
        related_name="bot_round_results",
    )
    votes_for_bot = models.PositiveSmallIntegerField(default=0)
    human_voters = models.PositiveSmallIntegerField(default=0)
    bot_fooled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return (
            f"RoundResult(round={self.round_id}, votes_for_bot={self.votes_for_bot}/"
            f"{self.human_voters}, fooled={self.bot_fooled})"
        )
