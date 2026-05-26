from __future__ import annotations

# ── Results page ──────────────────────────────────────────────────────────────
RESULTS_LIST = "ul.Rk10dc"
FLIGHT_ITEM = "li.pIav2d"

# Within each flight card (CSS selectors, compatible with BeautifulSoup .select())
DEPART_TIME = "span.wtdjmc"
ARRIVE_TIME = "span.XWcVob"
AIRLINE_NAME = "span.h1fkLb"
DURATION = "div.AdWm1c"
AIRPORTS = "div.Akvoyn"   # text: "SFO – CDG"
STOPS = "span.ogfYpf"     # text: "Nonstop" | "1 stop" | "2 stops"
PRICE = "div.YMlIz"       # text: "$849"

# ── Search form (Playwright locators used during live navigation) ──────────────
TRIP_TYPE_BTN = '[aria-label="Round trip, Change ticket type."]'
ONE_WAY_OPTION = 'li[data-value="2"]'
ORIGIN_INPUT = '[aria-label="Where from?"]'
DEST_INPUT = '[aria-label="Where to?"]'
DATE_INPUT_DEPART = '[placeholder="Departure"]'
DATE_DONE_BTN = 'button[aria-label*="Done"]'
SEARCH_BTN = 'button[aria-label="Search"]'
