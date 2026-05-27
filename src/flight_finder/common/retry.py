"""Tenacity-based retry helpers for site adapters."""

from __future__ import annotations

from typing import Any

import tenacity

from flight_finder.common.errors import NonRetryableError


def adapter_retry(wait: Any = None) -> tenacity.AsyncRetrying:
    """Return an AsyncRetrying policy for site adapters.

    - 3 total attempts (2 retries).
    - Exponential backoff: ~1 s → ~4 s (with jitter).
    - Does NOT retry on NonRetryableError (BlockedByAntiBot, DisallowedByRobotsTxt, etc.).
    - reraise=True: the last exception propagates after all attempts are exhausted.

    Args:
        wait: Override the wait strategy (useful in tests to avoid sleeping).
              If None, uses the production exponential-backoff schedule.
    """
    if wait is None:
        wait = tenacity.wait_exponential(
            multiplier=0.25, exp_base=4, min=1, max=16
        ) + tenacity.wait_random(0, 1)

    return tenacity.AsyncRetrying(
        stop=tenacity.stop_after_attempt(3),
        wait=wait,
        retry=tenacity.retry_if_not_exception_type(NonRetryableError),
        reraise=True,
    )
