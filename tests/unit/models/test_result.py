from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from flight_finder.models.result import NormalizedFlight, Segment, SiteResult


def _utc(hour: int = 8) -> datetime:
    return datetime(2026, 6, 1, hour, 0, 0, tzinfo=timezone.utc)


def _segment(origin: str = "SFO", destination: str = "CDG") -> Segment:
    return Segment(
        airline="Air France",
        flight_number="AF066",
        origin=origin,
        destination=destination,
        depart_at=_utc(8),
        arrive_at=_utc(19),
        duration=timedelta(hours=11),
    )


class TestSiteResult:
    def test_valid(self) -> None:
        sr = SiteResult(
            adapter="google_flights",
            payload={"price": "849", "url": "https://example.com"},
            captured_at=_utc(),
        )
        assert sr.adapter == "google_flights"
        assert sr.payload["price"] == "849"

    def test_empty_payload_allowed(self) -> None:
        sr = SiteResult(adapter="kayak", payload={}, captured_at=_utc())
        assert sr.payload == {}

    def test_missing_adapter_raises(self) -> None:
        with pytest.raises(ValidationError):
            SiteResult(payload={}, captured_at=_utc())  # type: ignore[call-arg]


class TestSegment:
    def test_valid(self) -> None:
        seg = _segment()
        assert seg.airline == "Air France"
        assert seg.flight_number == "AF066"
        assert seg.origin == "SFO"
        assert seg.destination == "CDG"
        assert seg.duration == timedelta(hours=11)

    def test_invalid_origin_raises(self) -> None:
        with pytest.raises(ValidationError):
            Segment(
                airline="AF",
                flight_number="AF066",
                origin="sf",  # too short
                destination="CDG",
                depart_at=_utc(8),
                arrive_at=_utc(19),
                duration=timedelta(hours=11),
            )

    def test_invalid_destination_raises(self) -> None:
        with pytest.raises(ValidationError):
            Segment(
                airline="AF",
                flight_number="AF066",
                origin="SFO",
                destination="cdg",  # lowercase
                depart_at=_utc(8),
                arrive_at=_utc(19),
                duration=timedelta(hours=11),
            )


class TestNormalizedFlight:
    def test_valid_one_way(self) -> None:
        flight = NormalizedFlight(
            source_adapter="google_flights",
            price=Decimal("849.00"),
            currency="USD",
            segments=[_segment()],
            stops=0,
            total_duration=timedelta(hours=11),
        )
        assert flight.price == Decimal("849.00")
        assert flight.stops == 0
        assert flight.score is None
        assert flight.booking_url is None

    def test_sources_defaults_empty(self) -> None:
        flight = NormalizedFlight(
            source_adapter="kayak",
            price=Decimal("700"),
            currency="EUR",
            segments=[_segment()],
            stops=0,
            total_duration=timedelta(hours=11),
        )
        assert flight.sources == []

    def test_sources_populated(self) -> None:
        flight = NormalizedFlight(
            source_adapter="google_flights",
            sources=["google_flights", "kayak"],
            price=Decimal("700"),
            currency="USD",
            segments=[_segment()],
            stops=0,
            total_duration=timedelta(hours=11),
        )
        assert "kayak" in flight.sources

    def test_with_score_and_url(self) -> None:
        flight = NormalizedFlight(
            source_adapter="google_flights",
            price=Decimal("900"),
            currency="USD",
            segments=[_segment()],
            stops=0,
            total_duration=timedelta(hours=11),
            booking_url="https://example.com/book",
            score=0.87,
        )
        assert flight.score == pytest.approx(0.87)
        assert flight.booking_url == "https://example.com/book"

    def test_multi_segment(self) -> None:
        segs = [_segment("SFO", "JFK"), _segment("JFK", "CDG")]
        flight = NormalizedFlight(
            source_adapter="kayak",
            price=Decimal("650"),
            currency="USD",
            segments=segs,
            stops=1,
            total_duration=timedelta(hours=14),
        )
        assert len(flight.segments) == 2
        assert flight.stops == 1

    def test_empty_segments_raises(self) -> None:
        with pytest.raises(ValidationError):
            NormalizedFlight(
                source_adapter="kayak",
                price=Decimal("650"),
                currency="USD",
                segments=[],
                stops=0,
                total_duration=timedelta(hours=11),
            )

    def test_negative_stops_raises(self) -> None:
        with pytest.raises(ValidationError):
            NormalizedFlight(
                source_adapter="kayak",
                price=Decimal("650"),
                currency="USD",
                segments=[_segment()],
                stops=-1,
                total_duration=timedelta(hours=11),
            )

    def test_invalid_currency_raises(self) -> None:
        with pytest.raises(ValidationError):
            NormalizedFlight(
                source_adapter="kayak",
                price=Decimal("650"),
                currency="usd",  # lowercase
                segments=[_segment()],
                stops=0,
                total_duration=timedelta(hours=11),
            )

    def test_decimal_price_preserved(self) -> None:
        flight = NormalizedFlight(
            source_adapter="google_flights",
            price=Decimal("1234.56"),
            currency="USD",
            segments=[_segment()],
            stops=0,
            total_duration=timedelta(hours=11),
        )
        assert flight.price == Decimal("1234.56")
