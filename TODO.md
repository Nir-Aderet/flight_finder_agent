# Flight Finder Agent — TODO

High-level roadmap. Each phase has a clear deliverable file, an exit checkpoint, and concrete next tasks. Do not start a phase until the previous phase's checkpoint is met.

Source of truth for the workflow: `flight_finder_system_prompt.txt`.

---

## Phase 0 — Project Setup

Goal: a clean, version-controlled repo skeleton ready for design and implementation work.

- [x] Connect project folder (`C:\Users\Nir\Documents\Claude\Projects\flight finder agent`)
- [x] Add system prompt (`flight_finder_system_prompt.txt`)
- [ ] Create folder skeleton: `docs/`, `src/`, `tests/`, `scripts/`
- [ ] Add `.gitignore` (Python defaults + `.venv/`, `.env`, `playwright/.cache/`, `node_modules/`, etc.)
- [ ] Add `README.md` (one paragraph: what this project is, link to `TODO.md` and `flight_finder_system_prompt.txt`)
- [ ] Add `LICENSE` (choose: MIT recommended for a free/open-source project)
- [ ] `git init` and first commit
- [ ] Create GitHub repo and push (details to be provided by user)

**Exit checkpoint:** repo skeleton committed and pushed to GitHub.

---

## Phase 1 — Architecture Research

Goal: a written survey of agent architectures applicable to free, browser-based flight search.

- [ ] Survey existing AI agent architectures relevant to travel / flight search:
  - Single-agent vs multi-agent orchestration
  - Planner–executor designs
  - Tool-calling / toolformer agents
  - RAG-augmented agents
  - Browser-based agents (Playwright-driven, browser-use, computer-use-style)
- [ ] Survey candidate free/open-source browser-automation stacks: Playwright, Selenium, browser-use, Puppeteer, Bright Data free tier (if applicable).
- [ ] Survey scraping-viable travel sites: which permit automated access under ToS / robots.txt, which actively block, which have anti-bot measures worth noting.
- [ ] Capture all findings (with source links) → `docs/01_research_notes.md`.

**Exit checkpoint:** `docs/01_research_notes.md` exists, covers at least five architecture patterns with citations, and lists at least three candidate travel sites with ToS/robots.txt notes.

---

## Phase 2 — Architecture Selection

Goal: a top-3 comparison table, a recommended choice, and your explicit go-ahead.

- [ ] Define a weighted scoring rubric (proposed defaults — adjustable):
  - Free/open-source fit — 25%
  - Robustness & reliability of flight search — 20%
  - Implementation complexity with Claude Code — 20% (lower complexity scores higher)
  - Maintainability & extensibility — 15%
  - Ethical / legal alignment (ToS, robots.txt) — 10%
  - Scalability potential — 10%
- [ ] Score the top candidates from Phase 1 against the rubric.
- [ ] Produce top-3 comparison table + 2–3 sentence summaries → `docs/02_architectures_comparison.md`.
- [ ] **CHECKPOINT — ASK USER:** "Which architecture would you like to use (1, 2, or 3)? You may also request a hybrid."

**Exit checkpoint:** user has chosen an architecture (or specified a hybrid), and the choice is recorded at the top of `docs/02_architectures_comparison.md`.

---

## Phase 3 — Detailed Design

Goal: an implementation-ready design document for the chosen architecture.

- [ ] Produce full design doc → `docs/03_design.md`, structured exactly per Task 4 of the system prompt:
  1. Overview
  2. High-level system architecture (with textual diagram description)
  3. Agent roles and responsibilities (inputs, outputs, decision logic)
  4. Tooling and tech stack
  5. Data flow and interfaces (request/response shapes)
  6. Browser automation & scraping strategy
  7. Ranking, filtering, business logic
  8. Configuration and extensibility
  9. Observability, logging, testing
  10. Security, compliance, ethics
  11. Implementation roadmap
- [ ] Specify core data schemas (`FlightSearchRequest`, `FlightResult`, `SearchPlan`, etc.) as pydantic-style sketches in `docs/03_design.md`.
- [ ] Draft per-agent system prompts → `docs/03_agent_prompts.md`.
- [ ] Propose repo layout (folders, modules, key files) → `docs/03_repo_structure.md`.
- [ ] **CHECKPOINT — USER REVIEW:** confirm design before any code is written.

**Exit checkpoint:** user has approved `docs/03_design.md`, `docs/03_agent_prompts.md`, and `docs/03_repo_structure.md`.

---

## Phase 4 — Implementation

Goal: a working flight finder agent, built in milestones so each step is reviewable.

- [ ] **M1 — Skeleton:** create `src/` layout per `docs/03_repo_structure.md`; `pyproject.toml` (or `requirements.txt`); install Playwright; first `pytest` run green on empty tests.
- [ ] **M2 — Core models:** implement `FlightSearchRequest`, `FlightResult`, and supporting types with unit tests.
- [ ] **M3 — First site scraper (proof of concept):** implement one site end-to-end — navigate, fill form, parse results, normalize into `FlightResult`.
- [ ] **M4 — Orchestrator + minimal agent loop:** wire user query → orchestrator → first scraper → normalized results.
- [ ] **M5 — Second scraper (validate extensibility):** add a second site to prove the abstraction holds.
- [ ] **M6 — Ranking & filtering:** implement scoring (price, duration, stops) and user-side filters.
- [ ] **M7 — Observability:** structured logging, retry/backoff, error taxonomy.
- [ ] **M8 — CLI / entry point:** user-facing command (e.g., `python -m flight_finder ...`) with sensible defaults.
- [ ] **M9 — Tests:** unit tests for parsers/normalizers; mocked integration tests for the orchestrator.

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
