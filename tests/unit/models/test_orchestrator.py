from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from flight_finder.models.orchestrator import AuditRecord, FailureContext, OrchestratorResult
from flight_finder.models.query import FlightSearchRequest
from flight_finder.models.result import NormalizedFlight, Segment


def _utc() -> datetime:
    return datetime(2026, 6, 1, 8, 0, 0, tzinfo=timezone.utc)


def _request() -> FlightSearchRequest:
    return FlightSearchRequest(origin="SFO", destination="CDG", depart_date=date(2026, 6, 1))


def _segment() -> Segment:
    return Segment(
        airline="Air France",
        flight_number="AF066",
        origin="SFO",
        destination="CDG",
        depart_at=_utc(),
        arrive_at=datetime(2026, 6, 1, 19, 0, 0, tzinfo=timezone.utc),
        duration=timedelta(hours=11),
    )


def _flight() -> NormalizedFlight:
    return NormalizedFlight(
        source_adapter="google_flights",
        price=Decimal("849"),
        currency="USD",
        segments=[_segment()],
        stops=0,
        total_duration=timedelta(hours=11),
    )


class TestAuditRecord:
    def test_valid_success(self) -> None:
        rec = AuditRecord(
            adapter="google_flights",
            step_index=0,
            success=True,
            result_count=12,
            duration_ms=2300.5,
            started_at=_utc(),
        )
        assert rec.success is True
        assert rec.result_count == 12
        assert rec.error is None

    def test_valid_failure(self) -> None:
        rec = AuditRecord(
            adapter="kayak",
            step_index=1,
            success=False,
            duration_ms=500.0,
            error="Blocked by anti-bot",
            started_at=_utc(),
        )
        assert rec.success is False
        assert rec.error == "Blocked by anti-bot"
        assert rec.result_count == 0

    def test_negative_step_index_raises(self) -> None:
        with pytest.raises(ValidationError):
            AuditRecord(
                adapter="kayak",
                step_index=-1,
                success=True,
                duration_ms=100.0,
                started_at=_utc(),
            )

    def test_negative_duration_raises(self) -> None:
        with pytest.raises(ValidationError):
            AuditRecord(
                adapter="kayak",
                step_index=0,
                success=True,
                duration_ms=-1.0,
                started_at=_utc(),
            )

    def test_negative_result_count_raises(self) -> None:
        with pytest.raises(ValidationError):
            AuditRecord(
                adapter="kayak",
                step_index=0,
                success=True,
                result_count=-1,
                duration_ms=100.0,
                started_at=_utc(),
            )


class TestFailureContext:
    def test_valid_retryable(self) -> None:
        fc = FailureContext(adapter="google_flights", reason="Timeout", retryable=True, attempt=1)
        assert fc.retryable is True
        assert fc.attempt == 1

    def test_valid_non_retryable(self) -> None:
        fc = FailureContext(
            adapter="kayak", reason="DisallowedByRobotsTxt", retryable=False, attempt=0
        )
        assert fc.retryable is False

    def test_negative_attempt_raises(self) -> None:
        with pytest.raises(ValidationError):
            FailureContext(
                adapter="kayak", reason="Timeout", retryable=True, attempt=-1
            )

    def test_missing_required_fields_raises(self) -> None:
        with pytest.raises(ValidationError):
            FailureContext(adapter="kayak")  # type: ignore[call-arg]


class TestOrchestratorResult:
    def test_valid_with_flights(self) -> None:
        audit = [
            AuditRecord(
                adapter="google_flights",
                step_index=0,
                success=True,
                result_count=5,
                duration_ms=1200.0,
                started_at=_utc(),
            )
        ]
        result = OrchestratorResult(
            query=_request(),
            flights=[_flight()],
            audit=audit,
        )
        assert len(result.flights) == 1
        assert result.replan_attempts == 0

    def test_empty_flights_allowed(self) -> None:
        result = OrchestratorResult(query=_request(), flights=[], audit=[])
        assert result.flights == []

    def test_replan_attempts_field(self) -> None:
        result = OrchestratorResult(
            query=_request(), flights=[], audit=[], replan_attempts=2
        )
        assert result.replan_attempts == 2

    def test_negative_replan_raises(self) -> None:
        with pytest.raises(ValidationError):
            OrchestratorResult(
                query=_request(), flights=[], audit=[], replan_attempts=-1
            )
