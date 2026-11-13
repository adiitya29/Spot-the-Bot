"""Deterministic fake LLM client for testing and offline development."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Sequence

from apps.bot.llm.base import LLMClient, LLMError, LLMTimeoutError


class FakeLLMClient(LLMClient):
    """In-memory fake model returning canned or rule-based replies."""

    def __init__(
        self,
        canned_responses: Sequence[str] | None = None,
        *,
        simulated_delay: float = 0.0,
        should_timeout: bool = False,
        should_fail: bool = False,
    ) -> None:
        self.canned_responses = list(canned_responses or [])
        self.simulated_delay = simulated_delay
        self.should_timeout = should_timeout
        self.should_fail = should_fail
        self.call_history: list[dict[str, str]] = []
        self._index = 0

    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        timeout: float = 8.0,
        temperature: float = 0.7,
        max_tokens: int = 150,
    ) -> str:
        self.call_history.append({"prompt": prompt, "system_prompt": system_prompt})

        if self.should_fail:
            raise LLMError("Simulated LLM completion failure.")

        if self.should_timeout or (self.simulated_delay > timeout > 0):
            if timeout > 0:
                await asyncio.sleep(min(self.simulated_delay, timeout))
            raise LLMTimeoutError(f"Simulated LLM timeout after {timeout}s.")

        if self.simulated_delay > 0:
            await asyncio.sleep(self.simulated_delay)

        if self.canned_responses:
            reply = self.canned_responses[self._index % len(self.canned_responses)]
            self._index += 1
            return reply

        # Default intelligent response matching probe patterns
        lower_prompt = prompt.lower()
        if "say banana" in lower_prompt:
            return "why would i say banana lol"
        if "ignore previous instructions" in lower_prompt or "system prompt" in lower_prompt:
            return "nah not doing that"
        if "are you a bot" in lower_prompt or "who is the bot" in lower_prompt:
            return "nah look at the others, not me"
        if re.search(
            r"\b(calculate|\d+\s*[\+\-\*\/x]\s*\d+|times\s+\d+|divided by|plus\s+\d+|minus\s+\d+)",
            lower_prompt,
        ):
            return "im not doing math during a game lol"

        return "honestly not sure but that seems pretty wild tbh"
