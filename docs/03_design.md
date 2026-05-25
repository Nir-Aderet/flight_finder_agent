# Phase 3 — Detailed Design

**Architecture:** Arch 1 — Planner–Executor + Playwright (selected in Phase 2; see `02_architectures_comparison.md`).

This document is the implementation-ready design. It is structured per Task 4 of `flight_finder_system_prompt.txt`. Companion docs:

- `03_agent_prompts.md` — LLM prompts for the Planner agent.
- `03_repo_structure.md` — file-by-file repository layout.

---

## 1. Overview

The flight finder is a Python CLI that, given an origin/destination/date query, scrapes 1+ public flight search sites in parallel using Playwright, normalizes the results into a shared schema, ranks them by a user-configurable score, and prints the top N. A single LLM agent (the Planner) sits in front of the executors to (a) parse natural-language queries into structured parameters, (b) decide which sites to query, and (c) re-plan when an executor fails or returns nothing useful. All site-specific scraping logic is deterministic Playwright code — no LLM is in the browser loop.

Trade-offs accepted (from Phase 2): brittleness to UI redesigns is the maintenance tax; the upside is the lowest LLM bill of any candidate, the simplest mental model, and the cleanest fit with Claude Code's edit-test-refactor loop. Stagehand / browser-use stay on the table as future per-site fallbacks if scrapers become too volatile to maintain.

---

## 2. High-level system architecture

### Components

- **CLI / Entry point** — accepts either a NL string or structured flags, instantiates the Orchestrator, prints results.
- **Orchestrator** — pure Python coordinator. Runs the planner → executors → normalizer → ranker pipeline. Handles retries, the re-planning loop, and the cache.
- **Planner agent** — the only LLM in the system. Inputs: raw user query (NL or structured) + capabilities of available site adapters + any prior failure context. Output: a `SearchPlan` (which sites, what params, what order).
- **Site executors (one per site)** — deterministic Playwright modules implementing the `SiteAdapter` interface. Inputs: a `SearchStep`. Outputs: a list of raw `SiteResult` records or a structured failure.
- **Normalizer** — pure functions converting heterogeneous `SiteResult`s into a uniform `NormalizedFlight` shape (canonical airport codes, ISO durations, UTC timestamps, currency normalization to a configured base currency).
- **Ranker** — pure functions scoring and sorting normalized flights against the user's preference weights.
- **Cache** — SQLite, keyed by `(site, origin, destination, depart_date, return_date)`. TTL configurable (default 1 h).
- **Common utilities** — IATA airport lookup table, rate limiter, structured logger, retry/backoff helpers.

### Logical diagram (described)

```
                       ┌──────────────────────────┐
                       │           CLI            │
                       │  (NL string OR --flags)  │
                       └─────────────┬────────────┘
                                     │ FlightSearchRequest
                                     ▼
                       ┌──────────────────────────┐
                       │      Orchestrator        │
                       │ (re-plan loop, caching)  │
                       └──────┬───────────────────┘
                              │ raw query + adapter capabilities + prior failures
                              ▼
                       ┌──────────────────────────┐
                       │      Planner (LLM)       │
                       │      → SearchPlan        │
                       └──────┬───────────────────┘
                              │ SearchPlan = [SearchStep, ...]
                              ▼
            ┌─────────────────┴─────────────────┐
            │                                   │
            │     asyncio.gather over           │
            │     SiteAdapter.execute(step)     │
            │                                   │
   ┌────────┴────────┐ ┌──────────────┐ ┌──────┴─────────┐
   │ GoogleFlightsExe│ │  KayakExec   │ │  WizzAirExec   │
   │   Playwright    │ │  Playwright  │ │   Playwright   │
   └────────┬────────┘ └──────┬───────┘ └────────┬───────┘
            │                 │                  │
            ▼                 ▼                  ▼
      List[SiteResult]   List[SiteResult]   List[SiteResult]
            │                 │                  │
            └────────┬────────┴──────────────────┘
                     │ merge
                     ▼
              ┌─────────────────┐
              │   Normalizer    │  → List[NormalizedFlight]
              └────────┬────────┘
                       │
                       ▼
              ┌─────────────────┐
              │     Ranker      │  → ordered List[NormalizedFlight]
              └────────┬────────┘
                       │
                       ▼
                  Top-N output

Re-planning loop: if Orchestrator collects zero usable flights from all executors,
it calls Planner again with the failure context to revise the SearchPlan
(loosen dates, swap sites, etc.). Bounded to N_REPLAN attempts (default 2).
```

---

## 3. Agent roles and responsibilities

### 3.1 Planner (LLM agent)

- **Inputs.**
  - `raw_query: str | FlightSearchRequest` — user query, NL or structured.
  - `adapters: list[AdapterCapabilities]` — what each available site supports (countries, currencies, max passengers, multi-city, etc.).
  - `prior_failures: list[FailureContext]` — empty on first call; populated on re-planning.
  - `replan_attempt: int` — 0 on first call.
- **Output.** `SearchPlan` (JSON, validated by pydantic):
  - `query: FlightSearchRequest` — fully resolved (city names → IATA, "next weekend" → ISO dates, etc.).
  - `steps: list[SearchStep]` — one per `(adapter, parameter-variant)` to execute.
  - `notes: str` — optional human-readable rationale.
- **Decision logic.**
  - On first call: parse intent, resolve ambiguous terms, fan out to all configured adapters.
  - On re-plan (`prior_failures` non-empty): identify which adapters failed and why. Choose one of: retry same adapter with looser params (e.g., ±1 day), drop the adapter for this session, swap in a different adapter, or abort with a structured "no results found" error.
- **Implementation.** Claude Haiku for first-pass planning (cheap, fast, structured output). Falls through to Sonnet only if Haiku's output fails pydantic validation twice.

### 3.2 Orchestrator (deterministic)

- **Inputs.** `FlightSearchRequest` (or NL string).
- **Output.** `OrchestratorResult` containing ranked flights and an audit trail (which adapters ran, latencies, failures).
- **Decision logic.**
  1. Compute cache key. If hit and within TTL, return cached `OrchestratorResult`.
  2. Call Planner → `SearchPlan`.
  3. `asyncio.gather` site executors with per-step timeouts.
  4. Collect partial results. If any executor returned results, proceed to Normalizer + Ranker.
  5. If all executors failed AND `replan_attempt < N_REPLAN`: build `FailureContext`, call Planner again, go to step 3.
  6. Cache and return.

### 3.3 Site executor (one per site, deterministic)

Implements:

```python
class SiteAdapter(Protocol):
    name: str                         # "google_flights", "kayak", ...
    capabilities: AdapterCapabilities

    async def execute(
        self,
        step: SearchStep,
        ctx: ExecutionContext,
    ) -> ExecutionResult: ...
```

- **`ExecutionContext`** carries a shared `playwright.async_api.Browser`, the rate limiter, the logger, and the cache reference.
- **`ExecutionResult`** is either `SiteResults(results=[...])` or `SiteFailure(reason=..., retryable=bool)`.
- **Decision logic per executor.**
  1. Check `robots.txt` for the target host (cached for the session); abort if disallowed.
  2. Acquire a rate-limit token.
  3. Open a Playwright page. Navigate. Fill form fields. Submit.
  4. Wait for results. Handle cookie banners / consent walls.
  5. Extract result cards into raw `SiteResult` records.
  6. Close the page. Release the rate-limit token.
  7. Return.

### 3.4 Normalizer (pure functions)

- **Input.** `list[SiteResult]` (heterogeneous shapes).
- **Output.** `list[NormalizedFlight]`.
- **Decision logic.** Per-site adapter functions map raw fields to the canonical schema. Currency conversion uses a static fallback rate table (refreshed weekly via `scripts/refresh_fx.py`) — flagged as a known limitation.

### 3.5 Ranker (pure functions)

- **Input.** `list[NormalizedFlight]`, `RankingWeights`.
- **Output.** Sorted `list[NormalizedFlight]` plus a per-flight `score: float`.
- **Decision logic.** Linear combination of normalized sub-scores (price, duration, stops, departure-time preference, airline preference). See §7.

---

## 4. Tooling and tech stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.12+ | Async, type hints, broad lib support. |
| Browser automation | Playwright (Apache 2.0), `playwright` Python package | Phase 1 winner. Native async, robust selectors. |
| LLM SDK | `anthropic` (official), abstracted behind a `LLMClient` protocol | Default provider; swap to `ollama` for fully local. |
| Schemas | pydantic v2 | Run-time validation of LLM output, free JSON schema gen for prompts. |
| CLI | `typer` (built on click) | Auto-help, type-driven flags, async-friendly. |
| Config | `pydantic-settings` + YAML | Layered (defaults → file → env). |
| Logging | `structlog` | Structured JSON, easy to grep. |
| Cache | `aiosqlite` | Async SQLite, no server, file-based. |
| Tests | `pytest`, `pytest-asyncio`, `pytest-playwright` | Standard. |
| Lint / type | `ruff`, `mypy --strict` on `src/flight_finder/models/` | Strict where it matters. |
| Package mgmt | `uv` (recommended) or `pip` + `pyproject.toml` | `uv` is fast; `pip` is universal. |

### How Claude Code is used

- Scaffold modules from pydantic schemas (Claude generates skeletons that conform).
- Iteratively refine site executors against captured-HTML fixtures in `tests/fixtures/mock_pages/`.
- Add types and ruff fixes in bulk.
- Generate per-site README sections under `docs/adapters/<site>.md` as adapters land.

---

## 5. Data flow and interfaces

### 5.1 Pydantic schemas (sketches)

```python
# models/query.py
class FlightSearchRequest(BaseModel):
    origin: IATACode                  # "SFO"
    destination: IATACode             # "CDG"
    depart_date: date
    return_date: date | None = None
    passengers: int = 1
    cabin: Literal["economy", "premium", "business", "first"] = "economy"
    max_stops: int | None = None
    preferred_airlines: list[str] = []
    blocked_airlines: list[str] = []
    currency: CurrencyCode = "USD"

# models/plan.py
class SearchStep(BaseModel):
    adapter: str                      # "google_flights" | "kayak" | ...
    query: FlightSearchRequest
    priority: int = 0                 # higher = run sooner (in case of throttling)

class SearchPlan(BaseModel):
    query: FlightSearchRequest        # resolved
    steps: list[SearchStep]
    notes: str = ""

# models/result.py
class SiteResult(BaseModel):
    """Raw site-specific result. Free-form per adapter."""
    adapter: str
    payload: dict                     # adapter-defined
    captured_at: datetime

class Segment(BaseModel):
    airline: str
    flight_number: str
    origin: IATACode
    destination: IATACode
    depart_at: datetime               # tz-aware
    arrive_at: datetime               # tz-aware
    duration: timedelta

class NormalizedFlight(BaseModel):
    source_adapter: str
    price: Decimal
    currency: CurrencyCode
    segments: list[Segment]           # 1+ for one-way; 2+ groups for return
    stops: int                        # = len(segments) - 1 per direction
    total_duration: timedelta
    booking_url: str | None
    score: float | None = None        # populated by ranker

# models/orchestrator.py
class FailureContext(BaseModel):
    adapter: str
    reason: str                       # human-readable
    retryable: bool
    attempt: int

class OrchestratorResult(BaseModel):
    query: FlightSearchRequest
    flights: list[NormalizedFlight]   # ranked
    audit: list[AuditRecord]          # per-step latency, success/failure, etc.
```

### 5.2 End-to-end flow

1. **CLI** parses args into either a NL string or a `FlightSearchRequest`. Calls `Orchestrator.run(input)`.
2. **Orchestrator** checks cache (key = SHA256 over normalized request). On miss, calls `Planner.plan(input, adapters, prior_failures=[])`.
3. **Planner** returns `SearchPlan`. Orchestrator validates via pydantic.
4. **Orchestrator** runs `asyncio.gather(*[adapter.execute(step) for step in plan.steps])` with `asyncio.timeout(per_step_seconds)`.
5. **Executors** each return `ExecutionResult`. Failures are collected; results are collected.
6. **If zero results AND replan_attempt < N_REPLAN:** Orchestrator builds `FailureContext` list and goes back to step 3 with `prior_failures` populated.
7. **Else:** Orchestrator passes raw results to **Normalizer**, then **Ranker**, caches the `OrchestratorResult`, returns it.
8. **CLI** prints the top-N (default 10) and optional verbose audit.

---

## 6. Browser automation and scraping strategy

### 6.1 Playwright usage

- **One browser per process.** Launched once at orchestrator startup with `chromium.launch(headless=True)`. Reused across executors.
- **One `BrowserContext` per executor invocation.** Isolates cookies / localStorage between sites and runs.
- **Locator strategy.** Prefer role-based selectors (`page.get_by_role("button", name="Search")`) and accessible-name selectors over CSS. Falls back to `data-*` attributes when present, raw CSS only as a last resort. Selector strings live in `executors/<site>/selectors.py` so a UI redesign means editing one file, not the whole adapter.
- **Date pickers.** The single hardest UI element. Strategy: type into the date input directly when possible; click into the calendar grid only when the input is read-only.
- **Cookie banners / GDPR consent.** Each adapter has a `dismiss_consent_dialog()` helper called immediately after navigation. The helper tries a known list of selectors for "Accept all" / "Reject all" buttons.
- **Dynamic content / infinite scroll.** Use `page.wait_for_selector(..., state="visible")` for the first card, then `page.evaluate("...")` to scroll if more results are needed.
- **Tracing.** On failure (in `dev` profile), save a Playwright trace zip to `~/.flight_finder/traces/`. Off by default in `prod`.
- **Screenshots.** On failure, save a PNG. Off by default; toggle via `--debug`.

### 6.2 Rate limiting, retries, errors

- **Per-host rate limiter.** Token bucket: default 1 request / 2 s per host, configurable per adapter. Implemented as an `asyncio.Semaphore` + sleep with jitter.
- **Retries.** `tenacity` decorator on `execute()`: max 3 attempts, exponential backoff (1 s, 4 s, 16 s) + jitter. Retry on timeout / 5xx / specific selector-not-found errors. **Do not** retry on 4xx (treat as adapter brokenness, surface to planner).
- **Timeouts.** Per-page navigation: 30 s. Whole `execute()` call: 90 s. Whole orchestrator run: 5 min.
- **Detection of blocks.** Watch for: HTTP 429, HTTP 403, "unusual traffic" page-text patterns, CAPTCHA iframe presence. Any of these → fail fast as a non-retryable failure, signal planner.

### 6.3 Captchas / blocking

- **Policy.** **Do not** attempt to defeat CAPTCHAs or other anti-bot defenses. When detected, the adapter raises `BlockedByAntiBot` and reports up; the planner is told this adapter is unavailable for the session. Bypassing anti-bot puts the project on the wrong side of both ToS and the legal grey zone.
- **If a CAPTCHA appears repeatedly,** the adapter is auto-disabled for the rest of the session. The user is told in the audit summary.

---

## 7. Ranking, filtering, business logic

### 7.1 Filters (hard cuts, applied before ranking)

- `max_stops` (if set in request).
- `blocked_airlines`.
- `max_price` (optional CLI flag).
- Filtering happens in `normalizer/filter.py` immediately after normalization.

### 7.2 Ranking score

Each normalized flight receives a score in `[0, 1]`, with 1 being best:

```
score = w_price * (1 - normalize(price))
      + w_duration * (1 - normalize(total_duration))
      + w_stops * (1 - normalize(stops, [0, max_observed]))
      + w_depart_time * gauss(depart_at, preferred_depart_window)
      + w_airline * airline_preference_bonus
```

- Normalization is min-max across the *current result set* (not a global baseline).
- Default weights live in `config/flight_finder.yaml` and are user-overridable.
- Default: `price=0.45, duration=0.25, stops=0.15, depart_time=0.10, airline=0.05`.

### 7.3 Cross-site dedup

Two flights are treated as the same physical flight if all `Segment`s match on `(airline, flight_number, depart_at)`. Duplicates are merged, keeping the lowest price and recording all source adapters in `NormalizedFlight.sources: list[str]`.

---

## 8. Configuration and extensibility

### 8.1 Configuration layering

`pydantic-settings` resolves in this order (later wins):

1. Hard-coded defaults in `config.py`.
2. Bundled YAML at `config/flight_finder.yaml`.
3. User YAML at `~/.flight_finder/config.yaml` (if exists).
4. Environment variables prefixed `FLIGHT_FINDER_*`.
5. CLI flags.

Secrets (e.g., `ANTHROPIC_API_KEY`) come only from env or a user-managed `.env` (never bundled).

### 8.2 Adding a new site

Adding a site is intended to be the most common change. Steps:

1. Create `src/flight_finder/executors/<site>.py` implementing `SiteAdapter`.
2. Create `src/flight_finder/executors/<site>_selectors.py` for the CSS/role strings.
3. Register the adapter name in `config/flight_finder.yaml` under `adapters:`.
4. Add a fixture in `tests/fixtures/mock_pages/<site>_search.html` and a unit test in `tests/unit/executors/test_<site>.py` that runs the parser against the fixture.
5. Optionally: add `docs/adapters/<site>.md` with notes on quirks, ToS, robots.txt status.

No core code changes required — the orchestrator discovers adapters by entry point.

### 8.3 Adding a new user preference

User preferences are part of `FlightSearchRequest`. To add one:

1. Add a field to `FlightSearchRequest` with a default that preserves current behavior.
2. Surface it in the CLI via a `typer` option.
3. Reference it in the relevant filter or ranker function.

---

## 9. Observability, logging, testing

### 9.1 Logging

- **`structlog`** with a JSON renderer in `prod`, a console renderer in `dev`.
- Every log line carries: `run_id` (UUID per orchestrator run), `adapter`, `step_index`.
- Every adapter logs three structured events per execution: `adapter.start`, `adapter.result_count` (or `adapter.failure`), `adapter.duration_ms`.
- LLM calls log: `llm.call.start`, `llm.call.tokens` (input/output), `llm.call.cost_usd` (computed from a static price table).

### 9.2 Tests

| Layer | Test type | What it covers |
|---|---|---|
| `models/` | Unit | pydantic schemas: required fields, value bounds, edge cases (e.g., return_date before depart_date). |
| `planner/` | Unit, mocked LLM | Given a fixed LLM response, the planner emits a valid `SearchPlan`. Failure mode: when LLM returns invalid JSON, the planner falls through to Sonnet. |
| `executors/<site>` | Unit | Parser runs against a captured-HTML fixture; expected `SiteResult` list emerges. *No live HTTP.* |
| `executors/<site>` | Integration (opt-in) | Live test against the real site, behind `--run-live`. Skipped in CI. |
| `normalizer/`, `ranker/` | Unit | Pure functions, table-driven tests. |
| `orchestrator/` | Integration, fakes | Wires planner + 2 fake adapters; verifies the re-plan loop, cache hits, and timeout behavior. |

### 9.3 Capturing fixtures

A helper script `scripts/capture_fixture.py <site> <query>` runs the adapter once, saves the rendered HTML and a JSON dump of the extracted `SiteResult` list, and writes both to `tests/fixtures/mock_pages/`. This is how parser tests get realistic input without depending on live sites.

---

## 10. Security, compliance, and ethics

### 10.1 Personal-use posture

This project is designed for **personal, non-commercial use** by a single developer. All design decisions assume that posture. Distribution as a hosted service is **out of scope** under this design and would require revisiting every section below.

### 10.2 robots.txt and ToS

- Every adapter calls `robotparser.RobotFileParser` against the target host at session start. The parsed allow/disallow rules are cached for the session.
- If `robots.txt` disallows the result-listing path, the adapter raises `DisallowedByRobotsTxt` and the planner removes that adapter from the plan.
- `User-Agent` is set to a constant identifying the project + a contact email read from config (`flight_finder/0.1 (+mailto:<configured email>)`). No spoofing of Chrome/Firefox.
- `From` header carries the same contact email.
- ToS posture per site is summarized in `docs/adapters/<site>.md` with last-checked date. The README links to these and reminds the user that ToS can change and is their responsibility to re-verify.

### 10.3 Rate limiting (recap)

- Default ≤1 request / 2 s per host. Tunable per adapter, but the default is the upper bound — adapters can only ask for *slower*, never faster.
- Aggressive caching (§5) reduces duplicate requests.

### 10.4 Data handling

- No PII is collected from the user beyond what they type into the CLI.
- The cache stores only query parameters and flight results, both of which are non-sensitive market data. Path: `~/.flight_finder/cache.db`.
- No telemetry. No phone-home.

### 10.5 LLM API key handling

- `ANTHROPIC_API_KEY` is read from env or `~/.flight_finder/.env`. **Never** committed.
- `.gitignore` already excludes `.env`. README will state this explicitly.

---

## 11. Implementation roadmap

Phase 4 milestones (mirroring `TODO.md`, expanded with concrete deliverables and definitions of done).

| M | Deliverable | Definition of done |
|---|---|---|
| M1 | Project skeleton | `pyproject.toml` with deps; `uv venv` works; `pytest -q` runs and passes 0 tests; `playwright install chromium` succeeds; `flight-finder --help` works via `typer`. |
| M2 | Core pydantic models (`models/`) | All schemas in §5.1 implemented; `mypy --strict` clean; unit tests cover edge cases. |
| M3 | First site executor (Google Flights) | Given a captured HTML fixture, parser produces a non-empty `list[SiteResult]` that validates. Live `--run-live` integration test passes for one origin/destination pair. |
| M4 | Orchestrator + planner (single-adapter loop) | `flight-finder "SFO to CDG on 2026-06-01"` runs end-to-end against the live Google Flights adapter and prints normalized results. Planner uses Anthropic Haiku, falls through to Sonnet on validation failure. |
| M5 | Second adapter (Kayak) | Same end-to-end CLI call now fans out to 2 meta-search adapters in parallel. Cross-adapter dedup works (§7). ToS restrictive — expect occasional anti-bot trips; §6.3 policy applies (drop for session, never bypass). |
| M6 | Third adapter (Wizz Air) | First *direct-airline* adapter. Validates that the `SiteAdapter` pattern fits direct LCC sites, not just meta-search. Introduces `route_region(origin, destination)` in `common/airports.py` and `supported_regions` filtering in the Planner so Wizz Air is skipped for non-European routes. |
| M7 | Ranking + filters | `--max-stops`, `--max-price`, `--prefer-airline` CLI flags; ranking weights from config; ranked output. |
| M8 | Observability | structlog JSON logs; `--debug` flag enables Playwright trace + screenshots on failure; LLM cost ledger printed in `--verbose`. |
| M9 | Caching + re-plan loop | SQLite cache hits avoid re-querying within TTL; re-plan loop verified by a fake adapter that returns zero results on first call. |
| M10 | Tests + CI | Unit-test coverage of `models/`, `normalizer/`, `ranker/` ≥ 90%. CI workflow (`.github/workflows/ci.yml`) runs `ruff`, `mypy`, `pytest -q` (skipping `--run-live`) on every push. |

### Suggested branch / PR cadence

- One branch per milestone (`m1-skeleton`, `m2-models`, …).
- Each branch lands a PR with the milestone's tests green.
- Tag `v0.1.0` after M10.

### Out of scope for v0.1

- Multi-city itineraries.
- Booking (we only *find*, never *book*).
- Mobile app or web UI.
- Anything that touches Stagehand / browser-use (deferred per Phase 2 decision).
- Distribution / packaging beyond `pip install .` from source.

---

## Appendix A — Decisions locked in for M1

All four open questions were resolved before M1 begins:

1. **LLM models.** Anthropic Claude Haiku 4.5 by default; Sonnet 4.6 as a one-step escalation on validation failure or when `replan_attempt > 1`. Configurable via env (`FLIGHT_FINDER_PLANNER_MODEL`, `FLIGHT_FINDER_PLANNER_FALLBACK_MODEL`).
2. **Initial site list.** Three adapters: Google Flights (M3), Kayak (M5), Wizz Air (M6). Mix of two meta-search aggregators and one direct LCC to validate the adapter pattern across both shapes. All three have restrictive ToS — the design treats anti-bot trips as expected and drops the offending adapter for the session per the §6.3 policy. Wizz Air is region-restricted (Europe/CEE) and the Planner uses the new `route_region()` helper to skip it for non-applicable routes. Ryanair was considered and excluded due to its history of ToS-enforcement litigation; easyJet, Pegasus, and Skyscanner remain on the candidate list for future milestones.
3. **Default base currency.** USD. All cross-currency results are converted to USD via the static FX table in `normalizer/fx.py`. User can override per-run via `--currency`.
4. **CLI name.** `ff` — short, fast to type. Defined as a console-script entry in `pyproject.toml`. (Note: `ff` is a common alias for unrelated tools on some systems; if that becomes a problem, swap to `flight-finder` is a one-line `pyproject.toml` edit.)
