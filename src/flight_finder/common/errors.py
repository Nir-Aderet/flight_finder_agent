"""Shared exception taxonomy for flight-finder.

All adapter-level errors live here so retry.py and executors can agree on
which exceptions stop retrying without creating circular imports.
"""

from __future__ import annotations


class FlightFinderError(Exception):
    """Base for all flight-finder exceptions."""


class NonRetryableError(FlightFinderError):
    """Subclass this to prevent tenacity from retrying on this exception.

    Examples: BlockedByAntiBot, DisallowedByRobotsTxt, AdapterBroken.
    """


class AdapterBroken(NonRetryableError):
    """Non-retryable adapter failure (HTTP 4xx, structural site change, etc.)."""


class AdapterTimeout(FlightFinderError):
    """All retry attempts exhausted due to navigation or scraping timeouts."""
