"""Abstract base class and error types for LLM clients."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod


class LLMError(Exception):
    """Base exception for LLM completion errors."""


class LLMTimeoutError(LLMError):
    """Raised when an LLM completion exceeds its deadline (default 8s)."""


class LLMBudgetError(LLMError):
    """Raised when round or IP token/call budget is exhausted."""


class LLMClient(ABC):
    """Abstract interface for LLM completions."""

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        timeout: float = 8.0,
        temperature: float = 0.7,
        max_tokens: int = 150,
    ) -> str:
        """Asynchronously return completed text from the model."""
        raise NotImplementedError

    def complete_sync(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        timeout: float = 8.0,
        temperature: float = 0.7,
        max_tokens: int = 150,
    ) -> str:
        """Synchronously return completed text from the model."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # If in an event loop, use run_in_executor or async interface
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(
                    asyncio.run,
                    self.complete(
                        prompt,
                        system_prompt=system_prompt,
                        timeout=timeout,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    ),
                ).result()

        return asyncio.run(
            self.complete(
                prompt,
                system_prompt=system_prompt,
                timeout=timeout,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        )
