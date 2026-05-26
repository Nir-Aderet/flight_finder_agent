from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from flight_finder.models.plan import SearchPlan, SearchStep
from flight_finder.models.query import FlightSearchRequest


def _request() -> FlightSearchRequest:
    return FlightSearchRequest(origin="SFO", destination="CDG", depart_date=date(2026, 6, 1))


class TestSearchStep:
    def test_valid_step(self) -> None:
        step = SearchStep(adapter="google_flights", query=_request())
        assert step.adapter == "google_flights"
        assert step.priority == 0

    def test_custom_priority(self) -> None:
        step = SearchStep(adapter="kayak", query=_request(), priority=5)
        assert step.priority == 5

    def test_negative_priority_allowed(self) -> None:
        step = SearchStep(adapter="kayak", query=_request(), priority=-1)
        assert step.priority == -1

    def test_missing_adapter_raises(self) -> None:
        with pytest.raises(ValidationError):
            SearchStep(query=_request())  # type: ignore[call-arg]

    def test_missing_query_raises(self) -> None:
        with pytest.raises(ValidationError):
            SearchStep(adapter="kayak")  # type: ignore[call-arg]


class TestSearchPlan:
    def test_valid_plan(self) -> None:
        req = _request()
        step = SearchStep(adapter="google_flights", query=req)
        plan = SearchPlan(query=req, steps=[step])
        assert len(plan.steps) == 1
        assert plan.notes == ""

    def test_empty_steps_default(self) -> None:
        plan = SearchPlan(query=_request())
        assert plan.steps == []

    def test_notes_field(self) -> None:
        plan = SearchPlan(query=_request(), notes="Using EU-based adapters only.")
        assert plan.notes == "Using EU-based adapters only."

    def test_multiple_steps(self) -> None:
        req = _request()
        steps = [
            SearchStep(adapter="google_flights", query=req, priority=1),
            SearchStep(adapter="kayak", query=req, priority=0),
        ]
        plan = SearchPlan(query=req, steps=steps)
        assert len(plan.steps) == 2
        assert plan.steps[0].adapter == "google_flights"

    def test_missing_query_raises(self) -> None:
        with pytest.raises(ValidationError):
            SearchPlan()  # type: ignore[call-arg]
