"""Unit tests for unambiguous room code generation and validation."""

from __future__ import annotations

import pytest

from apps.rooms.codes import (
    ROOM_CODE_ALPHABET,
    ROOM_CODE_LENGTH,
    generate_room_code,
    generate_unique_room_code,
    is_valid_room_code,
    normalize_room_code,
)


def test_alphabet_excludes_ambiguous_characters() -> None:
    """Room code alphabet must exclude I, O, 0, and 1."""
    for forbidden in ("I", "O", "0", "1"):
        assert forbidden not in ROOM_CODE_ALPHABET
    assert len(ROOM_CODE_ALPHABET) == 32


def test_generated_codes_are_valid_and_diverse() -> None:
    """Generated codes match length 6 and use only valid alphabet chars."""
    codes = [generate_room_code() for _ in range(200)]
    for code in codes:
        assert len(code) == ROOM_CODE_LENGTH
        assert is_valid_room_code(code)
    assert len(set(codes)) > 190


def test_normalize_and_validate_room_code() -> None:
    """Normalization trims and uppercases; validator rejects invalid codes."""
    assert normalize_room_code("  ab2c3d \n") == "AB2C3D"
    assert is_valid_room_code("AB2C3D")
    assert not is_valid_room_code("AB2C3")
    assert not is_valid_room_code("AB2C3D9")
    assert not is_valid_room_code("AB2O3D")
    assert not is_valid_room_code("AB2I3D")
    assert not is_valid_room_code("AB203D")
    assert not is_valid_room_code("AB213D")
    assert not is_valid_room_code("ab2c3d")


def test_generate_unique_room_code_retries_collisions() -> None:
    """Generator retries until exists_fn returns False."""
    seen_calls = 0

    def exists_fn(_candidate: str) -> bool:
        nonlocal seen_calls
        seen_calls += 1
        return seen_calls < 3

    code = generate_unique_room_code(exists_fn, max_attempts=5)
    assert is_valid_room_code(code)
    assert seen_calls == 3


def test_generate_unique_room_code_raises_when_exhausted() -> None:
    """Generator raises RuntimeError if all attempts collide."""
    with pytest.raises(RuntimeError, match="Failed to generate"):
        generate_unique_room_code(lambda _c: True, max_attempts=3)
