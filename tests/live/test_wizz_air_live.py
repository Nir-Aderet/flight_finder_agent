from __future__ import annotations

from datetime import date

import pytest
from playwright.async_api import async_playwright

from flight_finder.executors.base import ExecutionContext, SiteResults
from flight_finder.executors.wizz_air import WizzAirAdapter
from flight_finder.models.plan import SearchStep
from flight_finder.models.query import FlightSearchRequest


@pytest.mark.live
async def test_wizz_air_live_ltn_to_bud() -> None:
    """End-to-end: navigate Wizz Air, parse real results for LTN→BUD."""
    req = FlightSearchRequest(
        origin="LTN",
        destination="BUD",
        depart_date=date(2026, 8, 1),
    )
    step = SearchStep(adapter="wizz_air", query=req, priority=0)
    adapter = WizzAirAdapter()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = ExecutionContext(browser=browser)
        result = await adapter.execute(step, ctx)
        await browser.close()

    assert isinstance(result, SiteResults), f"Expected SiteResults, got: {result}"
    assert len(result.results) > 0, "No results returned from Wizz Air"
    first = result.results[0]
    assert first.adapter == "wizz_air"
    assert "price_text" in first.payload
    assert "airline" in first.payload
    assert "depart_time_text" in first.payload
