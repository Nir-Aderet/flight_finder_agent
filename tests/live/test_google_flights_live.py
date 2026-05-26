from __future__ import annotations

from datetime import date

import pytest
from playwright.async_api import async_playwright

from flight_finder.executors.base import ExecutionContext, SiteResults
from flight_finder.executors.google_flights import GoogleFlightsAdapter
from flight_finder.models.plan import SearchStep
from flight_finder.models.query import FlightSearchRequest


@pytest.mark.live
async def test_google_flights_live_sfo_to_cdg() -> None:
    """End-to-end: navigate Google Flights, parse real results for SFO→CDG."""
    req = FlightSearchRequest(
        origin="SFO",
        destination="CDG",
        depart_date=date(2026, 6, 1),
    )
    step = SearchStep(adapter="google_flights", query=req, priority=0)
    adapter = GoogleFlightsAdapter()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = ExecutionContext(browser=browser)
        result = await adapter.execute(step, ctx)
        await browser.close()

    assert isinstance(result, SiteResults), f"Expected SiteResults, got: {result}"
    assert len(result.results) > 0, "No results returned from Google Flights"
    first = result.results[0]
    assert first.adapter == "google_flights"
    assert "price_text" in first.payload
    assert "airline" in first.payload
