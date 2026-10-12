from typing import Any

from openai import AsyncOpenAI

from ...core.config import settings
from .base import LLMProvider, LLMResponse


class OpenAIProvider(LLMProvider):
    """OpenAI chat completions. Subclasses reuse it for OpenAI-compatible APIs."""

    provider_name = "openai"
    base_url: str | None = None

    def __init__(self):
        self._client: AsyncOpenAI | None = None

    @property
    def api_key(self) -> str:
        return settings.openai_api_key

    @property
    def model(self) -> str:
        return settings.openai_summarization_model

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url,
                timeout=settings.llm_timeout_seconds,
                max_retries=settings.llm_max_retries,
            )
        return self._client

    def is_available(self) -> bool:
        return bool(self.api_key)

    def _token_limit(self, max_tokens: int) -> dict[str, int]:
        # max_tokens is deprecated for OpenAI chat models and rejected by the
        # reasoning ones.
        return {"max_completion_tokens": max_tokens}

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.3,
        json_output: bool = False,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            **self._token_limit(max_tokens),
        }
        if json_output:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self._get_client().chat.completions.create(**kwargs)

        choice = response.choices[0]
        return LLMResponse(
            content=choice.message.content or "",
            provider=self.provider_name,
            model=response.model or self.model,
            tokens_used=response.usage.total_tokens if response.usage else 0,
            finish_reason=choice.finish_reason or "unknown",
        )
