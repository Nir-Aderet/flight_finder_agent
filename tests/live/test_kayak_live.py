from __future__ import annotations

from datetime import date

import pytest
from playwright.async_api import async_playwright

from flight_finder.executors.base import ExecutionContext, SiteResults
from flight_finder.executors.kayak import KayakAdapter
from flight_finder.models.plan import SearchStep
from flight_finder.models.query import FlightSearchRequest


@pytest.mark.live
async def test_kayak_live_sfo_to_cdg() -> None:
    """End-to-end: navigate Kayak, parse real results for SFO→CDG."""
    req = FlightSearchRequest(
        origin="SFO",
        destination="CDG",
        depart_date=date(2026, 6, 1),
    )
    step = SearchStep(adapter="kayak", query=req, priority=0)
    adapter = KayakAdapter()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = ExecutionContext(browser=browser)
        result = await adapter.execute(step, ctx)
        await browser.close()

    assert isinstance(result, SiteResults), f"Expected SiteResults, got: {result}"
    assert len(result.results) > 0, "No results returned from Kayak"
    first = result.results[0]
    assert first.adapter == "kayak"
    assert "price_text" in first.payload
    assert "airline" in first.payload
