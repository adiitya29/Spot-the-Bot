"""Unit tests for per-round alias generation and the 40 seeded topics script."""

from __future__ import annotations

import random

import pytest

from apps.game.aliases import COLOR_PALETTE_SIZE, assign_round_aliases
from apps.game.models import Topic, TopicCategory
from scripts.seed_topics import TOPIC_SEEDS, ensure_topics_seeded


def test_assign_round_aliases_is_unique_shuffled_and_deterministic() -> None:
    """Aliases, colors, and display order are unique per round and deterministic per RNG."""
    rng_a = random.Random(42)
    rng_b = random.Random(42)

    seats_a = assign_round_aliases(8, rng=rng_a)
    seats_b = assign_round_aliases(8, rng=rng_b)

    assert seats_a == seats_b
    assert len({s.alias for s in seats_a}) == 8
    assert len({s.color_index for s in seats_a}) == 8
    assert all(0 <= s.color_index < COLOR_PALETTE_SIZE for s in seats_a)
    assert sorted(s.order_index for s in seats_a) == list(range(8))

    with pytest.raises(ValueError):
        assign_round_aliases(COLOR_PALETTE_SIZE + 1)


@pytest.mark.django_db
def test_seed_topics_creates_40_topics_idempotently() -> None:
    """ensure_topics_seeded seeds 40 unique topics across all categories once."""
    Topic.objects.all().delete()
    assert len(TOPIC_SEEDS) == 40

    created_first, total_first = ensure_topics_seeded()
    assert created_first == 40
    assert total_first == 40

    created_second, total_second = ensure_topics_seeded()
    assert created_second == 0
    assert total_second == 40

    categories = set(Topic.objects.values_list("category", flat=True))
    assert categories == {
        TopicCategory.FUNNY,
        TopicCategory.OPINION,
        TopicCategory.STORY,
    }
