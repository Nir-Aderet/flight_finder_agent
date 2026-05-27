# Flight Finder Agent

A free, open-source Python CLI (`ff`) that searches for flights across multiple
public websites using browser automation (Playwright) and a single LLM Planner
(Claude Haiku 4.5). No paid flight APIs — all data is fetched live from
Google Flights, Kayak, and Wizz Air.

[![CI](https://github.com/Nir-Aderet/flight_finder_agent/actions/workflows/ci.yml/badge.svg)](https://github.com/Nir-Aderet/flight_finder_agent/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

## How it works

1. **Planner** — Claude Haiku 4.5 turns a natural-language query into a
   `SearchPlan` (JSON list of adapter + query pairs).
2. **Executors** — deterministic Playwright scrapers fill the search form on
   each site and parse the results page.
3. **Normalizer** — raw site payloads are mapped to a `NormalizedFlight`
   schema and deduplicated across adapters.
4. **Ranker** — flights are scored by price, duration, and stops and returned
   sorted.
5. **Orchestrator** — wires everything together, handles per-step timeouts,
   re-plan retries, and an optional SQLite cache.

Architecture: **Planner–Executor + Playwright** (Arch 1, chosen in Phase 2).
Full design: [`docs/03_design.md`](docs/03_design.md).

## Quick start

### Prerequisites

- Python ≥ 3.11
- An Anthropic API key (`ANTHROPIC_API_KEY` in your environment)

### Install

```bash
git clone https://github.com/Nir-Aderet/flight_finder_agent.git
cd flight_finder_agent

# Using pip
pip install -e ".[dev]"

# Or using uv (faster)
uv sync --extra dev

# Install the Playwright browser (one-time)
playwright install chromium
```

### Run

```bash
# Basic one-way search
ff search "New York to London, June 15"

# Round-trip with cabin class
ff search "SFO to CDG, June 1-14, business class"

# See all options
ff --help
ff search --help
```

### Run tests

```bash
pytest -q                   # all fast tests (261 pass)
pytest -q -m "not live"     # same — skips opt-in live tests
pytest -m live              # opt-in: hits real sites (needs network)
```

## Running locally vs. cloud VM

### Local machine

Works on macOS, Linux, and Windows. Chromium is headless by default; set
`PLAYWRIGHT_HEADFUL=1` to watch the browser.

```bash
export ANTHROPIC_API_KEY=sk-ant-...
ff search "BUD to BCN, July 4"
```

### Low-cost cloud VM (e.g., AWS t3.micro, Hetzner CX11)

```bash
# 1. Install system deps for Chromium
sudo apt-get update && sudo apt-get install -y \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libxkbcommon0 libpangocairo-1.0-0 libasound2

# 2. Clone and install
git clone https://github.com/Nir-Aderet/flight_finder_agent.git
cd flight_finder_agent
pip install -e .
playwright install chromium --with-deps

# 3. Set your key and search
export ANTHROPIC_API_KEY=sk-ant-...
ff search "WAW to LHR, August 10"
```

Chromium runs in headless mode automatically — no display server needed.

## Supported sites

| Site | Type | Regions |
|------|------|---------|
| Google Flights | Meta-search | Global |
| Kayak | Meta-search | Global |
| Wizz Air | Direct airline | Europe / CEE |

Adding a new site: see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Configuration

Copy `config/flight_finder.yaml` and point `FF_CONFIG` at it, or pass env vars:

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | — | **Required.** Your Anthropic key. |
| `FF_LLM_MODEL` | `claude-haiku-4-5` | Primary LLM model. |
| `FF_CURRENCY` | `USD` | Display currency. |
| `FF_CACHE_TTL` | `3600` | Cache TTL in seconds (0 = disabled). |
| `FF_HEADFUL` | `false` | Show browser window. |

## Project layout

```
flight_finder_agent/
├── src/flight_finder/
│   ├── cli.py              ← typer entry point (`ff` command)
│   ├── config.py           ← pydantic-settings layered config
│   ├── models/             ← Pydantic schemas
│   ├── planner/            ← LLM Planner
│   ├── llm/                ← LLMClient protocol + Anthropic impl
│   ├── executors/          ← Playwright scrapers (Google Flights, Kayak, Wizz Air)
│   ├── normalizer/         ← raw payload → NormalizedFlight
│   ├── ranker/             ← scoring + sorting
│   ├── orchestrator/       ← run-loop, cache, re-plan
│   └── common/             ← airports, cache, logging, retry, robots
├── tests/
│   ├── unit/               ← fast, no network
│   ├── integration/        ← fake adapters + planner
│   └── live/               ← opt-in real-site tests
├── docs/                   ← design docs, adapter notes
├── scripts/                ← fixture capture, site testing helpers
└── config/                 ← default YAML config
```

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for how to add a new site adapter
and the code conventions we follow.

## License

MIT — see [`LICENSE`](LICENSE).
