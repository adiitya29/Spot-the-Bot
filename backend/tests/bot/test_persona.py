"""Tests for persona generation determinism and structure."""

from __future__ import annotations

import random

from apps.bot.persona import generate_persona


def test_generate_persona_structure() -> None:
    persona = generate_persona("Is cereal soup?", rng=random.Random(42))
    assert "archetype" in persona
    assert "description" in persona
    assert "tone" in persona
    assert "quirk" in persona
    assert isinstance(persona["common_phrases"], list)
    assert "topic_stance" in persona
    assert persona["topic"] == "Is cereal soup?"


def test_generate_persona_is_deterministic_with_injected_rng() -> None:
    p1 = generate_persona("Best pizza topping?", rng=random.Random(1234))
    p2 = generate_persona("Best pizza topping?", rng=random.Random(1234))
    assert p1 == p2


def test_generate_persona_varies_with_different_seeds() -> None:
    p1 = generate_persona("Best pizza topping?", rng=random.Random(1))
    p2 = generate_persona("Best pizza topping?", rng=random.Random(9999))
    # Different seeds should yield different archetype or stance
    assert (p1["archetype"], p1["topic_stance"]) != (p2["archetype"], p2["topic_stance"])
