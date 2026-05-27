from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup

from flight_finder.common.logging import get_logger
from flight_finder.common.retry import adapter_retry
from flight_finder.common.robots import RobotsChecker, RobotsDisallowed
from flight_finder.executors import wizz_air_selectors as sel
from flight_finder.executors.base import (
    BlockedByAntiBot,
    ExecutionContext,
    ExecutionResult,
    SiteFailure,
    SiteResults,
)
from flight_finder.executors.playwright_base import (
    detect_anti_bot,
    dismiss_consent_dialog,
    save_debug_artifacts,
    wait_for_results,
)
from flight_finder.models.capabilities import AdapterCapabilities
from flight_finder.models.plan import SearchStep
from flight_finder.models.result import SiteResult

_BASE_URL = "https://wizzair.com"
_RATE_LIMIT_DELAY = 3.0  # Wizz Air is a direct airline; be more conservative


def _build_search_url(req: Any) -> str:
    date_str = req.depart_date.isoformat()
    pax = getattr(req, "passengers", 1)
    return (
        f"{_BASE_URL}/en-gb/flights/search"
        f"/{req.origin}/{req.destination}/{date_str}/null/{pax}/0/0/null"
    )


def _parse_stops(stops_text: str) -> int:
    text = stops_text.strip().lower()
    if text in ("direct", "nonstop"):
        return 0
    m = re.match(r"(\d+)\s+stop", text)
    return int(m.group(1)) if m else 0


def _detect_currency(price_text: str) -> str:
    if price_text.startswith("£"):
        return "GBP"
    if price_text.startswith("€"):
        return "EUR"
    if price_text.startswith("$"):
        return "USD"
    return "EUR"  # Wizz Air default display currency in Europe


def parse_results_html(
    html: str,
    origin: str,
    destination: str,
    captured_at: datetime | None = None,
) -> list[SiteResult]:
    """Parse rendered Wizz Air HTML into raw SiteResult records.

    Pure function — no browser required. Adapter's execute() calls
    page.content() then passes the HTML here.
    """
    if captured_at is None:
        captured_at = datetime.now(timezone.utc)

    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(sel.FLIGHT_ITEM)
    results: list[SiteResult] = []

    for card in cards:
        depart_el = card.select_one(sel.DEPART_TIME)
        arrive_el = card.select_one(sel.ARRIVE_TIME)
        airline_el = card.select_one(sel.AIRLINE_NAME)
        duration_el = card.select_one(sel.DURATION)
        origin_el = card.select_one(sel.DEPART_AIRPORT)
        dest_el = card.select_one(sel.ARRIVE_AIRPORT)
        stops_el = card.select_one(sel.STOPS)
        price_el = card.select_one(sel.PRICE)

        if not (depart_el and price_el):
            continue

        depart_text = depart_el.get_text(strip=True)
        arrive_text = arrive_el.get_text(strip=True) if arrive_el else ""
        airline_text = airline_el.get_text(strip=True) if airline_el else "Wizz Air"
        duration_text = duration_el.get_text(strip=True) if duration_el else ""

        card_origin = origin_el.get_text(strip=True) if origin_el else origin
        card_dest = dest_el.get_text(strip=True) if dest_el else destination

        stops_text = stops_el.get_text(strip=True) if stops_el else "Direct"
        stops = _parse_stops(stops_text)
        price_text = price_el.get_text(strip=True)
        currency = _detect_currency(price_text)

        payload: dict[str, Any] = {
            "price_text": price_text,
            "airline": airline_text,
            "depart_time_text": depart_text,
            "arrive_time_text": arrive_text,
            "arrives_next_day": False,
            "duration_text": duration_text,
            "stops": stops,
            "stops_text": stops_text,
            "origin": card_origin,
            "destination": card_dest,
            "currency": currency,
            "booking_url": None,
        }
        results.append(
            SiteResult(adapter="wizz_air", payload=payload, captured_at=captured_at)
        )

    return results


class WizzAirAdapter:
    name = "wizz_air"
    capabilities = AdapterCapabilities(
        name="wizz_air",
        supported_cabin_classes=["economy", "plus"],
        supports_multi_city=False,
        supports_round_trip=True,
        supported_regions=["EU", "MEA"],
        max_passengers=6,
        supported_currencies=["EUR", "GBP", "PLN", "HUF"],
        typical_latency_ms=7000,
    )

    def __init__(
        self, robots_checker: RobotsChecker | None = None
    ) -> None:
        self._robots = robots_checker or RobotsChecker(user_agent="flight_finder")

    async def execute(self, step: SearchStep, ctx: ExecutionContext) -> ExecutionResult:
        log = get_logger("wizz_air")
        t0 = time.monotonic()
        log.info("adapter.start", adapter=self.name)

        # robots.txt compliance — checked once before any browser launch
        req = step.query
        try:
            path = f"/en-gb/flights/search/{req.origin}/{req.destination}"
            await self._robots.assert_allowed(_BASE_URL, path)
        except RobotsDisallowed as exc:
            log.warning("adapter.robots_disallowed", adapter=self.name, reason=str(exc))
            return SiteFailure(reason=str(exc), retryable=False, error_type="robots_disallowed")

        result = SiteResults(results=[])
        try:
            async for attempt in adapter_retry():
                with attempt:
                    result = await self._fetch(step, ctx)
            elapsed_ms = round((time.monotonic() - t0) * 1000)
            log.info(
                "adapter.success",
                adapter=self.name,
                result_count=len(result.results),
                elapsed_ms=elapsed_ms,
            )
            return result
        except BlockedByAntiBot as exc:
            elapsed_ms = round((time.monotonic() - t0) * 1000)
            log.warning("adapter.blocked", adapter=self.name, reason=str(exc), elapsed_ms=elapsed_ms)
            return SiteFailure(reason=str(exc), retryable=False, error_type="blocked_by_anti_bot")
        except Exception as exc:
            elapsed_ms = round((time.monotonic() - t0) * 1000)
            log.error("adapter.failure", adapter=self.name, reason=str(exc), elapsed_ms=elapsed_ms)
            return SiteFailure(reason=str(exc), retryable=True, error_type="unknown")

    async def _fetch(self, step: SearchStep, ctx: ExecutionContext) -> SiteResults:
        req = step.query
        url = _build_search_url(req)
        await asyncio.sleep(_RATE_LIMIT_DELAY)

        browser_ctx = await ctx.browser.new_context(
            user_agent=(
                "flight_finder/0.1 (+mailto:niraderet@gmail.com) "
                "Mozilla/5.0 (compatible; Playwright)"
            )
        )
        page = await browser_ctx.new_page()

        if ctx.debug:
            await browser_ctx.tracing.start(screenshots=True, snapshots=True)

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await _dismiss_wizz_air_consent(page)
            await wait_for_results(page, sel.FLIGHT_ITEM, timeout=45_000)
            await detect_anti_bot(page)

            html = await page.content()
            captured_at = datetime.now(timezone.utc)
            results = parse_results_html(html, req.origin, req.destination, captured_at)
            return SiteResults(results=results)

        except Exception:
            if ctx.debug:
                await save_debug_artifacts(browser_ctx, page, self.name)
            raise
        finally:
            await browser_ctx.close()


async def _dismiss_wizz_air_consent(page: Any, timeout: int = 3000) -> None:
    """Try Wizz Air-specific cookie-consent selectors; silently skip if none found."""
    for btn_sel in sel.CONSENT_BTNS:
        try:
            await page.click(btn_sel, timeout=timeout)
            return
        except Exception:
            continue
    await dismiss_consent_dialog(page, timeout=timeout)
