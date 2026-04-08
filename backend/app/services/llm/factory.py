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
    available = []
    for name in _providers:
        try:
            provider = get_llm_provider(name)
            if provider.is_available():
                available.append(name)
        except Exception:
            pass
    return available


async def get_llm_with_fallback(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 500,
    temperature: float = 0.3,
    response_format: dict | None = None,
    primary_provider: str | None = None,
) -> LLMResponse:
    """
    Generate LLM response with automatic fallback.

    Fallback order: primary → openai → gemini → grok

    Args:
        system_prompt: System instructions
        user_prompt: User query with context
        max_tokens: Maximum tokens
        temperature: Creativity level
        response_format: JSON schema for structured output
        primary_provider: Preferred provider (optional)

    Returns:
        LLMResponse from first successful provider

    Raises:
        RuntimeError: If all providers fail
    """
    # Build fallback chain
    fallback_chain = []

    # Add primary provider first if specified
    if primary_provider:
        fallback_chain.append(primary_provider)

    # Add default fallback order
    default_order = [settings.llm_provider, "openai", "gemini", "grok"]
    for provider_name in default_order:
        if provider_name not in fallback_chain:
            fallback_chain.append(provider_name)

    errors = []

    for provider_name in fallback_chain:
        try:
            provider = get_llm_provider(provider_name)

            if not provider.is_available():
                logger.debug(f"Provider {provider_name} not available (no API key)")
                continue

            logger.info(f"Attempting LLM generation with {provider_name}")

            response = await provider.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                response_format=response_format,
            )

            logger.info(f"Successfully generated response with {provider_name}")
            return response

        except Exception as e:
            error_msg = f"{provider_name}: {type(e).__name__}: {str(e)}"
            errors.append(error_msg)
            logger.warning(f"Provider {provider_name} failed: {e}")
            continue

    # All providers failed
    raise RuntimeError(f"All LLM providers failed. Errors: {errors}")
