from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from .query import CurrencyCode, IATACode


class SiteResult(BaseModel):
    """Raw, adapter-specific result. Shape varies per site; normalizer converts to NormalizedFlight."""

    adapter: str
    payload: dict[str, Any]
    captured_at: datetime


class Segment(BaseModel):
    airline: str
    flight_number: str = ""
    origin: IATACode
    destination: IATACode
    depart_at: datetime
    arrive_at: datetime
    duration: timedelta


class NormalizedFlight(BaseModel):
    source_adapter: str
    sources: list[str] = Field(default_factory=list)
    price: Decimal
    currency: CurrencyCode
    segments: list[Segment] = Field(min_length=1)
    stops: int = Field(ge=0)
    total_duration: timedelta
    booking_url: str | None = None
    score: float | None = None
