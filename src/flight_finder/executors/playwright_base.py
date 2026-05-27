from __future__ import annotations

import contextlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import BrowserContext, Page

from flight_finder.executors.base import BlockedByAntiBot

_ANTI_BOT_PATTERNS = [
    r"unusual traffic",
    r"captcha",
    r"verify you.re human",
    r"are you a robot",
    r"security check",
    r"I.m not a robot",
]

_CONSENT_SELECTORS = [
    'button:text("Accept all")',
    'button:text("I agree")',
    '[aria-label="Accept all"]',
    'button:text("Agree")',
]


async def dismiss_consent_dialog(page: Page, timeout: int = 3000) -> None:
    """Try each known consent-button selector; silently skip if none found."""
    for sel in _CONSENT_SELECTORS:
        try:
            btn = page.locator(sel).first
            await btn.click(timeout=timeout)
            return
        except Exception:
            continue


async def detect_anti_bot(page: Page) -> None:
    """Raise BlockedByAntiBot if the page looks like an anti-bot gate."""
    content = (await page.content()).lower()
    for pat in _ANTI_BOT_PATTERNS:
        if re.search(pat, content):
            raise BlockedByAntiBot(f"Anti-bot pattern detected: {pat!r}")


async def wait_for_results(page: Page, selector: str, timeout: int = 30_000) -> None:
    """Wait until at least one element matching *selector* is visible."""
    await page.wait_for_selector(selector, state="visible", timeout=timeout)


async def save_debug_artifacts(
    browser_ctx: "BrowserContext",
    page: "Page",
    adapter_name: str,
) -> None:
    """Save Playwright trace zip and screenshot to ~/.flight_finder/traces/.

    Called on failure when ExecutionContext.debug is True. Silently swallows
    any errors so the original exception is not masked.
    """
    trace_dir = Path.home() / ".flight_finder" / "traces"
    with contextlib.suppress(Exception):
        trace_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    with contextlib.suppress(Exception):
        await browser_ctx.tracing.stop(
            path=str(trace_dir / f"{adapter_name}_{ts}.zip")
        )
    with contextlib.suppress(Exception):
        await page.screenshot(path=str(trace_dir / f"{adapter_name}_{ts}.png"))
