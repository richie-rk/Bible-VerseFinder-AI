from google import genai
from google.genai import types

from ...core.config import settings
from .base import LLMProvider, LLMResponse


def _finish_reason(response: types.GenerateContentResponse) -> str:
    if not response.candidates or response.candidates[0].finish_reason is None:
        return "unknown"
    reason = response.candidates[0].finish_reason
    if reason == types.FinishReason.MAX_TOKENS:
        return "length"
    if reason == types.FinishReason.STOP:
        return "stop"
    return str(getattr(reason, "name", reason)).lower()


class GeminiProvider(LLMProvider):

    provider_name = "gemini"

    def __init__(self):
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            self._client = genai.Client(
                api_key=settings.gemini_api_key,
                http_options=types.HttpOptions(
                    timeout=int(settings.llm_timeout_seconds * 1000),
                    retry_options=types.HttpRetryOptions(
                        attempts=settings.llm_max_retries + 1
                    ),
                ),
            )
        return self._client

    def is_available(self) -> bool:
        return bool(settings.gemini_api_key)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.3,
        json_output: bool = False,
    ) -> LLMResponse:
        thinking = (
            types.ThinkingConfig(thinking_level=settings.gemini_thinking_level)
            if settings.gemini_thinking_level
            else None
        )
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=max_tokens,
            temperature=temperature,
            # JSON mode; without it Gemini tends to wrap JSON in ```json fences.
            response_mime_type="application/json" if json_output else None,
            thinking_config=thinking,
        )

        response = await self._get_client().aio.models.generate_content(
            model=settings.gemini_summarization_model,
            contents=user_prompt,
            config=config,
        )

        usage = response.usage_metadata
        return LLMResponse(
            content=response.text or "",
            provider=self.provider_name,
            model=response.model_version or settings.gemini_summarization_model,
            tokens_used=(usage.total_token_count or 0) if usage else 0,
            finish_reason=_finish_reason(response),
        )
