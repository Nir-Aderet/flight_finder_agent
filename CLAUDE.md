# Flight Finder Agent — Claude Code Context

This file is read automatically by Claude Code on every session start.
Keep it current as milestones land.

---

## What this project is

A free, open-source Python CLI (`ff`) that searches for flights across multiple
public sites using browser automation (Playwright), a single LLM Planner agent
(Claude Haiku 4.5), and deterministic scraping adapters. No paid APIs, no
server-side flight data.

**Architecture:** Arch 1 — Planner–Executor + Playwright (chosen in Phase 2).
Full design: `docs/03_design.md`.

---

## Current state

| Phase | Status |
|---|---|
| Phase 0 — Repo setup | ✅ Done |
| Phase 1 — Architecture research | ✅ Done |
| Phase 2 — Architecture selection | ✅ Done (Arch 1 chosen) |
| Phase 3 — Detailed design | ✅ Done — see `docs/03_design.md`, `docs/03_agent_prompts.md`, `docs/03_repo_structure.md` |
| Phase 4 M1 — Skeleton | ✅ Files created; awaiting `pytest -q` green confirmation |
| Phase 4 M2 — Core models | 🔜 Next |

Active milestone tracker: `TODO.md`.

---

## Key decisions (locked)

| Decision | Value |
|---|---|
| CLI entry point | `ff` (`flight_finder.cli:app` via typer) |
| LLM — primary | `claude-haiku-4-5` |
| LLM — fallback | `claude-sonnet-4-6` (on validation failure or replan_attempt > 1) |
| Sites — M3 | Google Flights |
| Sites — M5 | Kayak |
| Sites — M6 | Wizz Air (EU/CEE only; skipped for non-European routes) |
| Base currency | USD |
| Python | ≥ 3.11 |
| Package manager | pip / uv |
| Dependency format | `pyproject.toml` (hatchling build backend) |

---

## Repo layout (abbreviated)

```
flight finder agent/
├── config/flight_finder.yaml   ← bundled defaults
├── docs/                       ← all design docs (read before coding)
├── src/flight_finder/
│   ├── cli.py                  ← typer entry point
│   ├── config.py               ← pydantic-settings layered config
│   ├── models/                 ← Pydantic schemas (M2)
│   ├── planner/                ← LLM Planner (M4)
│   ├── llm/                    ← LLMClient protocol + Anthropic impl (M4)
│   ├── executors/              ← SiteAdapter impls (M3/M5/M6)
│   ├── normalizer/             ← SiteResult → NormalizedFlight (M4)
│   ├── ranker/                 ← scoring + sorting (M7)
│   ├── orchestrator/           ← run() loop, re-plan, cache (M4/M9)
│   └── common/                 ← airports, cache, logging, ratelimit, retry, robots
├── tests/
│   ├── unit/                   ← fast, no network
│   ├── integration/            ← fakes for adapters + planner
│   ├── live/                   ← opt-in real-site tests (skipped in CI)
│   └── fixtures/mock_pages/    ← captured HTML for parser tests
├── scripts/                    ← capture_fixture.py, refresh_fx.py, test_site.py
├── CLAUDE.md                   ← this file
└── TODO.md                     ← milestone tracker (source of truth for what's next)
```

Full file-by-file table: `docs/03_repo_structure.md §2`.

---

## How to run

```bash
# Install deps (first time or after pyproject.toml changes)
pip install -e ".[dev]"
# or, if uv is installed:
uv sync --extra dev

# Install Playwright browser (first time)
playwright install chromium   # or: uv run playwright install chromium

# Run tests
pytest -q                     # or: uv run pytest -q

# Lint + type-check
ruff check src tests
mypy src/flight_finder/models src/flight_finder/normalizer src/flight_finder/ranker src/flight_finder/common

# CLI (stub until M4)
ff --help
ff version
```

---

## Coding rules

1. **One module, one responsibility.** Keep files small; prefer new files over
   growing existing ones.
2. **No LLM in the browser loop.** Executors are pure Playwright; the Planner
   only produces `SearchPlan` JSON.
3. **Pydantic v2 everywhere.** All data boundaries (LLM output, config, CLI
   input) are validated with pydantic models.
4. **Respect ToS and robots.txt.** Every adapter checks `robots.txt` at session
   start. See `docs/10_security.md` and `docs/adapters/<site>.md`.
5. **Type-annotate all public functions.** mypy strict mode is on for
   `models/`, `normalizer/`, `ranker/`, `common/`.
6. **Tests before marking a milestone done.** Each M has a stated exit
   checkpoint; don't advance until it's green.
7. **Keep commits small.** One milestone = one logical commit. Reference the
   milestone in the commit message (e.g. `feat(m2): core pydantic models`).

---

## Where to look for context

| Question | File |
|---|---|
| What does the system do? | `docs/03_design.md` |
| What prompts does the Planner use? | `docs/03_agent_prompts.md` |
| Where does X live in the repo? | `docs/03_repo_structure.md` |
| What's left to build? | `TODO.md` |
| What sites are supported and why? | `docs/03_design.md §Appendix A` |
| What does a NormalizedFlight look like? | `docs/03_design.md §5` (M2: `models/result.py`) |
| How does config layering work? | `src/flight_finder/config.py` |
