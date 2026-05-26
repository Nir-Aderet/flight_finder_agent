from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .query import FlightSearchRequest
from .result import NormalizedFlight


class AuditRecord(BaseModel):
    adapter: str
    step_index: int = Field(ge=0)
    success: bool
    result_count: int = Field(default=0, ge=0)
    duration_ms: float = Field(ge=0.0)
    error: str | None = None
    started_at: datetime


class FailureContext(BaseModel):
    adapter: str
    reason: str
    retryable: bool
    attempt: int = Field(ge=0)


class OrchestratorResult(BaseModel):
    query: FlightSearchRequest
    flights: list[NormalizedFlight]
    audit: list[AuditRecord]
    replan_attempts: int = Field(default=0, ge=0)
