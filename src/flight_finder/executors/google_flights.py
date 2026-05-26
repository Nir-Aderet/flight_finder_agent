from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

from bs4 import BeautifulSoup

from flight_finder.executors import google_flights_selectors as sel
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

_BASE_URL = "https://www.google.com/travel/flights"
_RATE_LIMIT_DELAY = 2.0  # seconds between requests (M8 will replace with token bucket)


def _parse_stops(stops_text: str) -> int:
    text = stops_text.strip().lower()
    if text == "nonstop":
        return 0
    m = re.match(r"(\d+)\s+stop", text)
    return int(m.group(1)) if m else 0


def _parse_arrive_time(el: Any) -> tuple[str, bool]:
    """Return (time_text, arrives_next_day) from the arrival <span>."""
    arrives_next_day = el.find("sup") is not None
    text = el.get_text(strip=True)
    text = re.sub(r"\+\d+", "", text).strip()
    return text, arrives_next_day


def parse_results_html(
    html: str,
    origin: str,
    destination: str,
    captured_at: datetime | None = None,
) -> list[SiteResult]:
    """Parse rendered Google Flights HTML into raw SiteResult records.

    This is a pure function — no browser required. The adapter's execute()
    calls page.content() then passes the HTML here.
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

        arrive_text, arrives_next_day = ("", False)
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
            SiteResult(adapter="google_flights", payload=payload, captured_at=captured_at)
        )

    return results


class GoogleFlightsAdapter:
    name = "google_flights"
    capabilities = AdapterCapabilities(
        name="google_flights",
        supported_cabin_classes=["economy", "premium", "business", "first"],
        supports_multi_city=True,
        max_passengers=9,
    )

    async def execute(self, step: SearchStep, ctx: ExecutionContext) -> ExecutionResult:
        req = step.query
        await asyncio.sleep(_RATE_LIMIT_DELAY)

        browser_ctx = await ctx.browser.new_context(
            user_agent=(
                "flight_finder/0.1 (+mailto:niraderet@gmail.com) "
                "Mozilla/5.0 (compatible; Playwright)"
            )
        )
        page = await browser_ctx.new_page()

        try:
            await page.goto(_BASE_URL, wait_until="domcontentloaded", timeout=30_000)
            await dismiss_consent_dialog(page)

            # Select "One way" when no return date
            if req.return_date is None:
                try:
                    await page.click(sel.TRIP_TYPE_BTN, timeout=5_000)
                    await page.click(sel.ONE_WAY_OPTION, timeout=5_000)
                except Exception:
                    pass

            # Fill origin
            origin_el = page.locator(sel.ORIGIN_INPUT).first
            await origin_el.click()
            await origin_el.fill(req.origin)
            await page.keyboard.press("Enter")

            # Fill destination
            dest_el = page.locator(sel.DEST_INPUT).first
            await dest_el.click()
            await dest_el.fill(req.destination)
            await page.keyboard.press("Enter")

            # Fill departure date
            date_str = req.depart_date.strftime("%b %d %Y")
            await page.locator(sel.DATE_INPUT_DEPART).first.fill(date_str)
            try:
                await page.click(sel.DATE_DONE_BTN, timeout=5_000)
            except Exception:
                pass

            # Submit
            await page.click(sel.SEARCH_BTN, timeout=10_000)

            # Wait for at least one result card
            await wait_for_results(page, sel.FLIGHT_ITEM, timeout=30_000)
            await detect_anti_bot(page)

            html = await page.content()
            captured_at = datetime.now(timezone.utc)
            results = parse_results_html(html, req.origin, req.destination, captured_at)
            return SiteResults(results=results)

        except BlockedByAntiBot as exc:
            return SiteFailure(reason=str(exc), retryable=False, error_type="anti_bot")
        except Exception as exc:
            return SiteFailure(reason=str(exc), retryable=True, error_type="unknown")
        finally:
            await browser_ctx.close()
