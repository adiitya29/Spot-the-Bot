"""Postprocessing and AI leak scrubbing for human-like bot outputs."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from typing import Any

LEAK_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(as an ai|as a language model|i am an ai|im an ai)\b", re.IGNORECASE),
    re.compile(r"\b(chatgpt|openai|anthropic|gemini|llm|deepmind)\b", re.IGNORECASE),
    re.compile(r"\b(system prompt|my instructions|developer mode)\b", re.IGNORECASE),
    re.compile(r"\b(is_bot|bot_persona|style_profile|player_id)\b", re.IGNORECASE),
)

MARKDOWN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\*\*([^*]+)\*\*"),  # bold
    re.compile(r"\*([^*]+)\*"),  # italics
    re.compile(r"`([^`]+)`"),  # inline code
    re.compile(r"^\s*[-*•]\s+", re.MULTILINE),  # bullet points
    re.compile(r"^\s*\d+\.\s+", re.MULTILINE),  # numbered list
)


@dataclass(frozen=True)
class PostprocessResult:
    text: str
    has_leak: bool
    cleaned_length: int


def detect_ai_leak(text: str) -> bool:
    """Return True if text contains recognizable AI giveaways or internal system tokens."""
    return any(pattern.search(text) for pattern in LEAK_PATTERNS)


def strip_markdown(text: str) -> str:
    """Remove markdown bold, italics, code fences, and bullet formatting."""
    cleaned = text
    for pat in MARKDOWN_PATTERNS:
        cleaned = pat.sub(r"\1" if pat.groups > 0 else "", cleaned)
    cleaned = cleaned.strip()
    if (cleaned.startswith('"') and cleaned.endswith('"')) or (
        cleaned.startswith("'") and cleaned.endswith("'")
    ):
        cleaned = cleaned[1:-1].strip()
    return cleaned


def postprocess_bot_message(
    raw_text: str,
    *,
    style_profile: dict[str, Any] | None = None,
    allow_typos: bool = False,
    rng: random.Random | None = None,
) -> PostprocessResult:
    """Clean, humanize, and check bot output against leaks and unnatural formality."""
    if not raw_text:
        return PostprocessResult(text="", has_leak=False, cleaned_length=0)

    if detect_ai_leak(raw_text):
        return PostprocessResult(text="", has_leak=True, cleaned_length=0)

    text = strip_markdown(raw_text)

    # Flatten newlines into spaces (party chat lines are single-line messages)
    text = " ".join(text.split())

    # Limit maximum message length to 280 characters
    if len(text) > 280:
        # Cut at word boundary if possible
        text = text[:280].rsplit(" ", 1)[0]

    profile = style_profile or {}

    # Lowercase first character if room leans heavily lowercase
    if profile.get("lowercase_ratio", 0.8) >= 0.6 and text and text[0].isupper():
        text = text[0].lower() + text[1:]

    # Remove terminal period if room leans away from formal punctuation
    if profile.get("punctuation_ratio", 0.2) <= 0.3 and text.endswith("."):
        text = text.rstrip(".")

    # Optional subtle human typo injection
    if allow_typos and len(text) > 8:
        chooser = rng or random.SystemRandom()
        if chooser.random() < 0.05:  # 5% chance
            idx = chooser.randint(1, len(text) - 2)
            # Swap two adjacent letters
            chars = list(text)
            chars[idx], chars[idx + 1] = chars[idx + 1], chars[idx]
            text = "".join(chars)

    return PostprocessResult(
        text=text,
        has_leak=False,
        cleaned_length=len(text),
    )
