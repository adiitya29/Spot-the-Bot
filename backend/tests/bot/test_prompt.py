"""Tests for system and chat prompt builders."""

from __future__ import annotations

from apps.bot.prompt import (
    FEW_SHOT_EXAMPLES,
    build_bot_answer_prompt,
    build_bot_chat_prompt,
    build_bot_system_prompt,
)


def test_build_bot_system_prompt_includes_core_rules() -> None:
    persona = {
        "tone": "Playful and cynical",
        "quirk": "never uses periods",
    }
    style = {
        "avg_word_count": 6,
        "lowercase_ratio": 0.9,
        "punctuation_ratio": 0.1,
        "slang_used": ["tbh", "lol"],
    }
    prompt = build_bot_system_prompt(
        persona=persona,
        style_profile=style,
        bot_alias="Golden Otter",
    )
    assert 'Your in-game anonymous alias is "Golden Otter"' in prompt
    assert "Playful and cynical" in prompt
    assert "PROBE DEFENSE RULES" in prompt
    assert "FEW-SHOT EXAMPLES" in prompt
    assert len(FEW_SHOT_EXAMPLES) == 8


def test_build_bot_chat_prompt_formats_transcript() -> None:
    recent = [
        ("Teal Badger", "hello everyone"),
        ("Amber Fox", "ready to vote"),
    ]
    prompt = build_bot_chat_prompt(
        topic_text="Favorite movie?",
        recent_messages=recent,
        bot_alias="Golden Otter",
    )
    assert 'ROUND TOPIC: "Favorite movie?"' in prompt
    assert "Teal Badger: hello everyone" in prompt
    assert "Amber Fox: ready to vote" in prompt
    assert "YOUR ALIAS IN THIS ROUND: Golden Otter" in prompt


def test_build_bot_answer_prompt() -> None:
    persona = {"topic_stance": "hates horror movies with a passion"}
    prompt = build_bot_answer_prompt(
        topic_text="What genre is overrated?",
        persona=persona,
        bot_alias="Golden Otter",
    )
    assert 'ROUND TOPIC: "What genre is overrated?"' in prompt
    assert "hates horror movies with a passion" in prompt
