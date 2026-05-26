from __future__ import annotations

import json
from datetime import date

import pytest

from flight_finder.llm.client import LLMResponse
from flight_finder.models.capabilities import AdapterCapabilities
from flight_finder.models.plan import SearchPlan
from flight_finder.planner.planner import Planner, PlannerError, _try_parse


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

_ADAPTERS = [
    AdapterCapabilities(name="google_flights", supported_regions=["NA", "EU"]),
    AdapterCapabilities(name="kayak", supported_regions=["NA", "EU"]),
]

_ADAPTER_NAMES = {"google_flights", "kayak"}

_QUERY_DICT = {
    "origin": "SFO",
    "destination": "CDG",
    "depart_date": "2026-06-01",
    "passengers": 1,
    "cabin": "economy",
    "preferred_airlines": [],
    "blocked_airlines": [],
    "currency": "USD",
}

_VALID_PLAN_JSON = json.dumps(
    {
        "query": _QUERY_DICT,
        "steps": [
            {"adapter": "google_flights", "query": _QUERY_DICT, "priority": 1},
        ],
        "notes": "test plan",
    }
)

_EMPTY_STEPS_PLAN_JSON = json.dumps(
    {
        "query": _QUERY_DICT,
        "steps": [],
        "notes": "Ambiguous query — need more info.",
    }
)


class FakeLLMClient:
    """Returns a sequence of responses; repeats the last one indefinitely."""

    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    async def complete(self, system: str, user: str, model: str | None = None) -> LLMResponse:
        idx = min(self._call_count, len(self._responses) - 1)
        content = self._responses[idx]
        self._call_count += 1
        return LLMResponse(content=content, model=model or "fake", input_tokens=0, output_tokens=0)


# ---------------------------------------------------------------------------
# _try_parse unit tests
# ---------------------------------------------------------------------------


class TestTryParse:
    def test_valid_json_returns_plan(self) -> None:
        plan = _try_parse(_VALID_PLAN_JSON, _ADAPTER_NAMES)
        assert plan is not None
        assert isinstance(plan, SearchPlan)
        assert len(plan.steps) == 1

    def test_invalid_json_returns_none(self) -> None:
        assert _try_parse("not json", _ADAPTER_NAMES) is None

    def test_unknown_adapter_returns_none(self) -> None:
        bad = json.dumps(
            {
                "query": _QUERY_DICT,
                "steps": [{"adapter": "unknown_site", "query": _QUERY_DICT, "priority": 0}],
                "notes": "",
            }
        )
        assert _try_parse(bad, _ADAPTER_NAMES) is None

    def test_empty_steps_with_notes_ok(self) -> None:
        plan = _try_parse(_EMPTY_STEPS_PLAN_JSON, _ADAPTER_NAMES)
        assert plan is not None
        assert plan.steps == []
        assert plan.notes != ""

    def test_empty_steps_no_notes_returns_none(self) -> None:
        bad = json.dumps({"query": _QUERY_DICT, "steps": [], "notes": ""})
        assert _try_parse(bad, _ADAPTER_NAMES) is None

    def test_strips_markdown_fences(self) -> None:
        fenced = f"```json\n{_VALID_PLAN_JSON}\n```"
        plan = _try_parse(fenced, _ADAPTER_NAMES)
        assert plan is not None

    def test_missing_required_field_returns_none(self) -> None:
        bad = json.dumps({"steps": [], "notes": "missing query"})
        assert _try_parse(bad, _ADAPTER_NAMES) is None


# ---------------------------------------------------------------------------
# Planner.plan() tests
# ---------------------------------------------------------------------------


class TestPlannerPlan:
    async def test_returns_plan_on_first_try(self) -> None:
        llm = FakeLLMClient([_VALID_PLAN_JSON])
        planner = Planner(llm=llm)
        plan = await planner.plan(
            query="SFO to CDG on 2026-06-01",
            adapters=_ADAPTERS,
            today=date(2026, 5, 25),
        )
        assert isinstance(plan, SearchPlan)
        assert len(plan.steps) == 1
        assert llm.call_count == 1

    async def test_retries_on_first_failure(self) -> None:
        llm = FakeLLMClient(["not valid json", _VALID_PLAN_JSON])
        planner = Planner(llm=llm)
        plan = await planner.plan(
            query="SFO to CDG",
            adapters=_ADAPTERS,
            today=date(2026, 5, 25),
        )
        assert plan is not None
        assert llm.call_count == 2

    async def test_falls_back_to_sonnet_on_two_failures(self) -> None:
        llm = FakeLLMClient(["bad", "bad", _VALID_PLAN_JSON])
        planner = Planner(llm=llm, primary_model="primary", fallback_model="fallback")
        plan = await planner.plan(
            query="SFO to CDG",
            adapters=_ADAPTERS,
            today=date(2026, 5, 25),
        )
        assert plan is not None
        assert llm.call_count == 3

    async def test_raises_planner_error_on_persistent_failure(self) -> None:
        llm = FakeLLMClient(["bad json"])
        planner = Planner(llm=llm)
        with pytest.raises(PlannerError):
            await planner.plan(
                query="SFO to CDG",
                adapters=_ADAPTERS,
                today=date(2026, 5, 25),
            )
        assert llm.call_count == 3

    async def test_empty_steps_plan_returned(self) -> None:
        llm = FakeLLMClient([_EMPTY_STEPS_PLAN_JSON])
        planner = Planner(llm=llm)
        plan = await planner.plan(
            query="Cheap flights to Asia",
            adapters=_ADAPTERS,
            today=date(2026, 5, 25),
        )
        assert plan.steps == []
        assert plan.notes != ""

    async def test_structured_request_passed_as_json(self) -> None:
        from flight_finder.models.query import FlightSearchRequest

        req = FlightSearchRequest(origin="SFO", destination="CDG", depart_date=date(2026, 6, 1))
        llm = FakeLLMClient([_VALID_PLAN_JSON])
        planner = Planner(llm=llm)
        plan = await planner.plan(query=req, adapters=_ADAPTERS, today=date(2026, 5, 25))
        assert plan is not None
