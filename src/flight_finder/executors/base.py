from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from playwright.async_api import Browser

from flight_finder.models.capabilities import AdapterCapabilities
from flight_finder.models.plan import SearchStep
from flight_finder.models.result import SiteResult


class BlockedByAntiBot(Exception):
    """Raised when the adapter detects a CAPTCHA or anti-bot page."""


class DisallowedByRobotsTxt(Exception):
    """Raised when robots.txt disallows the target path."""


@dataclass
class ExecutionContext:
    browser: Browser
    rate_limiter: Any = None
    logger: Any = None


@dataclass
class SiteResults:
    results: list[SiteResult]


@dataclass
class SiteFailure:
    reason: str
    retryable: bool
    error_type: str = "unknown"


ExecutionResult = SiteResults | SiteFailure


@runtime_checkable
class SiteAdapter(Protocol):
    name: str
    capabilities: AdapterCapabilities

    async def execute(
        self,
        step: SearchStep,
        ctx: ExecutionContext,
    ) -> ExecutionResult: ...
