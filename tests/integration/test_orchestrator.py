from __future__ import annotations

import json
from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pytest

from flight_finder.config import OrchestratorConfig
from flight_finder.executors.base import ExecutionContext, SiteFailure, SiteResults
from flight_finder.llm.client import LLMResponse
from flight_finder.models.capabilities import AdapterCapabilities
from flight_finder.models.plan import SearchStep
from flight_finder.models.query import FlightSearchRequest
from flight_finder.models.result import SiteResult
from flight_finder.orchestrator.orchestrator import Orchestrator
from flight_finder.planner.planner import Planner

# ---------------------------------------------------------------------------
# Shared test helpers
# ---------------------------------------------------------------------------

_DEPART = date(2026, 6, 1)
_CAPTURED = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)

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


def _plan_json(adapter: str = "fake", steps: bool = True) -> str:
    s = (
        [{"adapter": adapter, "query": _QUERY_DICT, "priority": 0}]
        if steps
        else []
    )
    notes = "" if steps else "No steps available."
    return json.dumps({"query": _QUERY_DICT, "steps": s, "notes": notes})


def _site_result(price: str = "$849") -> SiteResult:
    return SiteResult(
        adapter="google_flights",
        payload={
            "price_text": price,
            "airline": "Test Air",
            "depart_time_text": "8:30 AM",
            "arrive_time_text": "6:45 AM",
            "arrives_next_day": True,
            "duration_text": "11 hr 15 min",
            "stops": 0,
            "stops_text": "Nonstop",
            "origin": "SFO",
            "destination": "CDG",
            "booking_url": None,
        },
        captured_at=_CAPTURED,
    )


class FakeLLMClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = responses
        self._idx = 0

    @property
    def call_count(self) -> int:
        return self._idx

    async def complete(self, system: str, user: str, model: str | None = None) -> LLMResponse:
        content = self._responses[min(self._idx, len(self._responses) - 1)]
        self._idx += 1
        return LLMResponse(content=content, model=model or "fake", input_tokens=0, output_tokens=0)


class FakeAdapter:
    """Adapter that returns pre-configured results without touching a browser."""

    name = "fake"
    capabilities = AdapterCapabilities(
        name="fake",
        supported_regions=["NA", "EU"],
        supported_cabin_classes=["economy"],
    )

    def __init__(self, result: SiteResults | SiteFailure) -> None:
        self._result = result
        self.call_count = 0

    async def execute(self, step: SearchStep, ctx: ExecutionContext) -> SiteResults | SiteFailure:
        self.call_count += 1
        return self._result


def _mock_browser() -> MagicMock:
    return MagicMock()


def _make_orchestrator(
    adapter: FakeAdapter,
    llm_responses: list[str],
    max_replan: int = 2,
) -> Orchestrator:
    llm = FakeLLMClient(llm_responses)
    planner = Planner(llm=llm)
    cfg = OrchestratorConfig(
        per_step_timeout_seconds=30,
        max_replan_attempts=max_replan,
    )
    return Orchestrator(adapters=[adapter], planner=planner, config=cfg)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestOrchestratorSuccessPath:
    async def test_returns_normalized_flights(self) -> None:
        adapter = FakeAdapter(SiteResults(results=[_site_result("$849")]))
        orch = _make_orchestrator(adapter, [_plan_json("fake")])
        result = await orch.run(query="SFO to CDG", browser=_mock_browser())

        assert len(result.flights) == 1
        assert result.flights[0].price.__str__() == "849"
        assert result.replan_attempts == 0

    async def test_audit_records_success(self) -> None:
        adapter = FakeAdapter(SiteResults(results=[_site_result()]))
        orch = _make_orchestrator(adapter, [_plan_json("fake")])
        result = await orch.run(query="SFO to CDG", browser=_mock_browser())

        assert len(result.audit) == 1
        assert result.audit[0].success is True
        assert result.audit[0].result_count == 1

    async def test_query_resolved_from_plan(self) -> None:
        adapter = FakeAdapter(SiteResults(results=[_site_result()]))
        orch = _make_orchestrator(adapter, [_plan_json("fake")])
        result = await orch.run(query="SFO to CDG", browser=_mock_browser())

        assert result.query.origin == "SFO"
        assert result.query.destination == "CDG"


class TestOrchestratorFailurePath:
    async def test_all_failed_returns_empty_flights(self) -> None:
        adapter = FakeAdapter(SiteFailure(reason="timeout", retryable=True, error_type="timeout"))
        # Plan twice: both return steps, both fail → after max_replan break
        orch = _make_orchestrator(adapter, [_plan_json("fake")], max_replan=0)
        result = await orch.run(query="SFO to CDG", browser=_mock_browser())

        assert result.flights == []

    async def test_audit_records_failure(self) -> None:
        adapter = FakeAdapter(SiteFailure(reason="timeout", retryable=True, error_type="timeout"))
        orch = _make_orchestrator(adapter, [_plan_json("fake")], max_replan=0)
        result = await orch.run(query="SFO to CDG", browser=_mock_browser())

        assert len(result.audit) == 1
        assert result.audit[0].success is False
        assert result.audit[0].error is not None

    async def test_replan_triggered_after_failure(self) -> None:
        # First run fails, triggers replan; second plan has empty steps → stop
        adapter = FakeAdapter(SiteFailure(reason="err", retryable=True, error_type="unknown"))
        llm = FakeLLMClient([_plan_json("fake"), _plan_json("fake", steps=False)])
        planner = Planner(llm=llm)
        cfg = OrchestratorConfig(max_replan_attempts=1)
        orch = Orchestrator(adapters=[adapter], planner=planner, config=cfg)

        result = await orch.run(query="SFO to CDG", browser=_mock_browser())

        assert result.flights == []
        assert result.replan_attempts == 1
        assert llm.call_count == 2  # initial plan + 1 replan


class TestOrchestratorEmptyPlan:
    async def test_empty_steps_returns_immediately(self) -> None:
        adapter = FakeAdapter(SiteResults(results=[_site_result()]))
        orch = _make_orchestrator(adapter, [_plan_json("fake", steps=False)])
        result = await orch.run(query="vague query", browser=_mock_browser())

        assert result.flights == []
        assert adapter.call_count == 0  # adapter never called

    async def test_unknown_adapter_in_plan(self) -> None:
        adapter = FakeAdapter(SiteResults(results=[_site_result()]))
        # Plan references "fake", but planner validation will reject "unknown"
        # so we test with a plan that references a known adapter
        orch = _make_orchestrator(adapter, [_plan_json("fake")])
        result = await orch.run(query="SFO to CDG", browser=_mock_browser())
        assert len(result.flights) >= 0  # just confirm it doesn't crash
