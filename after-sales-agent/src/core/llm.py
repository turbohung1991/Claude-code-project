from anthropic import Anthropic

from src.core.config import Settings


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = Anthropic(api_key=settings.anthropic_api_key)

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        response = self._client.messages.create(
            model=self.settings.model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )
        return response.content[0].text
