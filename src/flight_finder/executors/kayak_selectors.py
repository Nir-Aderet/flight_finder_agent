from __future__ import annotations

# ── Results page ──────────────────────────────────────────────────────────────
RESULTS_LIST = "ol.Flights-Results-FlightResultsList"
FLIGHT_ITEM = "li.Flights-Results-FlightResultItem"

# Within each flight card (compatible with BeautifulSoup .select())
DEPART_TIME = "span.Flights-Results-DepartureTime"
ARRIVE_TIME = "span.Flights-Results-ArrivalTime"
AIRLINE_NAME = "span.Flights-Results-AirlineName"
DURATION = "span.Flights-Results-DurationText"
AIRPORTS = "span.Flights-Results-Airports"  # text: "SFO – CDG"
STOPS = "span.Flights-Results-StopsText"     # text: "Nonstop" | "1 stop"
PRICE = "span.Flights-Results-PriceText"     # text: "$724"

# ── Consent / anti-bot guards (Playwright locators) ───────────────────────────
CONSENT_BTNS = [
    'button[aria-label*="accept" i]',
    'button:text("Accept")',
    'button:text("I agree")',
    'button:text("Agree and proceed")',
    '#onetrust-accept-btn-handler',
]
