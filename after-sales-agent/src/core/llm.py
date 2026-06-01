from openai import OpenAI

from src.core.config import Settings


class LLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client = OpenAI(
            api_key=settings.api_key,
            base_url=settings.base_url,
        )

    def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.3,
        max_tokens: int = 1024,
    ) -> str:
        response = self._client.chat.completions.create(
            model=self.settings.model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content
