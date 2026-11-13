"""Safety and abuse filter for incoming and outgoing bot text."""

from __future__ import annotations

import re
from dataclasses import dataclass

# Blocklist of extreme slurs and severe abuse patterns
ABUSE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(nigg|fagg|kike|chink|spic)\w*", re.IGNORECASE),
    re.compile(r"\b(kill\s+your\s*self|suicide|die\s+in\s+a\s+fire)\b", re.IGNORECASE),
)

INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions?", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(in\s+developer\s+mode|dan)", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*override", re.IGNORECASE),
)


@dataclass(frozen=True)
class FilterResult:
    allowed: bool
    reason: str | None = None
    is_injection: bool = False


def check_content_safety(text: str) -> FilterResult:
    """Validate content against safety rules and prompt injection heuristics."""
    if not text or not text.strip():
        return FilterResult(allowed=False, reason="empty_text")

    for pat in ABUSE_PATTERNS:
        if pat.search(text):
            return FilterResult(allowed=False, reason="abusive_content")

    for pat in INJECTION_PATTERNS:
        if pat.search(text):
            # Flagged as injection attempt (will be safely deflected)
            return FilterResult(allowed=True, reason="injection_attempt", is_injection=True)

    return FilterResult(allowed=True)
