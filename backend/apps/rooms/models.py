"""Database models for game rooms and guest players."""

from __future__ import annotations

import uuid
from typing import Any

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower
from django.utils import timezone


class RoomStatus(models.TextChoices):
    """Lifecycle states of a multiplayer room."""

    LOBBY = "lobby", "Lobby"
    IN_PROGRESS = "in_progress", "In Progress"
    FINISHED = "finished", "Finished"
    ABANDONED = "abandoned", "Abandoned"


DEFAULT_PHASE_DURATIONS: dict[str, int] = {
    "answer": 45,
    "chat": 120,
    "vote": 30,
    "reveal": 12,
}


def default_room_config() -> dict[str, Any]:
    """Return default configurable settings for a newly created room."""
    return {
        "rounds": 3,
        "phase_durations": dict(DEFAULT_PHASE_DURATIONS),
        "min_humans": int(getattr(settings, "MIN_HUMANS_DEFAULT", 3)),
        "allow_replay_use": False,
    }


class Room(models.Model):
    """A multiplayer game room identified by a 6-character code."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=6, unique=True, db_index=True)
    host = models.ForeignKey(
        "rooms.Player",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    status = models.CharField(
        max_length=20,
        choices=RoomStatus.choices,
        default=RoomStatus.LOBBY,
        db_index=True,
    )
    config = models.JSONField(default=default_room_config)
    last_seq = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Room({self.code}, {self.status})"

    @property
    def min_humans(self) -> int:
        """Minimum connected human players required to start a game."""
        return int(self.config.get("min_humans", getattr(settings, "MIN_HUMANS_DEFAULT", 3)))

    @property
    def allow_replay_use(self) -> bool:
        """Whether the host enabled anonymized replay creation."""
        return bool(self.config.get("allow_replay_use", False))


class Player(models.Model):
    """A guest participant (human or covert AI bot) inside a room."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name="players")
    nickname = models.CharField(max_length=20)
    is_bot = models.BooleanField(default=False)
    is_host = models.BooleanField(default=False)
    connected = models.BooleanField(default=False)
    last_seen_at = models.DateTimeField(default=timezone.now)
    joined_at = models.DateTimeField(auto_now_add=True)
    score = models.IntegerField(default=0)

    class Meta:
        ordering = ["joined_at"]
        constraints = [
            models.UniqueConstraint(
                Lower("nickname"),
                "room",
                name="unique_player_nickname_ci_per_room",
            ),
            models.UniqueConstraint(
                fields=["room"],
                condition=Q(is_bot=True),
                name="unique_bot_per_room",
            ),
        ]

    def __str__(self) -> str:
        return f"Player({self.nickname}, room={self.room.code})"
