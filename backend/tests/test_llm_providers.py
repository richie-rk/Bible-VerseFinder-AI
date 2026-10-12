"""
Tests for the LLM providers' request parameters and the fallback chain. The
SDK clients are replaced with fakes, so no API keys or network are needed.
"""

import asyncio
from types import SimpleNamespace

import pytest
from google.genai import types

from app.core.config import settings
from app.services.llm import LLMResponse, LLMUnavailableError, factory
from app.services.llm.base import LLMProvider
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.grok_provider import GrokProvider
from app.services.llm.openai_provider import OpenAIProvider


def run(coro):
    return asyncio.run(coro)


class FakeChatCompletions:
    def __init__(self):
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(
            model="resolved-model",
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"a": 1}'), finish_reason="length")],
            usage=SimpleNamespace(total_tokens=42),
        )


def _with_fake_chat(provider):
    completions = FakeChatCompletions()
    provider._client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    return completions


def test_openai_provider_uses_max_completion_tokens_and_json_mode():
    provider = OpenAIProvider()
    completions = _with_fake_chat(provider)

    response = run(provider.generate("sys", "user", max_tokens=123, json_output=True))

    assert completions.kwargs["max_completion_tokens"] == 123
    assert "max_tokens" not in completions.kwargs
    assert completions.kwargs["response_format"] == {"type": "json_object"}
    assert completions.kwargs["model"] == settings.openai_summarization_model
    assert response == LLMResponse('{"a": 1}', "openai", "resolved-model", 42, "length")


def test_grok_provider_reuses_openai_client_with_its_own_settings(monkeypatch):
    monkeypatch.setattr(settings, "grok_api_key", "xai-key")
    provider = GrokProvider()
    assert provider.is_available()
    assert provider.base_url == "https://api.x.ai/v1"
    completions = _with_fake_chat(provider)

    response = run(provider.generate("sys", "user", max_tokens=50))

    assert completions.kwargs["max_tokens"] == 50
    assert completions.kwargs["model"] == settings.grok_summarization_model
    assert "response_format" not in completions.kwargs
    assert response.provider == "grok"


class FakeGeminiModels:
    def __init__(self, response):
        self.response = response
        self.call = None

    async def generate_content(self, model, contents, config):
        self.call = SimpleNamespace(model=model, contents=contents, config=config)
        return self.response


def _gemini_response(text, finish_reason):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(
            content=types.Content(parts=[types.Part(text=text)]) if text else None,
            finish_reason=finish_reason,
        )],
        usage_metadata=types.GenerateContentResponseUsageMetadata(total_token_count=7),
        model_version="gemini-test-001",
    )


def _with_fake_gemini(provider, response):
    models = FakeGeminiModels(response)
    provider._client = SimpleNamespace(aio=SimpleNamespace(models=models))
    return models


def test_gemini_provider_requests_json_mode_and_thinking_level(monkeypatch):
    monkeypatch.setattr(settings, "gemini_thinking_level", "low")
    provider = GeminiProvider()
    models = _with_fake_gemini(provider, _gemini_response('{"a": 1}', types.FinishReason.STOP))

    response = run(provider.generate("sys", "user", max_tokens=99, json_output=True))

    config = models.call.config
    assert config.response_mime_type == "application/json"
    assert config.max_output_tokens == 99
    assert config.system_instruction == "sys"
    assert config.thinking_config.thinking_level == types.ThinkingLevel.LOW
    assert response == LLMResponse('{"a": 1}', "gemini", "gemini-test-001", 7, "stop")


def test_gemini_thinking_level_can_be_disabled(monkeypatch):
    monkeypatch.setattr(settings, "gemini_thinking_level", "")
    provider = GeminiProvider()
    models = _with_fake_gemini(provider, _gemini_response("x", types.FinishReason.STOP))
    run(provider.generate("sys", "user"))
    assert models.call.config.thinking_config is None
    assert models.call.config.response_mime_type is None


@pytest.mark.parametrize(
    "finish_reason,expected",
    [
        (types.FinishReason.MAX_TOKENS, "length"),
        (types.FinishReason.STOP, "stop"),
        (types.FinishReason.SAFETY, "safety"),
    ],
)
def test_gemini_finish_reasons_are_normalized(finish_reason, expected):
    provider = GeminiProvider()
    _with_fake_gemini(provider, _gemini_response("", finish_reason))
    response = run(provider.generate("sys", "user"))
    assert response.finish_reason == expected
    assert response.content == ""


# ---------- Fallback chain ----------

class ScriptedProvider(LLMProvider):
    """Provider whose availability and behaviour are set per test."""

    available = True
    error: Exception | None = None
    calls: list[str] = []

    def is_available(self):
        return self.available

    async def generate(self, system_prompt, user_prompt, max_tokens=500, temperature=0.3, json_output=False):
        ScriptedProvider.calls.append(self.provider_name)
        if self.error:
            raise self.error
        return LLMResponse("ok", self.provider_name, "m", 1, "stop")


def _scripted(name, available=True, error=None):
    return type(name, (ScriptedProvider,), {"provider_name": name, "available": available, "error": error})


@pytest.fixture
def scripted_providers(monkeypatch):
    ScriptedProvider.calls = []

    def install(**providers):
        monkeypatch.setattr(factory, "_providers", providers)
        monkeypatch.setattr(factory, "_provider_instances", {})

    return install


def test_fallback_skips_unconfigured_and_failing_providers(scripted_providers, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider", "openai")
    scripted_providers(
        openai=_scripted("openai", error=RuntimeError("boom")),
        gemini=_scripted("gemini", available=False),
        grok=_scripted("grok"),
    )
    response = run(factory.get_llm_with_fallback("s", "u"))
    assert response.provider == "grok"
    assert ScriptedProvider.calls == ["openai", "grok"]


def test_primary_provider_is_tried_first(scripted_providers):
    scripted_providers(openai=_scripted("openai"), gemini=_scripted("gemini"), grok=_scripted("grok"))
    response = run(factory.get_llm_with_fallback("s", "u", primary_provider="grok"))
    assert response.provider == "grok"
    assert ScriptedProvider.calls == ["grok"]


def test_all_failing_raises_llm_unavailable(scripted_providers):
    scripted_providers(
        openai=_scripted("openai", error=RuntimeError("secret detail")),
        gemini=_scripted("gemini", available=False),
        grok=_scripted("grok", available=False),
    )
    with pytest.raises(LLMUnavailableError, match="openai: RuntimeError"):
        run(factory.get_llm_with_fallback("s", "u"))


def test_none_configured_raises_llm_unavailable(scripted_providers):
    scripted_providers(
        openai=_scripted("openai", available=False),
        gemini=_scripted("gemini", available=False),
        grok=_scripted("grok", available=False),
    )
    with pytest.raises(LLMUnavailableError, match="No LLM provider is configured"):
        run(factory.get_llm_with_fallback("s", "u"))
