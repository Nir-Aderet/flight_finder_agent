from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from flight_finder.models.query import FlightSearchRequest
from flight_finder.models.result import SiteResult
from flight_finder.normalizer.normalize import (
    _parse_duration,
    _parse_price,
    _parse_time,
    normalize_google_flights,
    normalize_results,
)

_REQ = FlightSearchRequest(origin="SFO", destination="CDG", depart_date=date(2026, 6, 1))

_CAPTURED = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)


def _make_result(**overrides: object) -> SiteResult:
    payload = {
        "price_text": "$849",
        "airline": "Air France",
        "depart_time_text": "8:30 AM",
        "arrive_time_text": "6:45 AM",
        "arrives_next_day": True,
        "duration_text": "11 hr 15 min",
        "stops": 0,
        "stops_text": "Nonstop",
        "origin": "SFO",
        "destination": "CDG",
        "booking_url": None,
    }
    payload.update(overrides)
    return SiteResult(adapter="google_flights", payload=payload, captured_at=_CAPTURED)


class TestParsePrice:
    def test_dollar_prefix(self) -> None:
        assert _parse_price("$849") == Decimal("849")

    def test_comma_thousands(self) -> None:
        assert _parse_price("$1,234") == Decimal("1234")

    def test_no_prefix(self) -> None:
        assert _parse_price("672") == Decimal("672")

    def test_empty_returns_none(self) -> None:
        assert _parse_price("") is None

    def test_text_only_returns_none(self) -> None:
        assert _parse_price("N/A") is None


class TestParseDuration:
    def test_hours_and_minutes(self) -> None:
        assert _parse_duration("11 hr 15 min") == timedelta(hours=11, minutes=15)

    def test_hours_only(self) -> None:
        assert _parse_duration("3 hr") == timedelta(hours=3)

    def test_minutes_only(self) -> None:
        assert _parse_duration("45 min") == timedelta(minutes=45)

    def test_empty_returns_zero(self) -> None:
        assert _parse_duration("") == timedelta(0)

    def test_compact_format(self) -> None:
        assert _parse_duration("2hr30min") == timedelta(hours=2, minutes=30)


class TestParseTime:
    def test_am_time(self) -> None:
        dt = _parse_time("8:30 AM", date(2026, 6, 1))
        assert dt == datetime(2026, 6, 1, 8, 30)

    def test_pm_time(self) -> None:
        dt = _parse_time("6:45 PM", date(2026, 6, 1))
        assert dt == datetime(2026, 6, 1, 18, 45)

    def test_hour_only(self) -> None:
        dt = _parse_time("9 AM", date(2026, 6, 1))
        assert dt == datetime(2026, 6, 1, 9, 0)

    def test_unparseable_returns_midnight(self) -> None:
        dt = _parse_time("", date(2026, 6, 1))
        assert dt == datetime(2026, 6, 1, 0, 0)


class TestNormalizeGoogleFlights:
    def test_happy_path(self) -> None:
        nf = normalize_google_flights(_make_result(), _REQ)
        assert nf is not None
        assert nf.price == Decimal("849")
        assert nf.currency == "USD"
        assert nf.stops == 0
        assert nf.source_adapter == "google_flights"
        assert "google_flights" in nf.sources

    def test_segment_airline(self) -> None:
        nf = normalize_google_flights(_make_result(), _REQ)
        assert nf is not None
        assert nf.segments[0].airline == "Air France"

    def test_segment_airports(self) -> None:
        nf = normalize_google_flights(_make_result(), _REQ)
        assert nf is not None
        assert nf.segments[0].origin == "SFO"
        assert nf.segments[0].destination == "CDG"

    def test_segment_flight_number_empty(self) -> None:
        nf = normalize_google_flights(_make_result(), _REQ)
        assert nf is not None
        assert nf.segments[0].flight_number == ""

    def test_duration_parsed(self) -> None:
        nf = normalize_google_flights(_make_result(), _REQ)
        assert nf is not None
        assert nf.total_duration == timedelta(hours=11, minutes=15)

    def test_missing_price_returns_none(self) -> None:
        result = _make_result(price_text="")
        assert normalize_google_flights(result, _REQ) is None

    def test_booking_url_none(self) -> None:
        nf = normalize_google_flights(_make_result(), _REQ)
        assert nf is not None
        assert nf.booking_url is None

    def test_invalid_iata_falls_back_to_request(self) -> None:
        result = _make_result(origin="bad", destination="also bad")
        nf = normalize_google_flights(result, _REQ)
        assert nf is not None
        assert nf.segments[0].origin == "SFO"
        assert nf.segments[0].destination == "CDG"

    def test_one_stop_flight(self) -> None:
        result = _make_result(stops=1, stops_text="1 stop")
        nf = normalize_google_flights(result, _REQ)
        assert nf is not None
        assert nf.stops == 1

    def test_depart_datetime_from_date_and_time(self) -> None:
        nf = normalize_google_flights(_make_result(), _REQ)
        assert nf is not None
        seg = nf.segments[0]
        assert seg.depart_at.year == 2026
        assert seg.depart_at.month == 6
        assert seg.depart_at.day == 1
        assert seg.depart_at.hour == 8
        assert seg.depart_at.minute == 30


class TestNormalizeResults:
    def test_filters_unknown_adapter(self) -> None:
        wrong = SiteResult(
            adapter="unknown_site",
            payload={"price_text": "$600"},
            captured_at=_CAPTURED,
        )
        results = normalize_results([wrong], _REQ)
        assert results == []

    def test_returns_normalized_google_flights(self) -> None:
        results = normalize_results([_make_result(), _make_result(price_text="$672")], _REQ)
        assert len(results) == 2

    def test_skips_unparseable(self) -> None:
        bad = _make_result(price_text="")
        good = _make_result()
        results = normalize_results([bad, good], _REQ)
        assert len(results) == 1
