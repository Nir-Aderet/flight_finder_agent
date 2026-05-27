from __future__ import annotations

from flight_finder.models.query import FlightSearchRequest
from flight_finder.models.result import NormalizedFlight


def apply_filters(
    flights: list[NormalizedFlight],
    request: FlightSearchRequest,
) -> list[NormalizedFlight]:
    """Apply hard-cut filters from *request*. Returns only flights that pass all filters."""
    blocked = {a.lower() for a in request.blocked_airlines}
    out: list[NormalizedFlight] = []
    for f in flights:
        if request.max_stops is not None and f.stops > request.max_stops:
            continue
        if request.max_price is not None and f.price > request.max_price:
            continue
        if blocked and any(seg.airline.lower() in blocked for seg in f.segments):
            continue
        out.append(f)
    return out
