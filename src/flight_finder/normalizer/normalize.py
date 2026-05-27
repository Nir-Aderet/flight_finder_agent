from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Callable

from flight_finder.models.query import FlightSearchRequest
from flight_finder.models.result import NormalizedFlight, Segment, SiteResult

_IATA_RE = re.compile(r"^[A-Z]{3}$")


# ---------------------------------------------------------------------------
# Primitive parsers (pure, no I/O)
# ---------------------------------------------------------------------------


def _parse_price(price_text: str) -> Decimal | None:
    cleaned = re.sub(r"[^\d.]", "", price_text)
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_duration(duration_text: str) -> timedelta:
    hours = 0
    minutes = 0
    # Matches both "11 hr 15 min" and compact "2h 45m"
    h_m = re.search(r"(\d+)\s*h", duration_text)
    m_m = re.search(r"(\d+)\s*m(?:in)?\b", duration_text)
    if h_m:
        hours = int(h_m.group(1))
    if m_m:
        minutes = int(m_m.group(1))
    return timedelta(hours=hours, minutes=minutes)


def _parse_time(time_text: str, base: date) -> datetime:
    # Try 24-hour first (Wizz Air), then 12-hour AM/PM (Google Flights, Kayak)
    for fmt in ("%H:%M", "%I:%M %p", "%I %p"):
        try:
            t = datetime.strptime(time_text, fmt)
            return datetime(base.year, base.month, base.day, t.hour, t.minute)
        except ValueError:
            continue
    return datetime(base.year, base.month, base.day)


# ---------------------------------------------------------------------------
# Shared payload → NormalizedFlight (used by all adapters with standard payload)
# ---------------------------------------------------------------------------


def _normalize_standard_payload(
    site_result: SiteResult,
    request: FlightSearchRequest,
) -> NormalizedFlight | None:
    """Convert a standard SiteResult payload (shared format) to NormalizedFlight.

    Both Google Flights and Kayak emit the same payload shape, so this function
    handles both. The ``source_adapter`` is taken from ``site_result.adapter``.
    """
    p = site_result.payload
    price = _parse_price(p.get("price_text", ""))
    if price is None:
        return None

    duration = _parse_duration(p.get("duration_text", ""))
    depart_dt = _parse_time(p.get("depart_time_text", ""), request.depart_date)
    arrive_dt = depart_dt + duration

    raw_origin = str(p.get("origin", request.origin))
    raw_dest = str(p.get("destination", request.destination))
    seg_origin = raw_origin if _IATA_RE.match(raw_origin) else request.origin
    seg_dest = raw_dest if _IATA_RE.match(raw_dest) else request.destination

    segment = Segment(
        airline=p.get("airline", ""),
        flight_number="",
        origin=seg_origin,
        destination=seg_dest,
        depart_at=depart_dt,
        arrive_at=arrive_dt,
        duration=duration,
    )

    return NormalizedFlight(
        source_adapter=site_result.adapter,
        sources=[site_result.adapter],
        price=price,
        currency=request.currency,
        segments=[segment],
        stops=p.get("stops", 0),
        total_duration=duration,
        booking_url=p.get("booking_url"),
    )


# ---------------------------------------------------------------------------
# Per-adapter normalize functions (thin wrappers for future divergence)
# ---------------------------------------------------------------------------


def normalize_google_flights(
    site_result: SiteResult,
    request: FlightSearchRequest,
) -> NormalizedFlight | None:
    return _normalize_standard_payload(site_result, request)


def normalize_kayak(
    site_result: SiteResult,
    request: FlightSearchRequest,
) -> NormalizedFlight | None:
    return _normalize_standard_payload(site_result, request)


def normalize_wizz_air(
    site_result: SiteResult,
    request: FlightSearchRequest,
) -> NormalizedFlight | None:
    nf = _normalize_standard_payload(site_result, request)
    if nf is None:
        return None
    # Use the currency detected from the price symbol (GBP/EUR) rather than
    # the request's default USD, since Wizz Air prices are not in USD.
    detected_currency = str(site_result.payload.get("currency", request.currency))
    return nf.model_copy(update={"currency": detected_currency})


# ---------------------------------------------------------------------------
# Dispatch table and public entry point
# ---------------------------------------------------------------------------

_NORMALIZERS: dict[str, Callable[[SiteResult, FlightSearchRequest], NormalizedFlight | None]] = {
    "google_flights": normalize_google_flights,
    "kayak": normalize_kayak,
    "wizz_air": normalize_wizz_air,
}


def normalize_results(
    site_results: list[SiteResult],
    request: FlightSearchRequest,
) -> list[NormalizedFlight]:
    normalized: list[NormalizedFlight] = []
    for r in site_results:
        fn = _NORMALIZERS.get(r.adapter)
        if fn is not None:
            nf = fn(r, request)
            if nf is not None:
                normalized.append(nf)
    return normalized
