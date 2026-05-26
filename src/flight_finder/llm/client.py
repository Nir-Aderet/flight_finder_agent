from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int


@runtime_checkable
class LLMClient(Protocol):
    async def complete(
        self,
        system: str,
        user: str,
        model: str | None = None,
    ) -> LLMResponse: ...
