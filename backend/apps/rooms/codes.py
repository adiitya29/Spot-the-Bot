"""Room code generation and normalization using an unambiguous 32-char alphabet."""

from __future__ import annotations

import secrets
from collections.abc import Callable

ROOM_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ROOM_CODE_LENGTH = 6
_AMBIGUOUS_CHARS = frozenset({"I", "O", "0", "1"})


def normalize_room_code(raw_code: str) -> str:
    """Trim surrounding whitespace and uppercase a room code."""
    return raw_code.strip().upper()


def is_valid_room_code(code: str) -> bool:
    """Return True if code has exact length and only unambiguous alphabet chars."""
    return len(code) == ROOM_CODE_LENGTH and all(ch in ROOM_CODE_ALPHABET for ch in code)


def generate_room_code() -> str:
    """Generate a single cryptographically random 6-character room code."""
    return "".join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(ROOM_CODE_LENGTH))


def generate_unique_room_code(
    exists_fn: Callable[[str], bool],
    max_attempts: int = 25,
) -> str:
    """Generate a room code not currently claimed according to exists_fn."""
    for _ in range(max_attempts):
        candidate = generate_room_code()
        if not exists_fn(candidate):
            return candidate
    raise RuntimeError("Failed to generate a unique room code after max_attempts")
