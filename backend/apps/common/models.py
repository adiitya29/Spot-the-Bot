"""Shared append-only event log model."""

from __future__ import annotations

from django.db import models


class Event(models.Model):
    """Append-only per-room state event log used for seq tracking, replays, and debugging."""

    room = models.ForeignKey("rooms.Room", on_delete=models.CASCADE, related_name="events")
    round = models.ForeignKey(
        "game.Round",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="events",
    )
    seq = models.PositiveIntegerField()
    type = models.CharField(max_length=64)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["room_id", "seq"]
        constraints = [
            models.UniqueConstraint(
                fields=["room", "seq"],
                name="unique_event_seq_per_room",
            ),
        ]

    def __str__(self) -> str:
        return f"Event(room={self.room_id}, seq={self.seq}, type={self.type})"
