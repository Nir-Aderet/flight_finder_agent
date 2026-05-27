# Contributing to Flight Finder Agent

## Adding a new site adapter

Each adapter is a self-contained Playwright scraper in
`src/flight_finder/executors/`. The steps below walk through everything needed
to add one end-to-end.

### 1. Check ToS and robots.txt

Before writing any code, verify that scraping is permitted:

```bash
# Check robots.txt
python scripts/test_site.py --robots https://www.example-flights.com/

# Review the site's Terms of Service manually
```

Document your findings in `docs/adapters/<site>.md` (copy
`docs/adapters/wizz_air.md` as a template). Include the robots.txt
`User-agent: *` block, any Disallow paths that matter, and your ToS summary.

The project will not accept an adapter for a site that explicitly disallows
scraping or has initiated legal action against scrapers.

### 2. Capture a fixture page

Save a static copy of the search-results HTML for unit tests:

```bash
python scripts/capture_fixture.py \
    --url "https://example-flights.com/search?from=SFO&to=CDG&date=2026-06-01" \
    --out tests/fixtures/mock_pages/example_search.html
```

### 3. Create the adapter module

Create two files:

```
src/flight_finder/executors/example.py          ← adapter logic
src/flight_finder/executors/example_selectors.py ← CSS/XPath selectors
```

**`example_selectors.py`** — one `ExampleSelectors` dataclass with all
selectors as string constants. Keeping selectors separate makes updates
cheap when the site's DOM changes.

**`example.py`** — implement the `SiteAdapter` protocol:

```python
from flight_finder.executors.base import SiteAdapter, SiteResults, SiteFailure
from flight_finder.models.capabilities import AdapterCapabilities
from flight_finder.models.plan import SearchStep
from flight_finder.executors.base import ExecutionContext

class ExampleAdapter:
    name = "example"
    capabilities = AdapterCapabilities(
        name="example",
        supported_regions=["NA", "EU"],   # see common/airports.py for region codes
        supported_cabin_classes=["economy", "business"],
    )

    async def execute(
        self, step: SearchStep, ctx: ExecutionContext
    ) -> SiteResults | SiteFailure:
        page = ctx.page
        # 1. Check robots.txt (use common/robots.py helper)
        # 2. Navigate and fill the search form
        # 3. Wait for results to load
        # 4. Parse the DOM into SiteResult objects
        # 5. Return SiteResults(results=[...])
```

Rules:
- No LLM calls inside an executor — pure Playwright only.
- Return `SiteFailure` (with `retryable=True/False`) on any error instead of
  raising; the orchestrator handles retry and re-plan logic.
- Respect the `robots.txt` check at the top of `execute()` using
  `common/robots.py`.

### 4. Add `AdapterCapabilities`

`supported_regions` must be a subset of the region codes in
`src/flight_finder/common/airports.py` (`route_region()` returns these).
The Planner uses `supported_regions` to skip adapters for routes outside
their coverage area.

Common region codes: `"NA"` (North America), `"EU"` (Europe), `"AS"`
(Asia), `"SA"` (South America), `"AF"` (Africa), `"OC"` (Oceania),
`"ME"` (Middle East).

### 5. Register the adapter

In `src/flight_finder/orchestrator/orchestrator.py`, add your adapter to the
default adapter list so the Planner knows it exists:

```python
from flight_finder.executors.example import ExampleAdapter

DEFAULT_ADAPTERS = [
    GoogleFlightsAdapter(),
    KayakAdapter(),
    WizzAirAdapter(),
    ExampleAdapter(),          # ← add here
]
```

### 6. Write unit tests

Create `tests/unit/executors/test_example.py`. Load the fixture HTML with
`BeautifulSoup` and test your parser functions directly — no browser needed:

```python
from pathlib import Path
from bs4 import BeautifulSoup
from flight_finder.executors.example import ExampleAdapter

FIXTURE = Path("tests/fixtures/mock_pages/example_search.html").read_text()

class TestExampleParser:
    def test_parses_price(self) -> None:
        soup = BeautifulSoup(FIXTURE, "html.parser")
        # call your internal parse function and assert fields
        ...
```

### 7. Add an optional live test

Create `tests/live/test_example_live.py` and mark it with `@pytest.mark.live`.
Live tests are excluded from CI (`pytest -m "not live"`) and must be run
manually:

```python
import pytest

@pytest.mark.live
async def test_example_live(browser) -> None:
    ...
```

### 8. Update docs

- Add `docs/adapters/example.md` (ToS summary, robots.txt excerpt, selector
  notes, known fragility points).
- Add a row to the **Supported sites** table in `README.md`.
- Note the new adapter in `CLAUDE.md` under **Key decisions**.

---

## Code conventions

- **Types everywhere.** All public functions must have full type annotations.
  `mypy --strict` must pass on `models/`, `normalizer/`, `ranker/`, `common/`.
- **No comments unless non-obvious.** Name things well instead.
- **Pydantic v2 for all data boundaries.** LLM output, config, CLI input,
  and cross-module data transfer use Pydantic models.
- **Ruff for lint/format.** Run `ruff check src tests` before committing.
- **One commit per milestone.** Reference the milestone in the message
  (`feat(m11): ExampleAir adapter`).

## Running the full check locally

```bash
ruff check src tests
mypy src/flight_finder/models src/flight_finder/normalizer \
     src/flight_finder/ranker src/flight_finder/common
pytest -q -m "not live"
```

All three must be green before opening a PR.
