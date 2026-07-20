import os

from anthropic import Anthropic

from app.services.ai.base import (
    AIProvider,
    AIProviderError,
    AIResponse,
)


class ClaudeProvider(AIProvider):
    """
    Implementazione del provider Anthropic Claude.
    """

    def __init__(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")

        if not api_key:
            raise AIProviderError(
                "ANTHROPIC_API_KEY non configurata."
            )

        self.model = os.getenv(
            "CLAUDE_MODEL",
            "claude-sonnet-4-20250514",
        )

        self.client = Anthropic(api_key=api_key)

    def generate(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> AIResponse:

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": user_prompt,
                    }
                ],
            )

            text = ""

            for block in response.content:
                if getattr(block, "type", "") == "text":
                    text += block.text

            usage = getattr(response, "usage", None)

            return AIResponse(
                content=text.strip(),
                model=self.model,
                input_tokens=getattr(
                    usage,
                    "input_tokens",
                    None,
                ),
                output_tokens=getattr(
                    usage,
                    "output_tokens",
                    None,
                ),
                raw_response=response,
            )

        except Exception as exc:
            raise AIProviderError(
                f"Errore Claude: {exc}"
            ) from exc