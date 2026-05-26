from __future__ import annotations

import json
import re
from datetime import date

from pydantic import ValidationError

from flight_finder.llm.client import LLMClient, LLMResponse
from flight_finder.models.capabilities import AdapterCapabilities
from flight_finder.models.orchestrator import FailureContext
from flight_finder.models.plan import SearchPlan
from flight_finder.models.query import FlightSearchRequest
from flight_finder.planner.prompts import SYSTEM_PROMPT, build_user_prompt


class PlannerError(Exception):
    pass


def _strip_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _try_parse(text: str, adapter_names: set[str]) -> SearchPlan | None:
    try:
        data = json.loads(_strip_fences(text))
        plan = SearchPlan.model_validate(data)
        for step in plan.steps:
            if step.adapter not in adapter_names:
                return None
        if not plan.steps and not plan.notes:
            return None
        return plan
    except (json.JSONDecodeError, ValidationError, ValueError):
        return None


class Planner:
    def __init__(
        self,
        llm: LLMClient,
        primary_model: str = "claude-haiku-4-5",
        fallback_model: str = "claude-sonnet-4-6",
    ) -> None:
        self._llm = llm
        self._primary = primary_model
        self._fallback = fallback_model

    async def plan(
        self,
        query: str | FlightSearchRequest,
        adapters: list[AdapterCapabilities],
        prior_failures: list[FailureContext] | None = None,
        replan_attempt: int = 0,
        today: date | None = None,
    ) -> SearchPlan:
        if prior_failures is None:
            prior_failures = []

        user = build_user_prompt(
            query=query,
            adapters=adapters,
            prior_failures=prior_failures,
            replan_attempt=replan_attempt,
            today=today,
        )
        names = {a.name for a in adapters}

        last_resp: LLMResponse | None = None
        for model in (self._primary, self._primary, self._fallback):
            last_resp = await self._llm.complete(SYSTEM_PROMPT, user, model)
            plan = _try_parse(last_resp.content, names)
            if plan is not None:
                return plan

        snippet = last_resp.content[:500] if last_resp else "<no response>"
        raise PlannerError(
            f"Planner failed after 3 attempts (primary ×2, fallback ×1). "
            f"Last response: {snippet}"
        )
