from __future__ import annotations

from datetime import timedelta

from flight_finder.models.result import NormalizedFlight

_BUCKET = timedelta(minutes=5)


def _dedup_key(flight: NormalizedFlight) -> tuple[str, str, str, str]:
    """Compute a hashable identity key for a flight.

    Uses the first segment's (airline, rounded-depart-minute, origin, dest).
    Rounding to 5-minute buckets tolerates minor display differences between
    sites (e.g. "8:30 AM" vs "8:28 AM").
    """
    if not flight.segments:
        return (flight.source_adapter, "", "", "")
    seg = flight.segments[0]
    d = seg.depart_at
    bucket_minutes = (d.hour * 60 + d.minute) // 5
    return (
        seg.airline.strip().lower(),
        f"{d.date().isoformat()}:{bucket_minutes}",
        seg.origin,
        seg.destination,
    )


def _merge(flights: list[NormalizedFlight]) -> NormalizedFlight:
    best = min(flights, key=lambda f: f.price)
    seen: set[str] = set()
    all_sources: list[str] = []
    for f in flights:
        for s in f.sources:
            if s not in seen:
                seen.add(s)
                all_sources.append(s)
    return best.model_copy(update={"sources": all_sources})


def dedup_flights(flights: list[NormalizedFlight]) -> list[NormalizedFlight]:
    """Merge flights with the same identity from different adapters.

    For each group of flights sharing the same dedup key:
    - Keep the lowest-priced version.
    - Combine the ``sources`` lists so downstream callers know which adapters
      found this flight.

    Flights with unique keys pass through unchanged.
    """
    groups: dict[tuple[str, str, str, str], list[NormalizedFlight]] = {}
    for flight in flights:
        key = _dedup_key(flight)
        groups.setdefault(key, []).append(flight)

    result: list[NormalizedFlight] = []
    for group in groups.values():
        result.append(_merge(group) if len(group) > 1 else group[0])
    return result
