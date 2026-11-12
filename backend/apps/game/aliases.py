"""Per-round anonymous alias and color generation."""

from __future__ import annotations

import random
from dataclasses import dataclass

ALIAS_ADJECTIVES: tuple[str, ...] = (
    "Amber",
    "Brisk",
    "Cedar",
    "Cobalt",
    "Coral",
    "Crisp",
    "Dapper",
    "Ember",
    "Fizzing",
    "Frosty",
    "Golden",
    "Indigo",
    "Jolly",
    "Lucky",
    "Mellow",
    "Mint",
    "Nimble",
    "Plum",
    "Rustic",
    "Saffron",
    "Silver",
    "Solar",
    "Teal",
    "Velvet",
)

ALIAS_ANIMALS: tuple[str, ...] = (
    "Alpaca",
    "Badger",
    "Beaver",
    "Bobcat",
    "Capybara",
    "Coyote",
    "Falcon",
    "Ferret",
    "Flamingo",
    "Fox",
    "Gecko",
    "Heron",
    "Koala",
    "Lemur",
    "Lynx",
    "Marmot",
    "Narwhal",
    "Ocelot",
    "Otter",
    "Panda",
    "Pelican",
    "Puffin",
    "Quokka",
    "Raccoon",
    "Toucan",
    "Wombat",
)

COLOR_PALETTE_SIZE = 10


@dataclass(frozen=True, slots=True)
class AssignedAlias:
    """Unique per-round identity tuple assigned to a RoundSeat."""

    alias: str
    color_index: int
    order_index: int


def assign_round_aliases(
    count: int,
    *,
    rng: random.Random | None = None,
) -> list[AssignedAlias]:
    """Generate `count` unique (alias, color_index, order_index) tuples for one round."""
    if count < 0:
        raise ValueError("count must be non-negative")
    if count > COLOR_PALETTE_SIZE:
        raise ValueError(f"count cannot exceed COLOR_PALETTE_SIZE ({COLOR_PALETTE_SIZE})")
    if count == 0:
        return []

    generator = rng or random.SystemRandom()
    color_indices = list(range(COLOR_PALETTE_SIZE))
    generator.shuffle(color_indices)

    order_indices = list(range(count))
    generator.shuffle(order_indices)

    used_aliases: set[str] = set()
    assigned: list[AssignedAlias] = []
    for idx in range(count):
        while True:
            adjective = generator.choice(ALIAS_ADJECTIVES)
            animal = generator.choice(ALIAS_ANIMALS)
            candidate = f"{adjective} {animal}"
            if candidate not in used_aliases:
                used_aliases.add(candidate)
                break
        assigned.append(
            AssignedAlias(
                alias=candidate,
                color_index=color_indices[idx],
                order_index=order_indices[idx],
            )
        )
    return assigned
