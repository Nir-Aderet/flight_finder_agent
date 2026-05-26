from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from flight_finder.executors.kayak import parse_results_html
from flight_finder.models.result import SiteResult

_FIXTURE = (
    Path(__file__).parents[2] / "fixtures" / "mock_pages" / "kayak_search.html"
)
_CAPTURED_AT = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)


def _load_fixture() -> str:
    return _FIXTURE.read_text(encoding="utf-8")


class TestParseResultsHtml:
    def test_returns_three_results(self) -> None:
        results = parse_results_html(_load_fixture(), "SFO", "CDG", _CAPTURED_AT)
        assert len(results) == 3

    def test_all_are_kayak_site_results(self) -> None:
        results = parse_results_html(_load_fixture(), "SFO", "CDG", _CAPTURED_AT)
        for r in results:
            assert isinstance(r, SiteResult)
            assert r.adapter == "kayak"
            assert r.captured_at == _CAPTURED_AT

    def test_nonstop_flight_parsed(self) -> None:
        results = parse_results_html(_load_fixture(), "SFO", "CDG", _CAPTURED_AT)
        r = results[0]
        assert r.payload["airline"] == "Delta"
        assert r.payload["stops"] == 0
        assert r.payload["stops_text"] == "Nonstop"
        assert r.payload["price_text"] == "$724"
        assert r.payload["depart_time_text"] == "10:00 AM"
        assert r.payload["arrive_time_text"] == "8:15 AM"
        assert r.payload["arrives_next_day"] is True
        assert r.payload["duration_text"] == "11 hr 15 min"

    def test_one_stop_flights_parsed(self) -> None:
        results = parse_results_html(_load_fixture(), "SFO", "CDG", _CAPTURED_AT)
        assert results[1].payload["stops"] == 1
        assert results[2].payload["stops"] == 1

    def test_prices_extracted(self) -> None:
        results = parse_results_html(_load_fixture(), "SFO", "CDG", _CAPTURED_AT)
        prices = [r.payload["price_text"] for r in results]
        assert "$724" in prices
        assert "$589" in prices
        assert "$648" in prices

    def test_airports_extracted(self) -> None:
        results = parse_results_html(_load_fixture(), "SFO", "CDG", _CAPTURED_AT)
        for r in results:
            assert r.payload["origin"] == "SFO"
            assert r.payload["destination"] == "CDG"

    def test_airlines_extracted(self) -> None:
        results = parse_results_html(_load_fixture(), "SFO", "CDG", _CAPTURED_AT)
        airlines = [r.payload["airline"] for r in results]
        assert "Delta" in airlines
        assert "Air France" in airlines
        assert "United · Lufthansa" in airlines

    def test_durations_non_empty(self) -> None:
        results = parse_results_html(_load_fixture(), "SFO", "CDG", _CAPTURED_AT)
        for r in results:
            assert r.payload["duration_text"] != ""

    def test_empty_html_returns_empty_list(self) -> None:
        results = parse_results_html("<html><body></body></html>", "SFO", "CDG", _CAPTURED_AT)
        assert results == []

    def test_default_captured_at_is_set(self) -> None:
        results = parse_results_html(_load_fixture(), "SFO", "CDG")
        assert len(results) == 3
        for r in results:
            assert r.captured_at.tzinfo is not None

    def test_payload_has_booking_url_key(self) -> None:
        results = parse_results_html(_load_fixture(), "SFO", "CDG", _CAPTURED_AT)
        for r in results:
            assert "booking_url" in r.payload

    def test_second_result_airline(self) -> None:
        results = parse_results_html(_load_fixture(), "SFO", "CDG", _CAPTURED_AT)
        assert results[1].payload["airline"] == "Air France"
        assert results[1].payload["price_text"] == "$589"

    def test_third_result_airline(self) -> None:
        results = parse_results_html(_load_fixture(), "SFO", "CDG", _CAPTURED_AT)
        assert results[2].payload["airline"] == "United · Lufthansa"
        assert results[2].payload["price_text"] == "$648"
