"""Tests for LLM client interfaces, FakeLLMClient, and Provider factory."""

from __future__ import annotations

import pytest
from django.test import override_settings

from apps.bot.llm.base import LLMError, LLMTimeoutError
from apps.bot.llm.fake import FakeLLMClient
from apps.bot.llm.provider import ProviderLLMClient, get_llm_client


@pytest.mark.asyncio
async def test_fake_llm_returns_canned_replies_in_sequence() -> None:
    fake = FakeLLMClient(canned_responses=["First reply", "Second reply"])
    r1 = await fake.complete("Hello")
    r2 = await fake.complete("How are you?")
    r3 = await fake.complete("Again")

    assert r1 == "First reply"
    assert r2 == "Second reply"
    assert r3 == "First reply"
    assert len(fake.call_history) == 3


@pytest.mark.asyncio
async def test_fake_llm_simulated_timeout() -> None:
    fake = FakeLLMClient(should_timeout=True)
    with pytest.raises(LLMTimeoutError):
        await fake.complete("Hello", timeout=0.1)


@pytest.mark.asyncio
async def test_fake_llm_simulated_failure() -> None:
    fake = FakeLLMClient(should_fail=True)
    with pytest.raises(LLMError, match="Simulated LLM completion failure"):
        await fake.complete("Hello")


def test_fake_llm_sync_completion() -> None:
    fake = FakeLLMClient(canned_responses=["Sync response"])
    res = fake.complete_sync("Test sync")
    assert res == "Sync response"


def test_get_llm_client_returns_fake_by_default() -> None:
    with override_settings(LLM_PROVIDER="fake", LLM_API_KEY=""):
        client = get_llm_client()
        assert isinstance(client, FakeLLMClient)


def test_get_llm_client_returns_provider_when_configured() -> None:
    with override_settings(LLM_PROVIDER="openai", LLM_API_KEY="test-key", LLM_MODEL="gpt-4o-mini"):
        client = get_llm_client()
        assert isinstance(client, ProviderLLMClient)
        assert client.provider == "openai"
        assert client.model == "gpt-4o-mini"
