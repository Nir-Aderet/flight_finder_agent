from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from flight_finder.models.query import FlightSearchRequest
from flight_finder.models.result import NormalizedFlight, Segment, SiteResult
from flight_finder.normalizer.dedup import dedup_flights
from flight_finder.normalizer.normalize import normalize_results

_REQ = FlightSearchRequest(origin="SFO", destination="CDG", depart_date=date(2026, 6, 1))
_CAPTURED = datetime(2026, 6, 1, 12, 0)

_DEPART = datetime(2026, 6, 1, 8, 30)
_ARRIVE = datetime(2026, 6, 1, 19, 45)
_DURATION = timedelta(hours=11, minutes=15)


def _make_flight(
    adapter: str,
    price: str,
    airline: str = "Air France",
    depart: datetime = _DEPART,
) -> NormalizedFlight:
    seg = Segment(
        airline=airline,
        flight_number="",
        origin="SFO",
        destination="CDG",
        depart_at=depart,
        arrive_at=depart + _DURATION,
        duration=_DURATION,
    )
    return NormalizedFlight(
        source_adapter=adapter,
        sources=[adapter],
        price=Decimal(price),
        currency="USD",
        segments=[seg],
        stops=0,
        total_duration=_DURATION,
    )


class TestDedupFlights:
    def test_unique_flights_pass_through(self) -> None:
        flights = [
            _make_flight("google_flights", "849", airline="Air France"),
            _make_flight("kayak", "589", airline="Delta"),
        ]
        result = dedup_flights(flights)
        assert len(result) == 2

    def test_same_flight_from_two_adapters_merged(self) -> None:
        gf_flight = _make_flight("google_flights", "849", airline="Air France")
        kayak_flight = _make_flight("kayak", "724", airline="Air France")
        result = dedup_flights([gf_flight, kayak_flight])
        assert len(result) == 1

    def test_merged_keeps_lowest_price(self) -> None:
        gf_flight = _make_flight("google_flights", "849", airline="Air France")
        kayak_flight = _make_flight("kayak", "724", airline="Air France")
        result = dedup_flights([gf_flight, kayak_flight])
        assert result[0].price == Decimal("724")

    def test_merged_combines_sources(self) -> None:
        gf_flight = _make_flight("google_flights", "849", airline="Air France")
        kayak_flight = _make_flight("kayak", "724", airline="Air France")
        result = dedup_flights([gf_flight, kayak_flight])
        assert "google_flights" in result[0].sources
        assert "kayak" in result[0].sources

    def test_five_minute_tolerance_matches_nearby_times(self) -> None:
        base = datetime(2026, 6, 1, 8, 30)
        nearby = datetime(2026, 6, 1, 8, 32)  # 2 min apart — same bucket
        gf_flight = _make_flight("google_flights", "849", airline="Air France", depart=base)
        kayak_flight = _make_flight("kayak", "724", airline="Air France", depart=nearby)
        result = dedup_flights([gf_flight, kayak_flight])
        assert len(result) == 1

    def test_different_airlines_not_merged(self) -> None:
        a = _make_flight("google_flights", "849", airline="Air France")
        b = _make_flight("kayak", "724", airline="Delta")
        result = dedup_flights([a, b])
        assert len(result) == 2

    def test_same_adapter_duplicate_preserved(self) -> None:
        # Two flights from same adapter with same key → merged (lowest price kept)
        a = _make_flight("google_flights", "900", airline="Air France")
        b = _make_flight("google_flights", "849", airline="Air France")
        result = dedup_flights([a, b])
        assert len(result) == 1
        assert result[0].price == Decimal("849")

    def test_empty_input(self) -> None:
        assert dedup_flights([]) == []

    def test_single_flight_unchanged(self) -> None:
        flight = _make_flight("google_flights", "849")
        result = dedup_flights([flight])
        assert result == [flight]

    def test_order_independent(self) -> None:
        gf = _make_flight("google_flights", "849", airline="Air France")
        kayak = _make_flight("kayak", "724", airline="Air France")
        result_ab = dedup_flights([gf, kayak])
        result_ba = dedup_flights([kayak, gf])
        assert result_ab[0].price == result_ba[0].price == Decimal("724")

    def test_sources_deduplicated_not_repeated(self) -> None:
        # If same adapter appears in multiple flights with same key, source listed once
        a = _make_flight("google_flights", "849")
        b = _make_flight("google_flights", "849")
        result = dedup_flights([a, b])
        assert result[0].sources.count("google_flights") == 1


class TestNormalizeAndDedup:
    """End-to-end: normalize from two adapters then dedup."""

    def _make_site_result(self, adapter: str, price: str, airline: str, time: str) -> SiteResult:
        return SiteResult(
            adapter=adapter,
            payload={
                "price_text": price,
                "airline": airline,
                "depart_time_text": time,
                "arrive_time_text": "7:45 PM",
                "arrives_next_day": False,
                "duration_text": "11 hr 15 min",
                "stops": 0,
                "stops_text": "Nonstop",
                "origin": "SFO",
                "destination": "CDG",
                "booking_url": None,
            },
            captured_at=_CAPTURED,
        )

    def test_cross_adapter_dedup_via_normalize_results(self) -> None:
        gf_result = self._make_site_result("google_flights", "$849", "Air France", "8:30 AM")
        kayak_result = self._make_site_result("kayak", "$724", "Air France", "8:30 AM")

        all_results = normalize_results([gf_result, kayak_result], _REQ)
        deduplicated = dedup_flights(all_results)

        assert len(deduplicated) == 1
        assert deduplicated[0].price == Decimal("724")
        assert set(deduplicated[0].sources) == {"google_flights", "kayak"}
