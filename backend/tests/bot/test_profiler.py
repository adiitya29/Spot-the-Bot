"""Tests for human chat style profiler and instruction formatter."""

from __future__ import annotations

from apps.bot.profiler import (
    compute_style_profile,
    format_style_instructions,
    should_recompute_profile,
)


def test_profiler_uses_baseline_when_under_six_messages() -> None:
    messages = ["hey", "hello there", "cool"]
    profile = compute_style_profile(messages)
    assert profile["is_baseline"] is True
    assert profile["message_count"] == 3


def test_profiler_computes_metrics_accurately_with_sufficient_messages() -> None:
    messages = [
        "tbh that was wild 😂",
        "idk what you mean lol",
        "nah not really",
        "Wait I think this is cool.",
        "honestly same fr",
        "bruh no way!",
        "okay fine.",
    ]
    profile = compute_style_profile(messages)

    assert profile["is_baseline"] is False
    assert profile["message_count"] == 7
    assert profile["avg_length"] > 10.0
    assert profile["avg_word_count"] >= 3.0
    # Lowercase starting ratio
    assert profile["lowercase_ratio"] > 0.5
    # Punctuation ratio (two end with period, one with exclamation)
    assert 0.2 < profile["punctuation_ratio"] < 0.8
    # Emojis detected
    assert profile["emoji_ratio"] > 0.0
    # Slang detected
    assert "tbh" in profile["slang_used"]
    assert "lol" in profile["slang_used"]
    assert "bruh" in profile["slang_used"]


def test_should_recompute_profile_thresholds() -> None:
    assert should_recompute_profile(0, 5) is False
    assert should_recompute_profile(0, 6) is True
    assert should_recompute_profile(6, 8) is False
    assert should_recompute_profile(6, 10) is True


def test_format_style_instructions() -> None:
    profile = {
        "avg_word_count": 5.2,
        "lowercase_ratio": 0.85,
        "punctuation_ratio": 0.1,
        "slang_used": ["tbh", "lol", "ngl"],
    }
    instructions = format_style_instructions(profile)
    assert "around 5 words" in instructions
    assert "lowercase" in instructions
    assert "Omit final periods" in instructions
    assert "tbh, lol, ngl" in instructions
