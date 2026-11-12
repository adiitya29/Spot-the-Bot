"""Bot app configuration."""

from __future__ import annotations

from django.apps import AppConfig


class BotConfig(AppConfig):
    """Django app configuration for the AI bot engine."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.bot"
