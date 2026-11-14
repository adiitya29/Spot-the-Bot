"""Models for viral replays and solo play."""

from __future__ import annotations

import uuid

from django.db import models


class ReplayCase(models.Model):
    """Consented, anonymized round snapshot published for solo 'Guess the Bot' play."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    round = models.ForeignKey(
        "game.Round",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="replay_cases",
    )
    room_code = models.CharField(max_length=6, db_index=True)
    topic_category = models.CharField(max_length=32, blank=True, default="general")
    topic_text = models.CharField(max_length=255)
    transcript = models.JSONField(
        default=dict,
        help_text="Anonymized round transcript without bot secret tags.",
    )
    bot_alias = models.CharField(
        max_length=64,
        help_text="Alias assigned to the bot (hidden until solo guess is submitted).",
    )
    bot_seat_id = models.CharField(max_length=64, blank=True, default="")
    bot_fooled_original = models.BooleanField(
        default=False,
        help_text="Whether the bot successfully fooled live human voters in this round.",
    )
    human_guesses_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of solo player attempts on this replay.",
    )
    correct_guesses_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of correct solo guesses identifying the bot.",
    )
    is_approved = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Curated / publicly playable status.",
    )
    allow_replay_use = models.BooleanField(
        default=True,
        help_text="Consent flag inherited from Room config at time of creation.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_approved", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"ReplayCase({self.id}, room={self.room_code}, topic={self.topic_text[:30]})"

    @property
    def solo_accuracy_rate(self) -> float:
        """Fraction of solo players who correctly spotted the bot."""
        if self.human_guesses_count == 0:
            return 0.0
        return round(self.correct_guesses_count / self.human_guesses_count, 4)

    @property
    def solo_bot_fooled_rate(self) -> float:
        """Fraction of solo players who were fooled by the bot."""
        if self.human_guesses_count == 0:
            return 0.0
        return round(1.0 - self.solo_accuracy_rate, 4)
