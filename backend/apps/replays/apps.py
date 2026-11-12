"""Replays app configuration."""

from __future__ import annotations

from django.apps import AppConfig


class ReplaysConfig(AppConfig):
    """Django app configuration for replay cases, share cards, and bot stats."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.replays"
