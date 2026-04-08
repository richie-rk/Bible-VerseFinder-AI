from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:

    content: str
    provider: str
    model: str
    tokens_used: int
    finish_reason: str


class LLMProvider(ABC):

    provider_name: str = "base"

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 500,
        temperature: float = 0.3,
        response_format: dict | None = None,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            system_prompt: System instructions
            user_prompt: User query with context
            max_tokens: Maximum tokens in response
            temperature: Creativity (0.0-1.0)
            response_format: JSON schema for structured output (if supported)

        Returns:
            LLMResponse with content and metadata
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass
