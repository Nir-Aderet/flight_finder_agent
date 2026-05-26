from __future__ import annotations

import pytest
from datetime import date
from pydantic import ValidationError

from flight_finder.models.query import FlightSearchRequest


def _base() -> dict:
    return {
        "origin": "SFO",
        "destination": "CDG",
        "depart_date": date(2026, 6, 1),
    }


class TestFlightSearchRequest:
    def test_valid_one_way(self) -> None:
        req = FlightSearchRequest(**_base())
        assert req.origin == "SFO"
        assert req.destination == "CDG"
        assert req.passengers == 1
        assert req.cabin == "economy"
        assert req.currency == "USD"
        assert req.return_date is None
        assert req.max_stops is None

    def test_valid_round_trip(self) -> None:
        req = FlightSearchRequest(**_base(), return_date=date(2026, 6, 15))
        assert req.return_date == date(2026, 6, 15)

    def test_same_day_return_is_valid(self) -> None:
        req = FlightSearchRequest(**_base(), return_date=date(2026, 6, 1))
        assert req.return_date == req.depart_date

    def test_return_before_depart_raises(self) -> None:
        with pytest.raises(ValidationError, match="return_date"):
            FlightSearchRequest(**_base(), return_date=date(2026, 5, 31))

    def test_invalid_iata_lowercase_raises(self) -> None:
        with pytest.raises(ValidationError):
            FlightSearchRequest(**{**_base(), "origin": "sfo"})

    def test_invalid_iata_too_short_raises(self) -> None:
        with pytest.raises(ValidationError):
            FlightSearchRequest(**{**_base(), "destination": "CD"})

    def test_invalid_iata_too_long_raises(self) -> None:
        with pytest.raises(ValidationError):
            FlightSearchRequest(**{**_base(), "origin": "SFOX"})

    def test_invalid_iata_digits_raises(self) -> None:
        with pytest.raises(ValidationError):
            FlightSearchRequest(**{**_base(), "origin": "1FO"})

    def test_passengers_min(self) -> None:
        req = FlightSearchRequest(**_base(), passengers=1)
        assert req.passengers == 1

    def test_passengers_max(self) -> None:
        req = FlightSearchRequest(**_base(), passengers=9)
        assert req.passengers == 9

    def test_passengers_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            FlightSearchRequest(**_base(), passengers=0)

    def test_passengers_above_max_raises(self) -> None:
        with pytest.raises(ValidationError):
            FlightSearchRequest(**_base(), passengers=10)

    def test_max_stops_zero_allowed(self) -> None:
        req = FlightSearchRequest(**_base(), max_stops=0)
        assert req.max_stops == 0

    def test_max_stops_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            FlightSearchRequest(**_base(), max_stops=-1)

    def test_cabin_values(self) -> None:
        for cabin in ("economy", "premium", "business", "first"):
            req = FlightSearchRequest(**_base(), cabin=cabin)  # type: ignore[arg-type]
            assert req.cabin == cabin

    def test_invalid_cabin_raises(self) -> None:
        with pytest.raises(ValidationError):
            FlightSearchRequest(**_base(), cabin="cargo")  # type: ignore[arg-type]

    def test_preferred_airlines_defaults_empty(self) -> None:
        req = FlightSearchRequest(**_base())
        assert req.preferred_airlines == []

    def test_blocked_airlines_roundtrip(self) -> None:
        req = FlightSearchRequest(**_base(), blocked_airlines=["FR", "W6"])
        assert req.blocked_airlines == ["FR", "W6"]

    def test_currency_default_usd(self) -> None:
        req = FlightSearchRequest(**_base())
        assert req.currency == "USD"

    def test_currency_override(self) -> None:
        req = FlightSearchRequest(**_base(), currency="EUR")
        assert req.currency == "EUR"

    def test_invalid_currency_raises(self) -> None:
        with pytest.raises(ValidationError):
            FlightSearchRequest(**_base(), currency="eu")
