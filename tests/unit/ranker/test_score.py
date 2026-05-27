from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from flight_finder.config import RankingWeights
from flight_finder.models.query import FlightSearchRequest
from flight_finder.models.result import NormalizedFlight, Segment
from flight_finder.ranker.score import _min_max_norm, score_all

_REQ = FlightSearchRequest(origin="SFO", destination="CDG", depart_date=date(2026, 6, 1))

_SEG = Segment(
    airline="Air France",
    origin="SFO",
    destination="CDG",
    depart_at=datetime(2026, 6, 1, 8, 30),
    arrive_at=datetime(2026, 6, 2, 6, 45),
    duration=timedelta(hours=11, minutes=15),
)

_WEIGHTS = RankingWeights()


def _flight(price: str, duration_hours: float = 11.0, stops: int = 0, airline: str = "Air France") -> NormalizedFlight:
    dur = timedelta(hours=duration_hours)
    seg = _SEG.model_copy(update={"airline": airline, "duration": dur})
    return NormalizedFlight(
        source_adapter="google_flights",
        sources=["google_flights"],
        price=Decimal(price),
        currency="USD",
        segments=[seg],
        stops=stops,
        total_duration=dur,
    )


class TestMinMaxNorm:
    def test_distinct_values(self) -> None:
        result = _min_max_norm([0.0, 5.0, 10.0])
        assert result == [0.0, 0.5, 1.0]

    def test_all_equal(self) -> None:
        result = _min_max_norm([7.0, 7.0, 7.0])
        assert result == [0.5, 0.5, 0.5]

    def test_single_element(self) -> None:
        assert _min_max_norm([42.0]) == [0.5]


class TestScoreAll:
    def test_empty_returns_empty(self) -> None:
        assert score_all([], _WEIGHTS, _REQ) == []

    def test_single_flight_gets_score(self) -> None:
        result = score_all([_flight("500")], _WEIGHTS, _REQ)
        assert len(result) == 1
        assert result[0].score is not None

    def test_score_in_unit_interval(self) -> None:
        flights = [_flight("300"), _flight("500"), _flight("800")]
        scored = score_all(flights, _WEIGHTS, _REQ)
        for f in scored:
            assert f.score is not None
            assert 0.0 <= f.score <= 1.0

    def test_cheaper_flight_scores_higher(self) -> None:
        cheap = _flight("300")
        expensive = _flight("800")
        scored = score_all([expensive, cheap], _WEIGHTS, _REQ)
        assert scored[0].price == Decimal("300")

    def test_shorter_duration_scores_higher_same_price(self) -> None:
        short = _flight("500", duration_hours=8.0)
        long_ = _flight("500", duration_hours=14.0)
        scored = score_all([long_, short], _WEIGHTS, _REQ)
        assert scored[0].total_duration == timedelta(hours=8)

    def test_nonstop_scores_higher_same_price_duration(self) -> None:
        nonstop = _flight("500", stops=0)
        one_stop = _flight("500", stops=1)
        scored = score_all([one_stop, nonstop], _WEIGHTS, _REQ)
        assert scored[0].stops == 0

    def test_preferred_airline_bonus(self) -> None:
        req = _REQ.model_copy(update={"preferred_airlines": ["Air France"]})
        preferred = _flight("500", airline="Air France")
        other = _flight("500", airline="Lufthansa")
        # Same price/duration/stops — airline preference is the tiebreaker.
        scored = score_all([other, preferred], _WEIGHTS, req)
        assert scored[0].segments[0].airline == "Air France"

    def test_no_preferred_airlines_neutral(self) -> None:
        f1 = _flight("500", airline="Air France")
        f2 = _flight("500", airline="Lufthansa")
        scored = score_all([f1, f2], _WEIGHTS, _REQ)
        # Both neutral airline component — scores should be equal
        assert scored[0].score == pytest.approx(scored[1].score)

    def test_returns_descending_order(self) -> None:
        flights = [_flight("800"), _flight("400"), _flight("600")]
        scored = score_all(flights, _WEIGHTS, _REQ)
        scores = [f.score for f in scored]
        assert scores == sorted(scores, reverse=True)

    def test_original_flights_unchanged(self) -> None:
        f = _flight("500")
        assert f.score is None
        score_all([f], _WEIGHTS, _REQ)
        assert f.score is None  # model_copy used; original unmodified
