"""CSS selectors for Wizz Air search-results page.

These target the mock fixture used in unit tests. The live page uses
similar class names but may diverge; update alongside live HTML captures.
"""

FLIGHT_LIST = "ol.flight-list"
FLIGHT_ITEM = "li.flight-list__item"
DEPART_TIME = "time.departure-time"
ARRIVE_TIME = "time.arrival-time"
AIRLINE_NAME = "span.airline-name"
DURATION = "span.flight-duration"
DEPART_AIRPORT = "span.origin-iata"
ARRIVE_AIRPORT = "span.destination-iata"
STOPS = "span.stops-text"
PRICE = "span.price-amount"

# Consent / cookie-banner dismissal buttons
CONSENT_BTNS: list[str] = [
    'button[data-test="accept-cookies"]',
    'button:text("Accept all cookies")',
    'button:text("Accept")',
    '[aria-label*="accept" i]',
]
