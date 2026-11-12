"""Game app configuration."""

from __future__ import annotations

from django.apps import AppConfig


class GameConfig(AppConfig):
    """Django app configuration for game state, scheduler, and WebSocket consumers."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.game"
