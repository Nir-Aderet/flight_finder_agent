from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from flight_finder.executors.wizz_air import parse_results_html
from flight_finder.models.result import SiteResult

_FIXTURE = (
    Path(__file__).parents[2] / "fixtures" / "mock_pages" / "wizz_air_search.html"
)
_CAPTURED_AT = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _load_fixture() -> str:
    return _FIXTURE.read_text(encoding="utf-8")


class TestParseResultsHtml:
    def test_returns_three_results(self) -> None:
        results = parse_results_html(_load_fixture(), "LTN", "BUD", _CAPTURED_AT)
        assert len(results) == 3

    def test_all_are_wizz_air_site_results(self) -> None:
        results = parse_results_html(_load_fixture(), "LTN", "BUD", _CAPTURED_AT)
        for r in results:
            assert isinstance(r, SiteResult)
            assert r.adapter == "wizz_air"
            assert r.captured_at == _CAPTURED_AT

    def test_first_flight_parsed(self) -> None:
        results = parse_results_html(_load_fixture(), "LTN", "BUD", _CAPTURED_AT)
        r = results[0]
        assert r.payload["airline"] == "Wizz Air"
        assert r.payload["stops"] == 0
        assert r.payload["stops_text"] == "Direct"
        assert r.payload["price_text"] == "£59"
        assert r.payload["depart_time_text"] == "06:30"
        assert r.payload["arrive_time_text"] == "10:15"
        assert r.payload["duration_text"] == "2h 45m"

    def test_all_flights_are_direct(self) -> None:
        results = parse_results_html(_load_fixture(), "LTN", "BUD", _CAPTURED_AT)
        for r in results:
            assert r.payload["stops"] == 0

    def test_prices_extracted(self) -> None:
        results = parse_results_html(_load_fixture(), "LTN", "BUD", _CAPTURED_AT)
        prices = [r.payload["price_text"] for r in results]
        assert "£59" in prices
        assert "£79" in prices
        assert "£89" in prices

    def test_currency_detected_as_gbp(self) -> None:
        results = parse_results_html(_load_fixture(), "LTN", "BUD", _CAPTURED_AT)
        for r in results:
            assert r.payload["currency"] == "GBP"

    def test_airports_extracted(self) -> None:
        results = parse_results_html(_load_fixture(), "LTN", "BUD", _CAPTURED_AT)
        for r in results:
            assert r.payload["origin"] == "LTN"
            assert r.payload["destination"] == "BUD"

    def test_depart_times_are_24h(self) -> None:
        results = parse_results_html(_load_fixture(), "LTN", "BUD", _CAPTURED_AT)
        times = [r.payload["depart_time_text"] for r in results]
        assert "06:30" in times
        assert "12:00" in times
        assert "17:30" in times

    def test_durations_non_empty(self) -> None:
        results = parse_results_html(_load_fixture(), "LTN", "BUD", _CAPTURED_AT)
        for r in results:
            assert r.payload["duration_text"] != ""

    def test_empty_html_returns_empty_list(self) -> None:
        results = parse_results_html("<html><body></body></html>", "LTN", "BUD", _CAPTURED_AT)
        assert results == []

    def test_default_captured_at_is_set(self) -> None:
        results = parse_results_html(_load_fixture(), "LTN", "BUD")
        assert len(results) == 3
        for r in results:
            assert r.captured_at.tzinfo is not None

    def test_payload_has_booking_url_key(self) -> None:
        results = parse_results_html(_load_fixture(), "LTN", "BUD", _CAPTURED_AT)
        for r in results:
            assert "booking_url" in r.payload

    def test_second_flight_depart_time(self) -> None:
        results = parse_results_html(_load_fixture(), "LTN", "BUD", _CAPTURED_AT)
        assert results[1].payload["depart_time_text"] == "12:00"
        assert results[1].payload["price_text"] == "£79"

    def test_third_flight_depart_time(self) -> None:
        results = parse_results_html(_load_fixture(), "LTN", "BUD", _CAPTURED_AT)
        assert results[2].payload["depart_time_text"] == "17:30"
        assert results[2].payload["price_text"] == "£89"
