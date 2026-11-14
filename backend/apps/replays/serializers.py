"""Serializers for public replay cases and solo gameplay."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.replays.models import ReplayCase


class ReplayCaseListSerializer(serializers.ModelSerializer[ReplayCase]):
    """Public listing of approved replays without secret bot identities."""

    solo_accuracy_rate = serializers.FloatField(read_only=True)
    solo_bot_fooled_rate = serializers.FloatField(read_only=True)

    class Meta:
        model = ReplayCase
        fields = [
            "id",
            "room_code",
            "topic_category",
            "topic_text",
            "human_guesses_count",
            "correct_guesses_count",
            "solo_accuracy_rate",
            "solo_bot_fooled_rate",
            "created_at",
        ]
        read_only_fields = fields


class ReplayCaseDetailSerializer(serializers.ModelSerializer[ReplayCase]):
    """Public round replay detail with sanitized transcript (zero bot identity leaks)."""

    solo_accuracy_rate = serializers.FloatField(read_only=True)
    solo_bot_fooled_rate = serializers.FloatField(read_only=True)
    transcript = serializers.SerializerMethodField()

    class Meta:
        model = ReplayCase
        fields = [
            "id",
            "room_code",
            "topic_category",
            "topic_text",
            "transcript",
            "human_guesses_count",
            "correct_guesses_count",
            "solo_accuracy_rate",
            "solo_bot_fooled_rate",
            "created_at",
        ]
        read_only_fields = fields

    def get_transcript(self, obj: ReplayCase) -> dict[str, Any]:
        """Ensure any potential internal bot secrets are stripped from transcript output."""
        data = dict(obj.transcript or {})
        # Defense-in-depth: Remove any bot identifiers
        data.pop("bot_alias", None)
        data.pop("bot_seat_id", None)
        outcome = dict(data.get("outcome", {}))
        outcome.pop("bot_alias", None)
        outcome.pop("bot_seat_id", None)
        data["outcome"] = outcome

        participants = []
        for p in data.get("participants", []):
            clean_p = dict(p)
            clean_p.pop("is_bot", None)
            participants.append(clean_p)
        data["participants"] = participants

        messages = []
        for m in data.get("messages", []):
            clean_m = dict(m)
            clean_m.pop("is_bot", None)
            messages.append(clean_m)
        data["messages"] = messages

        return data


class SoloGuessInputSerializer(serializers.Serializer):
    """Input payload for submitting a solo player's guess."""

    alias = serializers.CharField(
        max_length=64,
        required=True,
        trim_whitespace=True,
        help_text="The seat alias suspected of being the covert AI bot.",
    )
