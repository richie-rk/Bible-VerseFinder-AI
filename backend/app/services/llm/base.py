from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:

    content: str
    provider: str
    model: str
    tokens_used: int
    # Normalized across providers: "stop" for a complete answer, "length"
    # when max_tokens cut it off, otherwise the provider's own reason.
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
        json_output: bool = False,
    ) -> LLMResponse:
        """
        Generate a response from the LLM.

        Args:
            system_prompt: System instructions
            user_prompt: User query with context
            max_tokens: Maximum tokens in response
            temperature: Creativity (0.0-1.0)
            json_output: Ask the provider for a JSON object (JSON mode) where supported

        Returns:
            LLMResponse with content and metadata
        """

    @abstractmethod
    def is_available(self) -> bool:
        pass
