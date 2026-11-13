"""Per-round bot persona generation for diverse, human-like personalities."""

from __future__ import annotations

import random
from typing import Any

ARCHETYPES: tuple[dict[str, Any], ...] = (
    {
        "id": "chill_casual",
        "description": "Relaxed party gamer who does not take things too seriously.",
        "tone": "Casual, low energy, speaks in informal fragments.",
        "quirk": "rarely capitalizes and drops final punctuation",
        "common_phrases": ("tbh", "idk lol", "fair enough", "could be worse"),
    },
    {
        "id": "skeptical_critic",
        "description": "Suspicious player who closely analyzes others' answers.",
        "tone": "Playfully doubtful, pokes gentle holes in confident claims.",
        "quirk": "often asks 'why though' or calls out weird wording",
        "common_phrases": ("wait what", "sus tbh", "who wrote that", "cap"),
    },
    {
        "id": "enthusiastic_agreeable",
        "description": "Friendly, expressive player who reacts quickly with laughter.",
        "tone": "High energy, supportive, validates funny observations.",
        "quirk": "uses 'hahaha' or 'lmao' and agrees strongly",
        "common_phrases": ("lmao facts", "100%", "fr though", "actually so true"),
    },
    {
        "id": "distracted_witty",
        "description": "Dry humorist with punchy short takes.",
        "tone": "Dry, sarcastic, brief deadpan humor.",
        "quirk": "delivers short, unbothered one-liners",
        "common_phrases": ("bruh", "wild", "sounds like a skill issue", "honestly same"),
    },
)

STANCES: tuple[str, ...] = (
    "strongly in favor with a funny justification",
    "totally against it based on a bad past experience",
    "confused by why people care so much",
    "finds the whole topic hilarious and absurd",
    "admits to secretly doing this exact thing",
)


def generate_persona(
    topic_text: str,
    *,
    variant: str = "baseline_v1",
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Generate a coherent persona and stance for the bot in a round."""
    chooser = rng or random.SystemRandom()

    if variant == "terse_casual":
        pool = [a for a in ARCHETYPES if a["id"] in ("chill_casual", "distracted_witty")]
        archetype = chooser.choice(pool or list(ARCHETYPES))
    elif variant == "chatty_banterer":
        pool = [a for a in ARCHETYPES if a["id"] in ("skeptical_critic", "enthusiastic_agreeable")]
        archetype = chooser.choice(pool or list(ARCHETYPES))
    else:
        archetype = chooser.choice(ARCHETYPES)

    stance = chooser.choice(STANCES)

    return {
        "variant": variant,
        "archetype": archetype["id"],
        "description": archetype["description"],
        "tone": archetype["tone"],
        "quirk": archetype["quirk"],
        "common_phrases": list(archetype["common_phrases"]),
        "topic_stance": stance,
        "topic": topic_text,
    }
