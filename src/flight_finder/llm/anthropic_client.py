from __future__ import annotations

import anthropic

from .client import LLMResponse


class AnthropicClient:
    def __init__(self, api_key: str, default_model: str = "claude-haiku-4-5") -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._default_model = default_model

    async def complete(
        self,
        system: str,
        user: str,
        model: str | None = None,
    ) -> LLMResponse:
        m = model or self._default_model
        response = await self._client.messages.create(
            model=m,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        block = response.content[0]
        text = block.text if hasattr(block, "text") else str(block)
        return LLMResponse(
            content=text,
            model=m,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
