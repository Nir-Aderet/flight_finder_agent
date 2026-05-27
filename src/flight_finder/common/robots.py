"""robots.txt compliance helper.

Fetches and caches per-host robots.txt files for the session, using
asyncio.to_thread so the blocking urllib.robotparser.read() call does
not stall the async event loop.
"""

from __future__ import annotations

import asyncio
import urllib.robotparser
from urllib.parse import urljoin

from flight_finder.common.errors import NonRetryableError


class RobotsDisallowed(NonRetryableError):
    """Raised when robots.txt disallows the requested path for our user-agent."""


class RobotsChecker:
    """Session-scoped robots.txt cache.

    One instance per orchestrator run; create a new instance for each run
    so the cache does not carry state between sessions.
    """

    def __init__(self, user_agent: str = "flight_finder") -> None:
        self._ua = user_agent
        self._cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    async def is_allowed(self, base_url: str, path: str) -> bool:
        """Return True if our user-agent may fetch *path* on *base_url*."""
        parser = await self._get_parser(base_url)
        return parser.can_fetch(self._ua, path)

    async def assert_allowed(self, base_url: str, path: str) -> None:
        """Raise RobotsDisallowed if *path* is not permitted."""
        if not await self.is_allowed(base_url, path):
            raise RobotsDisallowed(
                f"robots.txt on {base_url} disallows {path!r} for '{self._ua}'"
            )

    async def _get_parser(
        self, base_url: str
    ) -> urllib.robotparser.RobotFileParser:
        if base_url not in self._cache:
            robots_url = urljoin(base_url, "/robots.txt")
            parser = await asyncio.to_thread(_load_robots, robots_url)
            self._cache[base_url] = parser
        return self._cache[base_url]


def _load_robots(robots_url: str) -> urllib.robotparser.RobotFileParser:
    """Blocking helper called via asyncio.to_thread."""
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception:
        # If robots.txt is unreachable, assume everything is allowed
        # (conservative: fail-open so we do not block on network errors).
        pass
    return rp
