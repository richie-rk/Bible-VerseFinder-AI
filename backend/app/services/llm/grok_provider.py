"""
xAI Grok LLM provider implementation.

Grok uses an OpenAI-compatible API endpoint.
"""

from openai import AsyncOpenAI

from ...core.config import settings
from .base import LLMProvider, LLMResponse


class GrokProvider(LLMProvider):
    """xAI Grok API provider (OpenAI-compatible)."""

    provider_name = "grok"

    def __init__(self):
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.grok_api_key,
                base_url="https://api.x.ai/v1",
            )
        return self._client

    def is_available(self) -> bool:
        return bool(settings.grok_api_key)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.3,
        response_format: dict | None = None,
    ) -> LLMResponse:
        client = self._get_client()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        kwargs = {
            "model": settings.grok_summarization_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # Add JSON response format if schema provided
        if response_format:
            kwargs["response_format"] = {"type": "json_object"}

        response = await client.chat.completions.create(**kwargs)

        choice = response.choices[0]

        return LLMResponse(
            content=choice.message.content or "",
            provider=self.provider_name,
            model=settings.grok_summarization_model,
            tokens_used=response.usage.total_tokens if response.usage else 0,
            finish_reason=choice.finish_reason or "unknown",
        )
