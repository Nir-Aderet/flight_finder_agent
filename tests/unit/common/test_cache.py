from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from flight_finder.common.cache import FlightCache
from flight_finder.models.orchestrator import OrchestratorResult
from flight_finder.models.query import FlightSearchRequest
from flight_finder.models.result import NormalizedFlight, Segment


_REQUEST = FlightSearchRequest(
    origin="SFO",
    destination="CDG",
    depart_date=date(2026, 6, 1),
    passengers=1,
    cabin="economy",
)

_FLIGHT = NormalizedFlight(
    source_adapter="fake",
    price=Decimal("849"),
    currency="USD",
    segments=[
        Segment(
            airline="Test Air",
            origin="SFO",
            destination="CDG",
            depart_at=datetime(2026, 6, 1, 8, 30, tzinfo=timezone.utc),
            arrive_at=datetime(2026, 6, 2, 6, 45, tzinfo=timezone.utc),
            duration=timedelta(hours=11, minutes=15),
        )
    ],
    stops=0,
    total_duration=timedelta(hours=11, minutes=15),
)

_RESULT = OrchestratorResult(
    query=_REQUEST,
    flights=[_FLIGHT],
    audit=[],
    replan_attempts=0,
)


class TestFlightCacheMakeKey:
    def test_same_request_same_key(self) -> None:
        key1 = FlightCache.make_key(_REQUEST)
        key2 = FlightCache.make_key(_REQUEST)
        assert key1 == key2

    def test_different_origin_different_key(self) -> None:
        other = _REQUEST.model_copy(update={"origin": "JFK"})
        assert FlightCache.make_key(_REQUEST) != FlightCache.make_key(other)

    def test_different_date_different_key(self) -> None:
        other = _REQUEST.model_copy(update={"depart_date": date(2026, 7, 1)})
        assert FlightCache.make_key(_REQUEST) != FlightCache.make_key(other)

    def test_key_is_64_char_hex(self) -> None:
        key = FlightCache.make_key(_REQUEST)
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)


class TestFlightCacheMiss:
    async def test_get_returns_none_on_empty_db(self, tmp_path: Path) -> None:
        async with FlightCache(tmp_path / "cache.db") as cache:
            result = await cache.get(_REQUEST)
        assert result is None


class TestFlightCacheHit:
    async def test_set_then_get_returns_result(self, tmp_path: Path) -> None:
        async with FlightCache(tmp_path / "cache.db") as cache:
            await cache.set(_REQUEST, _RESULT)
            retrieved = await cache.get(_REQUEST)
        assert retrieved is not None
        assert len(retrieved.flights) == 1
        assert retrieved.flights[0].price == Decimal("849")

    async def test_result_roundtrip_preserves_fields(self, tmp_path: Path) -> None:
        async with FlightCache(tmp_path / "cache.db") as cache:
            await cache.set(_REQUEST, _RESULT)
            retrieved = await cache.get(_REQUEST)
        assert retrieved is not None
        assert retrieved.query.origin == "SFO"
        assert retrieved.query.destination == "CDG"
        assert retrieved.flights[0].total_duration == timedelta(hours=11, minutes=15)

    async def test_second_set_overwrites_first(self, tmp_path: Path) -> None:
        other_result = _RESULT.model_copy(update={"replan_attempts": 1})
        async with FlightCache(tmp_path / "cache.db") as cache:
            await cache.set(_REQUEST, _RESULT)
            await cache.set(_REQUEST, other_result)
            retrieved = await cache.get(_REQUEST)
        assert retrieved is not None
        assert retrieved.replan_attempts == 1


class TestFlightCacheTTL:
    async def test_expired_entry_returns_none(self, tmp_path: Path) -> None:
        async with FlightCache(tmp_path / "cache.db", ttl_seconds=60) as cache:
            await cache.set(_REQUEST, _RESULT)
            # Simulate time passing beyond TTL
            with patch("flight_finder.common.cache.time.time", return_value=9_999_999_999.0):
                retrieved = await cache.get(_REQUEST)
        assert retrieved is None

    async def test_within_ttl_returns_result(self, tmp_path: Path) -> None:
        async with FlightCache(tmp_path / "cache.db", ttl_seconds=3600) as cache:
            await cache.set(_REQUEST, _RESULT)
            retrieved = await cache.get(_REQUEST)
        assert retrieved is not None


class TestFlightCacheInvalidate:
    async def test_invalidate_removes_entry(self, tmp_path: Path) -> None:
        async with FlightCache(tmp_path / "cache.db") as cache:
            await cache.set(_REQUEST, _RESULT)
            await cache.invalidate(_REQUEST)
            result = await cache.get(_REQUEST)
        assert result is None

    async def test_invalidate_nonexistent_key_does_not_raise(self, tmp_path: Path) -> None:
        async with FlightCache(tmp_path / "cache.db") as cache:
            await cache.invalidate(_REQUEST)  # should not raise


class TestFlightCacheErrors:
    async def test_get_without_open_raises(self, tmp_path: Path) -> None:
        cache = FlightCache(tmp_path / "cache.db")
        with pytest.raises(RuntimeError, match="not open"):
            await cache.get(_REQUEST)

    async def test_set_without_open_raises(self, tmp_path: Path) -> None:
        cache = FlightCache(tmp_path / "cache.db")
        with pytest.raises(RuntimeError, match="not open"):
            await cache.set(_REQUEST, _RESULT)

    async def test_creates_parent_dir_if_missing(self, tmp_path: Path) -> None:
        deep_path = tmp_path / "a" / "b" / "cache.db"
        async with FlightCache(deep_path) as cache:
            await cache.set(_REQUEST, _RESULT)
            result = await cache.get(_REQUEST)
        assert result is not None
