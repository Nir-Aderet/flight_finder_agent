# Flight Finder Agent — TODO

High-level roadmap. Each phase has a clear deliverable file, an exit checkpoint, and concrete next tasks. Do not start a phase until the previous phase's checkpoint is met.

Source of truth for the workflow: `flight_finder_system_prompt.txt`.

---

## Phase 0 — Project Setup ✅

Goal: a clean, version-controlled repo skeleton ready for design and implementation work.

- [x] Connect project folder (`C:\Users\Nir\Documents\Claude\Projects\flight finder agent`)
- [x] Add system prompt (`flight_finder_system_prompt.txt`)
- [x] Create folder skeleton: `docs/`, `src/`, `tests/`, `scripts/`
- [x] Add `.gitignore`
- [x] Add `README.md`
- [x] Add `LICENSE` (MIT)
- [x] `git init` and first commit (done on host)
- [x] Create GitHub repo and push — https://github.com/Nir-Aderet/flight_finder_agent (public)

**Exit checkpoint:** ✅ repo skeleton committed and pushed to GitHub.

---

## Phase 1 — Architecture Research ✅

Goal: a written survey of agent architectures applicable to free, browser-based flight search.

- [x] Survey AI agent architectures (6 patterns: single-agent/ReAct, tool-calling, planner–executor, multi-agent role-based, RAG-augmented, browser-using)
- [x] Survey free/open-source browser-automation stacks (Playwright, browser-use, Stagehand, Skyvern, Selenium/Puppeteer, Bright Data)
- [x] Audit scraping viability for 8 travel sites with ToS/robots.txt/anti-bot notes
- [x] Compile findings → `docs/01_research_notes.md`

**Exit checkpoint:** ✅ deliverable in `docs/01_research_notes.md`. Provisional shortlist of 3 candidate architectures identified for Phase 2.

---

## Phase 2 — Architecture Selection ✅

Goal: a top-3 comparison table, a recommended choice, and your explicit go-ahead.

- [x] Rubric locked: 25/20/20/15/10/10 (Free-OSS / Robustness / Impl complexity / Maintainability / Ethics / Scalability)
- [x] Scored top 3 candidates from Phase 1 against the rubric
- [x] Produced comparison + scoring tables + per-arch summaries → `docs/02_architectures_comparison.md`
- [x] Recommendation issued: Arch 3 (Hybrid)
- [x] **CHOICE RECORDED:** **Arch 1 — Planner–Executor + Playwright**

**Exit checkpoint:** ✅ user chose Arch 1; recorded at top of `docs/02_architectures_comparison.md`.

### Scores (for reference)
1. Hybrid Playwright + Stagehand — 4.25 *(recommended, not chosen)*
2. **Planner–Executor + Playwright — 4.10 *(chosen)***
3. Multi-agent + browser-use — 3.05

---

## Phase 3 — Detailed Design ✅

Goal: an implementation-ready design document for the chosen architecture (Arch 1 — Planner–Executor + Playwright).

- [x] Full design doc with all 11 sections + pydantic schema sketches → `docs/03_design.md`
- [x] Planner system prompt, user templates (initial + re-plan), output schema, few-shot examples, token budget → `docs/03_agent_prompts.md`
- [x] Repository layout, file-by-file responsibilities, design→code map, `pyproject.toml` skeleton → `docs/03_repo_structure.md`
- [x] **CHECKPOINT — USER APPROVED** the three design docs.
- [x] Open questions in §Appendix A resolved:
  - LLM models: **Haiku 4.5 default, Sonnet 4.6 fallback**
  - Initial sites: **Google Flights (M3) + Kayak (M5) + Wizz Air (M6)** — two meta-search + one direct LCC. Ryanair considered and excluded due to litigation history.
  - Default currency: **USD**
  - CLI name: **`ff`**

**Exit checkpoint:** user has approved all three design docs. Any open questions in §Appendix A of `03_design.md` should be resolved (or explicitly deferred) before M1.

---

## Phase 4 — Implementation

Goal: a working flight finder agent, built in milestones so each step is reviewable.

- [ ] **M1 — Skeleton:** create `src/` layout per `docs/03_repo_structure.md`; `pyproject.toml` (or `requirements.txt`); install Playwright; first `pytest` run green on empty tests.
- [x] **M2 — Core models:** implement `FlightSearchRequest`, `FlightResult`, and supporting types with unit tests.
- [x] **M3 — First site scraper (Google Flights):** implement end-to-end — navigate, fill form, parse results, normalize into `FlightResult`.
- [x] **M4 — Orchestrator + minimal agent loop:** wire user query → orchestrator → Planner (Haiku) → Google Flights → normalized results.
- [ ] **M5 — Second scraper (Kayak):** add as second meta-search adapter; validates cross-adapter dedup.
- [ ] **M6 — Third scraper (Wizz Air):** first *direct-airline* adapter (proves the pattern beyond meta-search). Introduces `route_region()` in `common/airports.py` and `supported_regions` filtering in the Planner so Wizz Air is skipped for non-European routes.
- [ ] **M7 — Ranking & filtering:** implement scoring (price, duration, stops) and user-side filters.
- [ ] **M8 — Observability:** structured logging, retry/backoff, error taxonomy.
- [ ] **M9 — Caching + re-plan loop:** SQLite cache, bounded re-plan attempts, verified with a fake adapter.
- [ ] **M10 — Tests + CI:** unit tests for parsers/normalizers; mocked integration tests for the orchestrator; CI workflow on push.

**Exit checkpoint:** end-to-end search runs from CLI against at least two sites and returns ranked results.

---

## Phase 5 — Hardening & GitHub CI

Goal: a maintainable, CI-backed repo.

- [ ] Set up GitHub Actions: lint (`ruff`), type-check (`mypy`), test (`pytest`).
- [ ] Add CONTRIBUTING notes (how to add a new site scraper).
- [ ] Document running locally and in a low-cost cloud VM.
- [ ] Tag a `v0.1.0` release.

**Exit checkpoint:** CI passes on `main`; `v0.1.0` tagged.

---

## Cross-cutting (apply throughout)

- Respect site ToS and robots.txt at every step.
- Keep `README.md` updated as phases land.
- Prefer small, reviewable commits; one phase milestone per branch is fine.
- Use Claude Code for iterative refactors, type annotations, and test scaffolding.

---

## Files to create next (Phase 0 concrete next tasks)

In priority order:
1. `.gitignore`
2. `README.md`
3. `LICENSE`
4. `docs/` (empty folder, ready for Phase 1 output)
5. `src/` (empty folder)
6. `tests/` (empty folder)
7. `git init` + first commit + push to GitHub
