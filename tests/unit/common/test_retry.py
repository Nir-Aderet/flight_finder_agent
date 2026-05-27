from __future__ import annotations

import pytest
from tenacity import wait_none

from flight_finder.common.errors import NonRetryableError
from flight_finder.common.retry import adapter_retry


# Helper: zero-wait retry for fast tests
def _fast_retry():
    return adapter_retry(wait=wait_none())


class TestAdapterRetry:
    async def test_succeeds_on_first_attempt(self) -> None:
        call_count = 0

        async def succeeds() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        result: str | None = None
        async for attempt in _fast_retry():
            with attempt:
                result = await succeeds()
        assert result == "ok"
        assert call_count == 1

    async def test_retries_on_transient_error(self) -> None:
        call_count = 0

        async def fails_twice_then_succeeds() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("transient")
            return "ok"

        result: str | None = None
        async for attempt in _fast_retry():
            with attempt:
                result = await fails_twice_then_succeeds()
        assert result == "ok"
        assert call_count == 3

    async def test_does_not_retry_non_retryable(self) -> None:
        call_count = 0

        async def raises_non_retryable() -> None:
            nonlocal call_count
            call_count += 1
            raise NonRetryableError("blocked")

        with pytest.raises(NonRetryableError):
            async for attempt in _fast_retry():
                with attempt:
                    await raises_non_retryable()

        assert call_count == 1  # must not retry

    async def test_exhausts_max_attempts_and_reraises(self) -> None:
        call_count = 0

        async def always_fails() -> None:
            nonlocal call_count
            call_count += 1
            raise RuntimeError("always fails")

        with pytest.raises(RuntimeError, match="always fails"):
            async for attempt in _fast_retry():
                with attempt:
                    await always_fails()

        assert call_count == 3  # 3 total attempts

    async def test_subclass_of_non_retryable_not_retried(self) -> None:
        """Subclasses of NonRetryableError (e.g. BlockedByAntiBot) must not be retried."""
        from flight_finder.executors.base import BlockedByAntiBot

        call_count = 0

        async def raises_blocked() -> None:
            nonlocal call_count
            call_count += 1
            raise BlockedByAntiBot("captcha")

        with pytest.raises(BlockedByAntiBot):
            async for attempt in _fast_retry():
                with attempt:
                    await raises_blocked()

        assert call_count == 1
