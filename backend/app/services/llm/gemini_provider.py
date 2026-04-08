import google.generativeai as genai

from ...core.config import settings
from .base import LLMProvider, LLMResponse


class GeminiProvider(LLMProvider):

    provider_name = "gemini"

    def __init__(self):
        self._configured = False

    def _configure(self):
        if not self._configured and settings.gemini_api_key:
            genai.configure(api_key=settings.gemini_api_key)
            self._configured = True

    def is_available(self) -> bool:
        return bool(settings.gemini_api_key)

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.3,
        response_format: dict | None = None,
    ) -> LLMResponse:
        self._configure()

        model = genai.GenerativeModel(
            model_name=settings.gemini_summarization_model,
            system_instruction=system_prompt,
            generation_config=genai.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
            ),
        )

        # Add JSON instruction if response format requested
        prompt = user_prompt
        if response_format:
            prompt += "\n\nRespond with valid JSON only."

        response = await model.generate_content_async(prompt)

        # Extract token count if available
        tokens_used = 0
        if hasattr(response, "usage_metadata"):
            tokens_used = getattr(response.usage_metadata, "total_token_count", 0)

        return LLMResponse(
            content=response.text,
            provider=self.provider_name,
            model=settings.gemini_summarization_model,
            tokens_used=tokens_used,
            finish_reason="stop",
        )
