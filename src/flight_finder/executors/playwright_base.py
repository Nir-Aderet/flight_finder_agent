from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page

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
