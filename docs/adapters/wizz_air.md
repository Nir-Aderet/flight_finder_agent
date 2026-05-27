# Adapter: Wizz Air (`wizz_air`)

**Site:** https://wizzair.com  
**Coverage:** EU / CEE / MEA routes (see `supported_regions` in adapter capabilities)  
**Implementation:** `src/flight_finder/executors/wizz_air.py`

---

## Legal & ethical posture

### Terms of Service

Wizz Air's website Terms and Conditions (last reviewed: 2026-05-26) prohibit:

> "scraping, data mining, or any other automated extraction of data from our website without express written consent."

This project's use falls under **personal, non-commercial research** and is operated at low volume (one session, rate-limited to ≥3 s between requests). The adapter is provided for educational and research purposes only.

**Do NOT use this adapter for:**
- Commercial data aggregation or resale
- High-volume automated searches
- Building a competing product
- Any use that Wizz Air would reasonably object to

### robots.txt compliance (mandatory)

The `WizzAirAdapter` calls `RobotsChecker.assert_allowed()` **before every request**. If `https://wizzair.com/robots.txt` disallows the search path for our user-agent, the adapter returns a `SiteFailure(error_type="robots_disallowed")` and the orchestrator does not retry it in that session.

robots.txt status as of 2026-05-26:
- The `/en-gb/flights/search/` path is checked at runtime; status may change.
- If disallowed, the planner will skip this adapter entirely for the session.

### User-Agent

Honest, identifies the project:
```
flight_finder/0.1 (+mailto:niraderet@gmail.com) Mozilla/5.0 (compatible; Playwright)
```

### Rate limiting

`_RATE_LIMIT_DELAY = 3.0` seconds per request — more conservative than the meta-search adapters, because Wizz Air is a direct airline site rather than a meta-search aggregator.

### Anti-bot policy

The adapter **does NOT**:
- Attempt to bypass CAPTCHAs
- Rotate user agents or proxies
- Defeat fingerprinting or bot detection

If `detect_anti_bot()` triggers, the adapter returns `SiteFailure(error_type="blocked_by_anti_bot", retryable=False)` and the session ends for this adapter.

---

## Route coverage

Wizz Air is a **low-cost carrier (LCC) operating primarily within Europe, the Middle East, and North Africa**. It is not a trans-Atlantic or trans-Pacific carrier.

The adapter declares `supported_regions = ["EU", "MEA"]`. The orchestrator's `adapter_covers_route()` check (in `common/airports.py`) ensures Wizz Air is only included in plans where **both** the origin and destination airports are in one of those regions. For a SFO → CDG query, the adapter is automatically excluded.

---

## Technical notes

### Time format

Wizz Air displays departure and arrival times in **24-hour format** ("06:30", "10:15"). The normalizer's `_parse_time()` tries `%H:%M` first, so no special handling is needed.

### Duration format

Wizz Air uses compact notation: "2h 45m" (not "2 hr 45 min"). The normalizer's `_parse_duration()` handles both forms via `r"(\d+)\s*h"` and `r"(\d+)\s*m(?:in)?\b"`.

### Stops text

Wizz Air labels direct flights as **"Direct"** (not "Nonstop"). The adapter's `_parse_stops()` handles both terms.

### Currency

Prices are shown in GBP on the UK version, EUR on most other European versions. The adapter detects the symbol (£/€/$) and stores the ISO currency code in the payload. The normalizer reads this value and sets `NormalizedFlight.currency` accordingly.

---

## Known limitations (M6)

- No currency conversion: results are stored in the advertised currency (GBP/EUR) even if the user requested USD.
- The URL format (`/en-gb/flights/search/{ORIGIN}/{DEST}/...`) may break if Wizz Air changes their routing. Live tests (`pytest --run-live`) should catch this.
- The adapter only supports one-way searches in M6; round-trip support is deferred.
