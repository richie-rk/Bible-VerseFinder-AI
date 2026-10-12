import logging

from ...core.config import settings
from .base import LLMProvider, LLMResponse
from .openai_provider import OpenAIProvider
from .gemini_provider import GeminiProvider
from .grok_provider import GrokProvider

logger = logging.getLogger(__name__)

# Provider registry
_providers: dict[str, type[LLMProvider]] = {
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
    "grok": GrokProvider,
}

# Singleton instances
_provider_instances: dict[str, LLMProvider] = {}


class LLMUnavailableError(RuntimeError):
    """Every provider in the fallback chain failed or has no API key. The
    message lists provider names and exception types for the server log;
    it is not meant for API clients."""


def get_llm_provider(provider_name: str) -> LLMProvider:
    """
    Get an LLM provider instance by name.

    Args:
        provider_name: One of "openai", "gemini", "grok"

    Returns:
        LLMProvider instance

    Raises:
        ValueError: If provider name is unknown
    """
    if provider_name not in _providers:
        raise ValueError(f"Unknown provider: {provider_name}. Available: {list(_providers.keys())}")

    if provider_name not in _provider_instances:
        _provider_instances[provider_name] = _providers[provider_name]()

    return _provider_instances[provider_name]


def get_available_providers() -> list[str]:
    """Get list of available (configured) providers."""
    return [name for name in _providers if get_llm_provider(name).is_available()]


def _fallback_chain(primary_provider: str | None) -> list[str]:
    chain = [primary_provider] if primary_provider else []
    for provider_name in [settings.llm_provider, "openai", "gemini", "grok"]:
        if provider_name not in chain:
            chain.append(provider_name)
    return chain


async def get_llm_with_fallback(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 500,
    temperature: float = 0.3,
    json_output: bool = False,
    primary_provider: str | None = None,
) -> LLMResponse:
    """
    Generate LLM response with automatic fallback.

    Fallback order: primary → configured default → openai → gemini → grok

    Args:
        system_prompt: System instructions
        user_prompt: User query with context
        max_tokens: Maximum tokens
        temperature: Creativity level
        json_output: Request JSON mode from the provider
        primary_provider: Preferred provider (optional)

    Returns:
        LLMResponse from first successful provider

    Raises:
        LLMUnavailableError: If all providers fail or none is configured
    """
    errors = []

    for provider_name in _fallback_chain(primary_provider):
        provider = get_llm_provider(provider_name)

        if not provider.is_available():
            logger.debug("Provider %s not available (no API key)", provider_name)
            continue

        logger.info("Attempting LLM generation with %s", provider_name)
        try:
            response = await provider.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                json_output=json_output,
            )
        # Any failure (network, auth, quota, SDK error) means "try the next one".
        except Exception as e:
            errors.append(f"{provider_name}: {type(e).__name__}")
            logger.warning("Provider %s failed: %s: %s", provider_name, type(e).__name__, e)
            continue

        logger.info("Generated response with %s", provider_name)
        return response

    if not errors:
        raise LLMUnavailableError("No LLM provider is configured (set OPENAI_API_KEY, GEMINI_API_KEY or GROK_API_KEY)")
    raise LLMUnavailableError(f"All LLM providers failed: {'; '.join(errors)}")
