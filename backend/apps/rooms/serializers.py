"""Serializers and validators for rooms and guest players."""

from __future__ import annotations

import unicodedata
from typing import Any

from django.conf import settings
from rest_framework import serializers

from apps.rooms.models import DEFAULT_PHASE_DURATIONS, Player, Room, default_room_config

NICKNAME_MIN_LENGTH = 2
NICKNAME_MAX_LENGTH = 20


def sanitize_nickname(raw: str) -> str:
    """Strip control characters and outer whitespace from a nickname."""
    cleaned = "".join(
        ch for ch in raw if unicodedata.category(ch) not in {"Cc", "Cf"} and ch not in {"\r", "\n"}
    )
    return cleaned.strip()


class NicknameField(serializers.CharField):
    """Validated guest nickname field (2-20 characters, no control chars)."""

    def to_internal_value(self, data: Any) -> str:
        raw = super().to_internal_value(data)
        cleaned = sanitize_nickname(raw)
        if len(cleaned) < NICKNAME_MIN_LENGTH:
            raise serializers.ValidationError(
                f"Nickname must be at least {NICKNAME_MIN_LENGTH} characters."
            )
        if len(cleaned) > NICKNAME_MAX_LENGTH:
            raise serializers.ValidationError(
                f"Nickname must be at most {NICKNAME_MAX_LENGTH} characters."
            )
        return cleaned


class PhaseDurationsSerializer(serializers.Serializer):
    """Optional phase duration overrides (seconds)."""

    answer = serializers.IntegerField(min_value=5, max_value=600, required=False)
    chat = serializers.IntegerField(min_value=5, max_value=600, required=False)
    vote = serializers.IntegerField(min_value=5, max_value=600, required=False)
    reveal = serializers.IntegerField(min_value=5, max_value=600, required=False)


class RoomConfigInputSerializer(serializers.Serializer):
    """Optional room configuration overrides supplied by the host."""

    rounds = serializers.IntegerField(min_value=1, max_value=10, required=False)
    min_humans = serializers.IntegerField(required=False)
    allow_replay_use = serializers.BooleanField(required=False)
    phase_durations = PhaseDurationsSerializer(required=False)

    def validate_min_humans(self, value: int) -> int:
        default_min = getattr(settings, "MIN_HUMANS_DEFAULT", 3)
        min_allowed = int(getattr(settings, "MIN_HUMANS_MIN", default_min))
        max_allowed = int(getattr(settings, "MAX_HUMANS_DEFAULT", 7))
        if value < min_allowed or value > max_allowed:
            raise serializers.ValidationError(
                f"min_humans must be between {min_allowed} and {max_allowed}."
            )
        return value


def merge_room_config(overrides: dict[str, Any] | None) -> dict[str, Any]:
    """Merge validated optional overrides onto default room config."""
    config = default_room_config()
    if not overrides:
        return config
    if "rounds" in overrides:
        config["rounds"] = overrides["rounds"]
    if "min_humans" in overrides:
        config["min_humans"] = overrides["min_humans"]
    if "allow_replay_use" in overrides:
        config["allow_replay_use"] = overrides["allow_replay_use"]
    if "phase_durations" in overrides:
        merged_durations = dict(DEFAULT_PHASE_DURATIONS)
        merged_durations.update(overrides["phase_durations"])
        config["phase_durations"] = merged_durations
    return config


class CreateRoomSerializer(serializers.Serializer):
    """Request payload for creating a new room."""

    nickname = NicknameField(trim_whitespace=False)
    config = RoomConfigInputSerializer(required=False)


class JoinRoomSerializer(serializers.Serializer):
    """Request payload for joining an existing room."""

    nickname = NicknameField(trim_whitespace=False)


class PlayerPublicSerializer(serializers.ModelSerializer):
    """Public player representation (strictly omits is_bot)."""

    class Meta:
        model = Player
        fields = ["id", "nickname", "is_host", "connected", "score", "joined_at"]
        read_only_fields = fields


class RoomPublicSerializer(serializers.ModelSerializer):
    """Public room metadata including capacity and replay-use consent notice."""

    human_count = serializers.SerializerMethodField()
    capacity = serializers.SerializerMethodField()
    min_humans = serializers.IntegerField(read_only=True)
    allow_replay_use = serializers.BooleanField(read_only=True)

    class Meta:
        model = Room
        fields = [
            "code",
            "status",
            "human_count",
            "capacity",
            "min_humans",
            "allow_replay_use",
            "config",
        ]
        read_only_fields = fields

    def get_human_count(self, obj: Room) -> int:
        return obj.players.filter(is_bot=False).count()

    def get_capacity(self, obj: Room) -> int:
        return int(getattr(settings, "MAX_HUMANS_DEFAULT", 7))
