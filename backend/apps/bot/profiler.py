"""Human style profiler analyzing chat metrics to imitate room typing conventions."""

from __future__ import annotations

import re
from typing import Any

COMMON_SLANG: tuple[str, ...] = (
    "lol",
    "lmao",
    "tbh",
    "idk",
    "ngl",
    "fr",
    "lowkey",
    "highkey",
    "bruh",
    "rn",
    "smh",
    "imo",
    "nah",
    "yea",
    "yeah",
    "wild",
    "cap",
)

EMOJI_PATTERN = re.compile(
    r"[\U00010000-\U0010ffff\u2600-\u27ff\u2300-\u23ff]",
    flags=re.UNICODE,
)

MIN_HUMAN_MESSAGES = 6
RECOMPUTE_INTERVAL = 4

DEFAULT_PROFILE: dict[str, Any] = {
    "avg_length": 35.0,
    "avg_word_count": 6.0,
    "lowercase_ratio": 0.8,
    "punctuation_ratio": 0.2,
    "emoji_ratio": 0.1,
    "slang_used": ["lol", "tbh"],
    "message_count": 0,
    "is_baseline": True,
}


def compute_style_profile(messages: list[str]) -> dict[str, Any]:
    """Analyze a collection of human message texts to produce a style profile."""
    cleaned = [m.strip() for m in messages if m and m.strip()]
    count = len(cleaned)

    if count < MIN_HUMAN_MESSAGES:
        res = dict(DEFAULT_PROFILE)
        res["message_count"] = count
        return res

    total_chars = sum(len(m) for m in cleaned)
    words_list = [m.split() for m in cleaned]
    total_words = sum(len(w) for w in words_list)

    lowercase_count = sum(1 for m in cleaned if m[0].islower() or m.islower())
    punct_count = sum(1 for m in cleaned if m[-1] in ".!?")
    emoji_count = sum(1 for m in cleaned if EMOJI_PATTERN.search(m))

    detected_slang: set[str] = set()
    for words in words_list:
        for word in words:
            cleaned_word = re.sub(r"[^\w]", "", word.lower())
            if cleaned_word in COMMON_SLANG:
                detected_slang.add(cleaned_word)

    return {
        "avg_length": round(total_chars / count, 1),
        "avg_word_count": round(total_words / count, 1),
        "lowercase_ratio": round(lowercase_count / count, 2),
        "punctuation_ratio": round(punct_count / count, 2),
        "emoji_ratio": round(emoji_count / count, 2),
        "slang_used": sorted(detected_slang),
        "message_count": count,
        "is_baseline": False,
    }


def should_recompute_profile(last_analyzed_count: int, current_count: int) -> bool:
    """Return True if message count threshold justifies recomputing the profile."""
    if current_count < MIN_HUMAN_MESSAGES:
        return False
    if last_analyzed_count < MIN_HUMAN_MESSAGES:
        return True
    return (current_count - last_analyzed_count) >= RECOMPUTE_INTERVAL


def format_style_instructions(profile: dict[str, Any]) -> str:
    """Produce plain-language prompt guidelines from a style profile."""
    instructions: list[str] = []

    avg_words = profile.get("avg_word_count", 6)
    instructions.append(f"Keep message brief (around {int(avg_words)} words).")

    if profile.get("lowercase_ratio", 0.8) >= 0.6:
        instructions.append("Start with a lowercase letter and avoid rigid capital letters.")

    if profile.get("punctuation_ratio", 0.2) <= 0.3:
        instructions.append("Omit final periods or formal end punctuation.")

    slang = profile.get("slang_used", [])
    if slang:
        slang_sample = ", ".join(slang[:3])
        instructions.append(f"Casual slang used in this room: {slang_sample}.")

    return " ".join(instructions)
