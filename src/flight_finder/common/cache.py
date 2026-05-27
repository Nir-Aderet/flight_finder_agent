from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import TYPE_CHECKING

import aiosqlite

if TYPE_CHECKING:
    from flight_finder.models.orchestrator import OrchestratorResult
    from flight_finder.models.query import FlightSearchRequest

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS cache (
    cache_key TEXT PRIMARY KEY,
    payload   TEXT NOT NULL,
    cached_at REAL NOT NULL
)
"""


class FlightCache:
    """Async SQLite result cache keyed by SHA-256 of the normalized search request."""

    def __init__(self, path: Path, ttl_seconds: int = 3600) -> None:
        self._path = path
        self._ttl = ttl_seconds
        self._db: aiosqlite.Connection | None = None

    async def open(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._path)
        await self._db.execute(_CREATE_TABLE)
        await self._db.commit()

    async def close(self) -> None:
        if self._db is not None:
            await self._db.close()
            self._db = None

    async def __aenter__(self) -> FlightCache:
        await self.open()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    @staticmethod
    def make_key(request: FlightSearchRequest) -> str:
        data = {
            "origin": request.origin,
            "destination": request.destination,
            "depart_date": str(request.depart_date),
            "return_date": str(request.return_date) if request.return_date else None,
            "passengers": request.passengers,
            "cabin": request.cabin,
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

    async def get(self, request: FlightSearchRequest) -> OrchestratorResult | None:
        from flight_finder.models.orchestrator import OrchestratorResult

        if self._db is None:
            raise RuntimeError("Cache is not open; call open() or use as context manager")
        key = self.make_key(request)
        async with self._db.execute(
            "SELECT payload, cached_at FROM cache WHERE cache_key = ?", (key,)
        ) as cur:
            row = await cur.fetchone()
        if row is None:
            return None
        payload, cached_at = row
        if time.time() - cached_at > self._ttl:
            return None
        return OrchestratorResult.model_validate_json(payload)

    async def set(self, request: FlightSearchRequest, result: OrchestratorResult) -> None:
        if self._db is None:
            raise RuntimeError("Cache is not open; call open() or use as context manager")
        key = self.make_key(request)
        await self._db.execute(
            "INSERT OR REPLACE INTO cache (cache_key, payload, cached_at) VALUES (?, ?, ?)",
            (key, result.model_dump_json(), time.time()),
        )
        await self._db.commit()

    async def invalidate(self, request: FlightSearchRequest) -> None:
        if self._db is None:
            raise RuntimeError("Cache is not open; call open() or use as context manager")
        key = self.make_key(request)
        await self._db.execute("DELETE FROM cache WHERE cache_key = ?", (key,))
        await self._db.commit()
