from __future__ import annotations

from pydantic import BaseModel, Field


class AdapterCapabilities(BaseModel):
    name: str
    supported_cabin_classes: list[str] = Field(default_factory=list)
    supports_multi_city: bool = False
    supported_regions: list[str] = Field(default_factory=list)
    max_passengers: int = Field(default=9, ge=1)
    supported_currencies: list[str] = Field(default_factory=list)
