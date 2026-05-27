from __future__ import annotations

from flight_finder.config import RankingWeights
from flight_finder.models.query import FlightSearchRequest
from flight_finder.models.result import NormalizedFlight


def _min_max_norm(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5] * len(values)
    span = hi - lo
    return [(v - lo) / span for v in values]


def score_all(
    flights: list[NormalizedFlight],
    weights: RankingWeights,
    request: FlightSearchRequest,
) -> list[NormalizedFlight]:
    """Score and sort *flights* by weighted preference.

    Returns a new list with :attr:`NormalizedFlight.score` populated, sorted
    descending (best first).
    """
    if not flights:
        return []

    preferred = {a.lower() for a in request.preferred_airlines}

    norm_prices = _min_max_norm([float(f.price) for f in flights])
    norm_durations = _min_max_norm([f.total_duration.total_seconds() for f in flights])
    norm_stops = _min_max_norm([float(f.stops) for f in flights])

    scored: list[NormalizedFlight] = []
    for i, f in enumerate(flights):
        price_s = 1.0 - norm_prices[i]
        duration_s = 1.0 - norm_durations[i]
        stops_s = 1.0 - norm_stops[i]
        # No preferred departure window in M7 — neutral component.
        depart_s = 0.5

        if not preferred:
            airline_s = 0.5
        else:
            flight_airlines = {seg.airline.lower() for seg in f.segments}
            airline_s = 1.0 if flight_airlines & preferred else 0.0

        raw = (
            weights.price * price_s
            + weights.duration * duration_s
            + weights.stops * stops_s
            + weights.depart_time * depart_s
            + weights.airline * airline_s
        )
        scored.append(f.model_copy(update={"score": raw}))

    scored.sort(key=lambda x: x.score or 0.0, reverse=True)
    return scored
