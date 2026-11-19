"""Provider-agnostic HTTP LLM client using httpx."""

from __future__ import annotations

from typing import Any

import httpx
from django.conf import settings

from apps.bot.llm.base import LLMClient, LLMError, LLMTimeoutError
from apps.bot.llm.fake import FakeLLMClient


class ProviderLLMClient(LLMClient):
    """Call external LLM APIs (OpenAI, Gemini, Anthropic) via standard HTTP."""

    def __init__(
        self,
        provider: str,
        api_key: str,
        model: str,
        *,
        base_url: str | None = None,
    ) -> None:
        self.provider = provider.lower()
        self.api_key = api_key
        self.model = model
        self.base_url = base_url

    async def complete(
        self,
        prompt: str,
        *,
        system_prompt: str = "",
        timeout: float = 8.0,
        temperature: float = 0.7,
        max_tokens: int = 150,
    ) -> str:
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                if self.provider in ("openai", "openrouter", "groq"):
                    if self.base_url:
                        url = self.base_url
                    elif self.provider == "groq":
                        url = "https://api.groq.com/openai/v1/chat/completions"
                    else:
                        url = "https://api.openai.com/v1/chat/completions"

                    messages = []
                    if system_prompt:
                        messages.append({"role": "system", "content": system_prompt})
                    messages.append({"role": "user", "content": prompt})

                    headers = {
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    }
                    data = {
                        "model": self.model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                    res = await client.post(url, headers=headers, json=data)
                    res.raise_for_status()
                    payload = res.json()
                    return str(payload["choices"][0]["message"]["content"]).strip()

                if self.provider in ("gemini", "google"):
                    url = (
                        self.base_url
                        or f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
                    )
                    req_data: dict[str, Any] = {
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {
                            "temperature": temperature,
                            "maxOutputTokens": max_tokens,
                        },
                    }
                    if system_prompt:
                        req_data["systemInstruction"] = {"parts": [{"text": system_prompt}]}

                    res = await client.post(url, json=req_data)
                    res.raise_for_status()
                    payload = res.json()
                    candidates = payload.get("candidates", [])
                    if not candidates:
                        return ""
                    return str(candidates[0]["content"]["parts"][0]["text"]).strip()

                if self.provider == "anthropic":
                    url = self.base_url or "https://api.anthropic.com/v1/messages"
                    headers = {
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json",
                    }
                    data = {
                        "model": self.model,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                        "messages": [{"role": "user", "content": prompt}],
                    }
                    if system_prompt:
                        data["system"] = system_prompt

                    res = await client.post(url, headers=headers, json=data)
                    res.raise_for_status()
                    payload = res.json()
                    return str(payload["content"][0]["text"]).strip()

                raise LLMError(f"Unsupported LLM provider: {self.provider}")
            except httpx.TimeoutException as exc:
                raise LLMTimeoutError(f"LLM request timed out after {timeout}s.") from exc
            except Exception as exc:
                if isinstance(exc, (LLMError, LLMTimeoutError)):
                    raise
                raise LLMError(f"LLM provider error: {exc}") from exc


def get_llm_client() -> LLMClient:
    """Return configured LLM client instance (FakeLLMClient if provider is 'fake' or unset)."""
    provider = getattr(settings, "LLM_PROVIDER", "fake").lower()
    api_key = getattr(settings, "LLM_API_KEY", "")
    model = getattr(settings, "LLM_MODEL", "")

    if provider == "fake" or not api_key:
        return FakeLLMClient()

    if not model or model == "fake":
        if provider == "groq":
            model = "llama-3.3-70b-versatile"
        elif provider in ("openai", "openrouter"):
            model = "gpt-4o-mini"
        elif provider in ("gemini", "google"):
            model = "gemini-2.0-flash"
        elif provider == "anthropic":
            model = "claude-3-5-haiku-20241022"
        else:
            model = "default"

    return ProviderLLMClient(provider=provider, api_key=api_key, model=model)
