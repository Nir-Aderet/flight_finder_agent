from __future__ import annotations

import asyncio
import time
import uuid
from datetime import datetime, timezone

import structlog
from playwright.async_api import Browser

from flight_finder.common.airports import adapter_covers_route
from flight_finder.common.cache import FlightCache
from flight_finder.common.logging import get_logger
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
from flight_finder.normalizer.dedup import dedup_flights
from flight_finder.normalizer.normalize import normalize_results
from flight_finder.planner.planner import Planner


class Orchestrator:
    def __init__(
        self,
        adapters: list[SiteAdapter],
        planner: Planner,
        config: OrchestratorConfig | None = None,
        cache: FlightCache | None = None,
    ) -> None:
        self._adapters: dict[str, SiteAdapter] = {a.name: a for a in adapters}
        self._planner = planner
        self._config = config or OrchestratorConfig()
        self._cache = cache

    async def run(
        self,
        query: str | FlightSearchRequest,
        browser: Browser,
        debug: bool = False,
    ) -> OrchestratorResult:
        run_id = uuid.uuid4().hex[:12]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(run_id=run_id)
        log = get_logger("orchestrator")

        t_run = time.monotonic()
        log.info("run.start", query=str(query)[:120])

        ctx = ExecutionContext(browser=browser, debug=debug, run_id=run_id)
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
                if self._cache is not None:
                    cached = await self._cache.get(resolved_query)
                    if cached is not None:
                        log.info("run.cache_hit", key=FlightCache.make_key(resolved_query))
                        return cached

            if not plan.steps:
                break

            # Filter steps to adapters that cover this route (e.g. skip Wizz Air for trans-Atlantic)
            eligible_steps = [
                s for s in plan.steps
                if s.adapter in self._adapters
                and adapter_covers_route(
                    self._adapters[s.adapter].capabilities.supported_regions,
                    resolved_query.origin,
                    resolved_query.destination,
                )
            ]
            steps = sorted(eligible_steps, key=lambda s: s.priority, reverse=True)
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
                    normalized = normalize_results(raw.results, plan.query)
                    if normalized:
                        round_flights.extend(normalized)
                    else:
                        new_failures.append(
                            FailureContext(
                                adapter=step.adapter,
                                reason="no_results",
                                detail="Adapter returned empty results",
                                retryable=True,
                                attempt=replan_attempt + 1,
                            )
                        )
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
        deduped = dedup_flights(all_flights)
        elapsed_ms = round((time.monotonic() - t_run) * 1000)
        log.info(
            "run.complete",
            total_flights=len(deduped),
            replan_attempts=replan_attempt,
            elapsed_ms=elapsed_ms,
        )
        result = OrchestratorResult(
            query=resolved_query,
            flights=deduped,
            audit=all_audit,
            replan_attempts=replan_attempt,
        )
        if self._cache is not None:
            await self._cache.set(resolved_query, result)
        return result

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
