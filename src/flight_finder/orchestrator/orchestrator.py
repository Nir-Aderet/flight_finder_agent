from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

from playwright.async_api import Browser

from flight_finder.config import OrchestratorConfig
from flight_finder.executors.base import (
    ExecutionContext,
    SiteAdapter,
    SiteFailure,
    SiteResults,
)
from flight_finder.models.orchestrator import AuditRecord, FailureContext, OrchestratorResult
from flight_finder.models.plan import SearchStep
from flight_finder.models.query import FlightSearchRequest
from flight_finder.models.result import NormalizedFlight
from flight_finder.normalizer.normalize import normalize_results
from flight_finder.planner.planner import Planner


class Orchestrator:
    def __init__(
        self,
        adapters: list[SiteAdapter],
        planner: Planner,
        config: OrchestratorConfig | None = None,
    ) -> None:
        self._adapters: dict[str, SiteAdapter] = {a.name: a for a in adapters}
        self._planner = planner
        self._config = config or OrchestratorConfig()

    async def run(
        self,
        query: str | FlightSearchRequest,
        browser: Browser,
    ) -> OrchestratorResult:
        ctx = ExecutionContext(browser=browser)
        prior_failures: list[FailureContext] = []
        all_flights: list[NormalizedFlight] = []
        all_audit: list[AuditRecord] = []
        resolved_query: FlightSearchRequest | None = None
        replan_attempt = 0

        while True:
            plan = await self._planner.plan(
                query=query,
                adapters=[a.capabilities for a in self._adapters.values()],
                prior_failures=prior_failures,
                replan_attempt=replan_attempt,
            )

            if resolved_query is None:
                resolved_query = plan.query

            if not plan.steps:
                break

            steps = sorted(plan.steps, key=lambda s: s.priority, reverse=True)
            step_coros = [
                self._run_step(step, ctx, idx, all_audit)
                for idx, step in enumerate(steps)
            ]
            raw_results = await asyncio.gather(*step_coros, return_exceptions=True)

            round_flights: list[NormalizedFlight] = []
            new_failures: list[FailureContext] = []

            for step, raw in zip(steps, raw_results):
                if isinstance(raw, BaseException):
                    new_failures.append(
                        FailureContext(
                            adapter=step.adapter,
                            reason="unknown",
                            detail=str(raw),
                            retryable=True,
                            attempt=replan_attempt + 1,
                        )
                    )
                elif isinstance(raw, SiteResults):
                    round_flights.extend(normalize_results(raw.results, plan.query))
                elif isinstance(raw, SiteFailure):
                    new_failures.append(
                        FailureContext(
                            adapter=step.adapter,
                            reason=raw.error_type,
                            detail=raw.reason,
                            retryable=raw.retryable,
                            attempt=replan_attempt + 1,
                        )
                    )

            all_flights.extend(round_flights)

            if round_flights:
                break

            if replan_attempt >= self._config.max_replan_attempts:
                break

            prior_failures = new_failures
            replan_attempt += 1

        assert resolved_query is not None
        return OrchestratorResult(
            query=resolved_query,
            flights=all_flights,
            audit=all_audit,
            replan_attempts=replan_attempt,
        )

    async def _run_step(
        self,
        step: SearchStep,
        ctx: ExecutionContext,
        step_index: int,
        audit: list[AuditRecord],
    ) -> SiteResults | SiteFailure:
        adapter = self._adapters.get(step.adapter)
        started_at = datetime.now(timezone.utc)
        t0 = time.monotonic()

        if adapter is None:
            failure = SiteFailure(
                reason=f"Unknown adapter '{step.adapter}'",
                retryable=False,
                error_type="unknown",
            )
            audit.append(
                AuditRecord(
                    adapter=step.adapter,
                    step_index=step_index,
                    success=False,
                    duration_ms=0.0,
                    error=failure.reason,
                    started_at=started_at,
                )
            )
            return failure

        try:
            result: SiteResults | SiteFailure = await asyncio.wait_for(
                adapter.execute(step, ctx),
                timeout=float(self._config.per_step_timeout_seconds),
            )
        except asyncio.TimeoutError:
            result = SiteFailure(
                reason=f"Timed out after {self._config.per_step_timeout_seconds}s",
                retryable=True,
                error_type="timeout",
            )
        except Exception as exc:
            result = SiteFailure(
                reason=str(exc),
                retryable=True,
                error_type="unknown",
            )

        duration_ms = (time.monotonic() - t0) * 1000
        success = isinstance(result, SiteResults)
        audit.append(
            AuditRecord(
                adapter=step.adapter,
                step_index=step_index,
                success=success,
                result_count=len(result.results) if isinstance(result, SiteResults) else 0,
                duration_ms=duration_ms,
                error=result.reason if isinstance(result, SiteFailure) else None,
                started_at=started_at,
            )
        )
        return result
