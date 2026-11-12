"""Rooms app configuration."""

from __future__ import annotations

from django.apps import AppConfig


class RoomsConfig(AppConfig):
    """Django app configuration for rooms and guest players."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.rooms"
