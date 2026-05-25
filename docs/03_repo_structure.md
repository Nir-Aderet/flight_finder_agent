# Phase 3 — Repository Structure

Proposed layout for `src/`, `tests/`, `scripts/`, and `config/`. Optimized for Claude Code navigability: small files with single responsibilities, predictable names, and explicit boundaries between deterministic code and the (single) LLM agent.

Companion: `03_design.md` (the *what*), `03_agent_prompts.md` (the prompts).

---

## 1. Top-level tree

```
flight finder agent/
├── .github/
│   └── workflows/
│       └── ci.yml                         # Phase 5 — lint, type, test on push
├── config/
│   └── flight_finder.yaml                 # bundled defaults
├── docs/
│   ├── 01_research_notes.md
│   ├── 02_architectures_comparison.md
│   ├── 03_design.md
│   ├── 03_agent_prompts.md
│   ├── 03_repo_structure.md               # this file
│   └── adapters/                          # per-site notes (ToS, robots.txt, quirks)
│       ├── google_flights.md
│       ├── kayak.md
│       └── wizz_air.md
├── scripts/
│   ├── capture_fixture.py                 # save a real page's HTML for tests
│   ├── refresh_fx.py                      # update bundled FX rates
│   └── test_site.py                       # smoke-test a single adapter
├── src/
│   └── flight_finder/                     # importable package
│       ├── __init__.py
│       ├── __main__.py                    # `python -m flight_finder ...`
│       ├── cli.py                         # typer app, entry point
│       ├── config.py                      # pydantic-settings layering
│       ├── orchestrator/
│       │   ├── __init__.py
│       │   ├── orchestrator.py            # the run() loop, re-plan, cache check
│       │   ├── audit.py                   # AuditRecord, run-id tracking
│       │   └── exceptions.py              # domain-specific errors
│       ├── planner/
│       │   ├── __init__.py
│       │   ├── planner.py                 # Planner class; calls LLMClient
│       │   ├── prompts.py                 # system + user templates (from 03_agent_prompts.md)
│       │   └── replan.py                  # FailureContext helpers, reason vocabulary
│       ├── llm/
│       │   ├── __init__.py
│       │   ├── client.py                  # LLMClient Protocol
│       │   ├── anthropic_client.py        # default impl
│       │   └── ollama_client.py           # optional local fallback
│       ├── executors/
│       │   ├── __init__.py
│       │   ├── base.py                    # SiteAdapter Protocol, ExecutionContext
│       │   ├── playwright_base.py         # shared browser/page helpers
│       │   ├── google_flights.py          # adapter impl (meta-search)
│       │   ├── google_flights_selectors.py
│       │   ├── kayak.py                    # adapter impl (meta-search)
│       │   ├── kayak_selectors.py
│       │   ├── wizz_air.py                 # adapter impl (direct LCC, EU/CEE)
│       │   └── wizz_air_selectors.py
│       ├── normalizer/
│       │   ├── __init__.py
│       │   ├── normalize.py               # SiteResult → NormalizedFlight
│       │   ├── filter.py                  # hard cuts (max_stops, blocked airlines, ...)
│       │   ├── dedup.py                   # cross-adapter dedup
│       │   └── fx.py                      # currency conversion (static rates)
│       ├── ranker/
│       │   ├── __init__.py
│       │   ├── score.py                   # main score() function
│       │   └── weights.py                 # default weights + override loading
│       ├── models/
│       │   ├── __init__.py
│       │   ├── query.py                   # FlightSearchRequest, IATACode, CurrencyCode
│       │   ├── plan.py                    # SearchPlan, SearchStep
│       │   ├── result.py                  # SiteResult, Segment, NormalizedFlight
│       │   ├── orchestrator.py            # OrchestratorResult, AuditRecord, FailureContext
│       │   └── capabilities.py            # AdapterCapabilities
│       └── common/
│           ├── __init__.py
│           ├── airports.py                # IATA lookup (city → airport code)
│           ├── cache.py                   # aiosqlite-backed cache
│           ├── logging.py                 # structlog config
│           ├── ratelimit.py               # per-host token bucket
│           ├── retry.py                   # tenacity wrappers
│           └── robots.py                  # robots.txt fetch + parse + cache
├── tests/
│   ├── unit/
│   │   ├── models/                        # one test file per schema module
│   │   ├── normalizer/
│   │   ├── ranker/
│   │   ├── planner/                       # mocked LLM
│   │   └── executors/                     # parser-only tests against fixtures
│   ├── integration/
│   │   ├── test_orchestrator.py           # fakes for adapters + Planner
│   │   ├── test_cache.py
│   │   └── test_replan_loop.py
│   ├── live/                              # opt-in, --run-live, skipped in CI
│   │   ├── test_google_flights_live.py
│   │   ├── test_kayak_live.py
│   │   └── test_wizz_air_live.py
│   ├── fixtures/
│   │   └── mock_pages/
│   │       ├── google_flights_search.html
│   │       ├── kayak_search.html
│   │       └── wizz_air_search.html
│   └── conftest.py                        # shared pytest fixtures, fakes
├── .env.example                           # ANTHROPIC_API_KEY placeholder
├── .gitignore                             # already exists
├── .python-version                        # 3.12
├── LICENSE                                # MIT, already exists
├── pyproject.toml                         # uv/pip metadata, deps, console-script
├── README.md                              # already exists
├── TODO.md                                # already exists
└── flight_finder_system_prompt.txt        # the spec
```

---

## 2. Module-by-module responsibilities

| Module / file | Responsibility | Touches LLM? | Touches network? |
|---|---|---|---|
| `cli.py` | Parse args, build `FlightSearchRequest` or pass NL through, call `Orchestrator.run()`, print results. | No | No |
| `config.py` | Layered config loading (defaults → YAML → user YAML → env → CLI). | No | No |
| `orchestrator/orchestrator.py` | The `run()` loop: cache check → Planner → executors → normalizer → ranker → cache write. Owns the re-plan loop. | No (delegates to `planner/`) | No (delegates to `executors/`) |
| `orchestrator/audit.py` | `AuditRecord` accumulation, run-id, timing. | No | No |
| `planner/planner.py` | Build prompts, call `LLMClient`, validate `SearchPlan`, handle one-shot retry + Haiku→Sonnet escalation. | **Yes** | Yes (LLM API) |
| `planner/prompts.py` | The exact prompt strings from `03_agent_prompts.md`. Template-rendered with `today_iso`, `adapter_catalog_json`, `prior_failures`. | No | No |
| `planner/replan.py` | Build `FailureContext` from `ExecutionResult` failures; consult `reason` vocabulary. | No | No |
| `llm/client.py` | `LLMClient` Protocol with `complete_json(system, user, schema) → BaseModel`. | No | No |
| `llm/anthropic_client.py` | Default impl using the `anthropic` SDK. | Yes | Yes |
| `llm/ollama_client.py` | Optional local impl. | Yes | localhost only |
| `executors/base.py` | `SiteAdapter` Protocol, `ExecutionContext`, `ExecutionResult` (Sum type: `SiteResults \| SiteFailure`). | No | No |
| `executors/playwright_base.py` | `BrowserPool`, `with_context()` helper, `dismiss_consent_dialog()`, screenshot/trace helpers, detection of anti-bot pages. | No | Browser only |
| `executors/google_flights.py` | The Google Flights adapter end-to-end (navigate, fill, submit, parse). | No | **Yes (target site)** |
| `executors/google_flights_selectors.py` | All CSS / role selectors for Google Flights. Editable in isolation when the site changes. | No | No |
| `executors/kayak.py` / `kayak_selectors.py` | Same shape as above for Kayak (meta-search). | No | **Yes** |
| `executors/wizz_air.py` / `wizz_air_selectors.py` | Same shape for Wizz Air (direct LCC). `capabilities.supported_regions = ["EU","CEE"]`; the Planner skips it for non-applicable routes. | No | **Yes** |
| `normalizer/normalize.py` | Per-adapter `to_normalized(SiteResult) → NormalizedFlight`. | No | No |
| `normalizer/filter.py` | Hard-cut filters from `FlightSearchRequest`. | No | No |
| `normalizer/dedup.py` | `(airline, flight_number, depart_at)` merge. | No | No |
| `normalizer/fx.py` | Currency conversion against bundled rate table. | No | No |
| `ranker/score.py` | `score_all(flights, weights) → list[NormalizedFlight]`. | No | No |
| `ranker/weights.py` | Default `RankingWeights`, loader from config. | No | No |
| `models/*.py` | All pydantic models from `03_design.md` §5.1. Pure data, no behavior. | No | No |
| `common/airports.py` | Static IATA lookup (city → airport). Bundled CSV; loaded at startup. | No | No |
| `common/cache.py` | `aiosqlite` cache: `get(key, ttl) -> OrchestratorResult \| None`, `put(key, result)`. | No | Disk only |
| `common/logging.py` | `structlog` setup; `get_logger()`. | No | No |
| `common/ratelimit.py` | `PerHostLimiter`: async semaphore + jittered sleep. | No | No |
| `common/retry.py` | `@retry_on_network_error`, `@retry_on_selector_miss` decorators (tenacity). | No | No |
| `common/robots.py` | Fetch + parse `robots.txt`, cache per-session. | No | **Yes** (one request per host per session) |

---

## 3. Mapping from design sections to code

Lets you find the code for any section of `03_design.md` in one jump.

| Design section | Primary code locations |
|---|---|
| §2 Architecture, §3 Roles | `orchestrator/orchestrator.py`, `planner/planner.py`, `executors/base.py` |
| §3.1 Planner | `planner/`, `llm/`, `models/plan.py`, `models/capabilities.py` |
| §3.2 Orchestrator | `orchestrator/orchestrator.py`, `orchestrator/audit.py` |
| §3.3 Executors | `executors/` |
| §3.4 Normalizer | `normalizer/` |
| §3.5 Ranker | `ranker/` |
| §4 Tech stack | `pyproject.toml`, `.python-version` |
| §5.1 Schemas | `models/` |
| §5.2 Data flow | `orchestrator/orchestrator.py` (the `run()` method) |
| §6.1 Playwright usage | `executors/playwright_base.py`, `executors/<site>_selectors.py` |
| §6.2 Rate limits / retries | `common/ratelimit.py`, `common/retry.py` |
| §6.3 Captcha policy | `executors/playwright_base.py::detect_anti_bot()`, raises `BlockedByAntiBot` from `orchestrator/exceptions.py` |
| §7 Ranking | `ranker/score.py`, `ranker/weights.py` |
| §7 Dedup | `normalizer/dedup.py` |
| §7 Filters | `normalizer/filter.py` |
| §8 Config | `config.py`, `config/flight_finder.yaml` |
| §8 Adding sites | `executors/<site>.py` + `executors/<site>_selectors.py` + `tests/unit/executors/test_<site>.py` + `tests/fixtures/mock_pages/<site>_search.html` |
| §9 Logging | `common/logging.py` |
| §9 Tests | `tests/` (mirrors `src/flight_finder/`) |
| §10 robots.txt | `common/robots.py` |
| §10 Personal-use posture | `README.md`, `docs/adapters/*.md` |
| §11 Roadmap milestones | tracked in `TODO.md` Phase 4; one branch per milestone |

---

## 4. Design rules

A handful of conventions that keep the codebase predictable for both humans and Claude Code:

- **One responsibility per file.** Adapter parser logic and selector strings live in *separate* files. Filters, dedup, and ranking are in *separate* modules. This minimizes the blast radius of any edit.
- **Schemas are read-only data.** `models/` has no behavior. All transformations are pure functions in `normalizer/` or `ranker/`.
- **Async all the way down.** Anything that does I/O is `async def`. `cli.py` is the only place that calls `asyncio.run()`.
- **LLM is touched in exactly one place.** Only `planner/planner.py` and `llm/*.py` import an LLM SDK. If any other module ever needs the LLM, add a tool to the Planner instead — do not import from `llm/` outside `planner/`.
- **Network I/O is touched in exactly two places.** `executors/` (target sites) and `llm/` (LLM provider). Plus `common/robots.py` (one robots.txt fetch per host per session). Nothing else.
- **No global state.** All shared state (config, logger, browser pool, cache, rate limiter) is wired in via `ExecutionContext` passed explicitly.
- **Tests mirror src.** A path under `tests/unit/X/` exists for every `src/flight_finder/X/`.
- **Live tests are opt-in.** Anything under `tests/live/` runs only with `pytest --run-live`. CI never runs live tests.

---

## 5. Why this layout works well with Claude Code

- **Predictable navigation.** Asking Claude to "edit the Kayak selectors" maps to a single file (`executors/kayak_selectors.py`). No grepping required.
- **Small files.** Most modules are ≤ 200 lines; Claude can hold each one fully in context when refactoring.
- **Schema-first.** Generating new code is usually "given this pydantic model, scaffold X" — Claude does this well.
- **Tests next to types.** When Claude edits a model, it can find the corresponding test file at the mirror path without searching.
- **Single LLM call site.** Refactors to LLM prompts or providers happen in `planner/` and `llm/` only — they don't ripple.
- **Adapter pattern is a template.** Adding a new site is a recipe Claude can follow without architectural reasoning: copy `google_flights.py` + `_selectors.py` + the matching test + the matching fixture, then edit. The orchestrator picks the new adapter up automatically via the config registry.

---

## 6. `pyproject.toml` skeleton (preview)

Not authoritative until M1, but for reference:

```toml
[project]
name = "flight-finder"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "anthropic>=0.40",
  "playwright>=1.48",
  "pydantic>=2.9",
  "pydantic-settings>=2.6",
  "typer>=0.13",
  "structlog>=24.4",
  "aiosqlite>=0.20",
  "tenacity>=9.0",
  "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.3", "pytest-asyncio>=0.24", "pytest-playwright>=0.5",
       "ruff>=0.7", "mypy>=1.13"]
ollama = ["ollama>=0.3"]

[project.scripts]
flight-finder = "flight_finder.cli:app"

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.mypy]
strict = true
files = ["src/flight_finder/models", "src/flight_finder/ranker", "src/flight_finder/normalizer"]
```
