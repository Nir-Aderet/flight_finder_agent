from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

from flight_finder.models.query import FlightSearchRequest
from flight_finder.models.result import NormalizedFlight, Segment
from flight_finder.normalizer.filter import apply_filters

_BASE_REQ = FlightSearchRequest(origin="SFO", destination="CDG", depart_date=date(2026, 6, 1))

_SEG = Segment(
    airline="Air France",
    origin="SFO",
    destination="CDG",
    depart_at=datetime(2026, 6, 1, 8, 30),
    arrive_at=datetime(2026, 6, 2, 6, 45),
    duration=timedelta(hours=11, minutes=15),
)


def _flight(price: str = "500", stops: int = 0, airline: str = "Air France") -> NormalizedFlight:
    seg = _SEG.model_copy(update={"airline": airline})
    return NormalizedFlight(
        source_adapter="google_flights",
        sources=["google_flights"],
        price=Decimal(price),
        currency="USD",
        segments=[seg],
        stops=stops,
        total_duration=timedelta(hours=11),
    )


class TestApplyFilters:
    def test_no_filters_passes_all(self) -> None:
        flights = [_flight("300"), _flight("500"), _flight("800")]
        assert apply_filters(flights, _BASE_REQ) == flights

    def test_empty_list_returns_empty(self) -> None:
        assert apply_filters([], _BASE_REQ) == []

    def test_max_stops_zero_removes_one_stop(self) -> None:
        req = _BASE_REQ.model_copy(update={"max_stops": 0})
        flights = [_flight(stops=0), _flight(stops=1), _flight(stops=2)]
        result = apply_filters(flights, req)
        assert len(result) == 1
        assert result[0].stops == 0

    def test_max_stops_one_keeps_nonstop_and_one_stop(self) -> None:
        req = _BASE_REQ.model_copy(update={"max_stops": 1})
        flights = [_flight(stops=0), _flight(stops=1), _flight(stops=2)]
        result = apply_filters(flights, req)
        assert len(result) == 2

    def test_max_price_removes_expensive(self) -> None:
        req = _BASE_REQ.model_copy(update={"max_price": Decimal("600")})
        flights = [_flight("300"), _flight("600"), _flight("601")]
        result = apply_filters(flights, req)
        assert len(result) == 2
        assert all(f.price <= Decimal("600") for f in result)

    def test_max_price_exact_boundary_kept(self) -> None:
        req = _BASE_REQ.model_copy(update={"max_price": Decimal("500")})
        result = apply_filters([_flight("500")], req)
        assert len(result) == 1

    def test_blocked_airline_case_insensitive(self) -> None:
        req = _BASE_REQ.model_copy(update={"blocked_airlines": ["air france"]})
        flights = [_flight(airline="Air France"), _flight(airline="Lufthansa")]
        result = apply_filters(flights, req)
        assert len(result) == 1
        assert result[0].segments[0].airline == "Lufthansa"

    def test_blocked_airline_mixed_case(self) -> None:
        req = _BASE_REQ.model_copy(update={"blocked_airlines": ["AIR FRANCE"]})
        result = apply_filters([_flight(airline="Air France")], req)
        assert result == []

    def test_multiple_filters_combined(self) -> None:
        req = _BASE_REQ.model_copy(update={
            "max_stops": 0,
            "max_price": Decimal("600"),
            "blocked_airlines": ["Ryanair"],
        })
        flights = [
            _flight("500", stops=0, airline="Air France"),   # passes
            _flight("500", stops=1, airline="Air France"),   # fails stops
            _flight("700", stops=0, airline="Air France"),   # fails price
            _flight("500", stops=0, airline="Ryanair"),      # fails blocked
        ]
        result = apply_filters(flights, req)
        assert len(result) == 1
        assert result[0].segments[0].airline == "Air France"

    def test_none_max_stops_no_filter(self) -> None:
        req = _BASE_REQ.model_copy(update={"max_stops": None})
        flights = [_flight(stops=0), _flight(stops=3)]
        assert len(apply_filters(flights, req)) == 2

    def test_empty_blocked_airlines_no_filter(self) -> None:
        req = _BASE_REQ.model_copy(update={"blocked_airlines": []})
        result = apply_filters([_flight(airline="Ryanair")], req)
        assert len(result) == 1
