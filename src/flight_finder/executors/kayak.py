from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from flight_finder.executors import kayak_selectors as sel
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
    wait_for_results,
)
from flight_finder.models.capabilities import AdapterCapabilities
from flight_finder.models.plan import SearchStep
from flight_finder.models.result import SiteResult

_BASE_URL = "https://www.kayak.com/flights"
_RATE_LIMIT_DELAY = 2.0


def _build_search_url(step_query: Any) -> str:
    route = f"{step_query.origin}-{step_query.destination}"
    path = f"{_BASE_URL}/{route}/{step_query.depart_date.isoformat()}"
    if step_query.return_date:
        path += f"/{step_query.return_date.isoformat()}"
    params: dict[str, str] = {}
    if step_query.passengers > 1:
        params["travelers"] = f"{step_query.passengers}a"
    if params:
        path += "?" + urlencode(params)
    return path


def _parse_stops(stops_text: str) -> int:
    text = stops_text.strip().lower()
    if text == "nonstop":
        return 0
    m = re.match(r"(\d+)\s+stop", text)
    return int(m.group(1)) if m else 0


def _parse_arrive_time(el: Any) -> tuple[str, bool]:
    arrives_next_day = el.find("sup") is not None
    text = re.sub(r"\+\d+", "", el.get_text(strip=True)).strip()
    return text, arrives_next_day


def parse_results_html(
    html: str,
    origin: str,
    destination: str,
    captured_at: datetime | None = None,
) -> list[SiteResult]:
    """Parse rendered Kayak HTML into raw SiteResult records.

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
        airports_el = card.select_one(sel.AIRPORTS)
        stops_el = card.select_one(sel.STOPS)
        price_el = card.select_one(sel.PRICE)

        if not (depart_el and price_el):
            continue

        depart_text = depart_el.get_text(strip=True)

        arrive_text, arrives_next_day = "", False
        if arrive_el:
            arrive_text, arrives_next_day = _parse_arrive_time(arrive_el)

        airline_text = airline_el.get_text(strip=True) if airline_el else ""
        duration_text = duration_el.get_text(strip=True) if duration_el else ""

        card_origin, card_dest = origin, destination
        if airports_el:
            parts = airports_el.get_text(strip=True).split("–")
            if len(parts) == 2:
                card_origin = parts[0].strip()
                card_dest = parts[1].strip()

        stops_text = stops_el.get_text(strip=True) if stops_el else "Nonstop"
        stops = _parse_stops(stops_text)
        price_text = price_el.get_text(strip=True)

        payload: dict[str, Any] = {
            "price_text": price_text,
            "airline": airline_text,
            "depart_time_text": depart_text,
            "arrive_time_text": arrive_text,
            "arrives_next_day": arrives_next_day,
            "duration_text": duration_text,
            "stops": stops,
            "stops_text": stops_text,
            "origin": card_origin,
            "destination": card_dest,
            "booking_url": None,
        }
        results.append(
            SiteResult(adapter="kayak", payload=payload, captured_at=captured_at)
        )

    return results


class KayakAdapter:
    name = "kayak"
    capabilities = AdapterCapabilities(
        name="kayak",
        supported_cabin_classes=["economy", "premium", "business", "first"],
        supports_multi_city=True,
        supports_round_trip=True,
        supported_regions=["NA", "EU", "APAC", "LATAM"],
        max_passengers=8,
        supported_currencies=["USD", "EUR", "GBP"],
        typical_latency_ms=6200,
    )

    async def execute(self, step: SearchStep, ctx: ExecutionContext) -> ExecutionResult:
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

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            await _dismiss_kayak_consent(page)
            await wait_for_results(page, sel.FLIGHT_ITEM, timeout=45_000)
            await detect_anti_bot(page)

            html = await page.content()
            captured_at = datetime.now(timezone.utc)
            results = parse_results_html(html, req.origin, req.destination, captured_at)
            return SiteResults(results=results)

        except BlockedByAntiBot as exc:
            return SiteFailure(reason=str(exc), retryable=False, error_type="blocked_by_anti_bot")
        except Exception as exc:
            return SiteFailure(reason=str(exc), retryable=True, error_type="unknown")
        finally:
            await browser_ctx.close()


async def _dismiss_kayak_consent(page: Any, timeout: int = 3000) -> None:
    """Try each Kayak-specific consent selector; silently skip if none found."""
    for btn_sel in sel.CONSENT_BTNS:
        try:
            await page.click(btn_sel, timeout=timeout)
            return
        except Exception:
            continue
    # Fall back to the shared helper for any remaining patterns
    await dismiss_consent_dialog(page, timeout=timeout)
