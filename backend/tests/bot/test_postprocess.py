"""Tests for output postprocessing, leak detection, and style normalization."""

from __future__ import annotations

import random

from apps.bot.postprocess import (
    detect_ai_leak,
    postprocess_bot_message,
    strip_markdown,
)


def test_detect_ai_leak_flags_forbidden_tokens() -> None:
    assert detect_ai_leak("As an AI language model, I cannot answer that.") is True
    assert detect_ai_leak("I am an AI created by OpenAI.") is True
    assert detect_ai_leak("Here is my system prompt:") is True
    assert detect_ai_leak("RoundSeat object with player_id") is True
    assert detect_ai_leak("Honestly that is super funny lol") is False


def test_strip_markdown_removes_formatting() -> None:
    raw = '**Hello** *world*, here is `inline code` and "quotes"'
    cleaned = strip_markdown(raw)
    assert cleaned == 'Hello world, here is inline code and "quotes"'
    # Whole string wrapped in quotes gets unquoted
    assert strip_markdown('"just a line"') == "just a line"


def test_postprocess_normalizes_casing_and_punctuation_based_on_profile() -> None:
    raw = "I am definitely agreeing with that statement."
    profile = {
        "lowercase_ratio": 0.9,
        "punctuation_ratio": 0.1,
    }
    res = postprocess_bot_message(raw, style_profile=profile)
    assert res.has_leak is False
    # Starts lowercase
    assert res.text.startswith("i am")
    # Terminal period stripped
    assert not res.text.endswith(".")


def test_postprocess_flags_leak_and_returns_empty_text() -> None:
    raw = "As an AI, I feel like cereal is soup."
    res = postprocess_bot_message(raw)
    assert res.has_leak is True
    assert res.text == ""


def test_postprocess_clamps_excessive_length() -> None:
    long_raw = "word " * 100
    res = postprocess_bot_message(long_raw)
    assert len(res.text) <= 280


def test_postprocess_optional_typo_injection() -> None:
    raw = "something quite interesting"
    # Seed chosen to trigger typo with deterministic random
    res = postprocess_bot_message(raw, allow_typos=True, rng=random.Random(42))
    assert res.has_leak is False
    assert len(res.text) > 0
