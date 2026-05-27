from __future__ import annotations

import anthropic

from flight_finder.common.logging import estimate_cost_usd, get_logger
from .client import LLMResponse


class AnthropicClient:
    def __init__(self, api_key: str, default_model: str = "claude-haiku-4-5") -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._default_model = default_model
        self._total_cost_usd: float = 0.0

    @property
    def total_cost_usd(self) -> float:
        """Accumulated estimated LLM cost for this client instance (USD)."""
        return self._total_cost_usd

    def reset_cost(self) -> None:
        """Reset the accumulated cost counter."""
        self._total_cost_usd = 0.0

    async def complete(
        self,
        system: str,
        user: str,
        model: str | None = None,
    ) -> LLMResponse:
        m = model or self._default_model
        log = get_logger("llm")
        log.info("llm.call.start", model=m, user_chars=len(user))

        response = await self._client.messages.create(
            model=m,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        block = response.content[0]
        text = block.text if hasattr(block, "text") else str(block)

        in_tok = response.usage.input_tokens
        out_tok = response.usage.output_tokens
        cost = estimate_cost_usd(m, in_tok, out_tok)
        self._total_cost_usd += cost

        log.info(
            "llm.call.complete",
            model=m,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=round(cost, 6),
        )

        return LLMResponse(
            content=text,
            model=m,
            input_tokens=in_tok,
            output_tokens=out_tok,
        )
