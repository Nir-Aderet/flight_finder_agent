from __future__ import annotations

from pydantic import BaseModel, Field

from .query import FlightSearchRequest


class SearchStep(BaseModel):
    adapter: str
    query: FlightSearchRequest
    priority: int = 0


class SearchPlan(BaseModel):
    query: FlightSearchRequest
    steps: list[SearchStep] = Field(default_factory=list)
    notes: str = ""
