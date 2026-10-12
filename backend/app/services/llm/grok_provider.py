"""
xAI Grok LLM provider implementation.

Grok uses an OpenAI-compatible API endpoint, so this only swaps the
credentials, base URL and model.
"""

from ...core.config import settings
from .openai_provider import OpenAIProvider


class GrokProvider(OpenAIProvider):
    """xAI Grok API provider (OpenAI-compatible)."""

    provider_name = "grok"
    base_url = "https://api.x.ai/v1"

    @property
    def api_key(self) -> str:
        return settings.grok_api_key

    @property
    def model(self) -> str:
        return settings.grok_summarization_model

    def _token_limit(self, max_tokens: int) -> dict[str, int]:
        # xAI documents max_tokens for its chat completions endpoint.
        return {"max_tokens": max_tokens}
