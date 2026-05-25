# Phase 2 — Architecture Comparison

Scoring the three candidates that emerged from `docs/01_research_notes.md` against the rubric defined in `TODO.md`.

**Selected architecture:** **Arch 1 — Planner–Executor + Playwright** (chosen May 2026).

Phase 3 (Detailed Design) will expand this architecture into a full implementation-ready design. Stagehand and browser-use are out of scope for the primary path but may resurface as future enhancements if/when target sites become harder to scrape deterministically.

---

## Scoring rubric (recap)

| Criterion | Weight | Direction |
|---|---|---|
| A. Free / open-source fit (incl. ongoing LLM cost) | 25% | higher = freer |
| B. Robustness & reliability of flight search | 20% | higher = more reliable end-to-end |
| C. Implementation complexity with Claude Code | 20% | higher = simpler to build |
| D. Maintainability & extensibility | 15% | higher = easier to keep alive |
| E. Ethical / legal alignment (ToS, robots.txt, request volume) | 10% | higher = better citizen |
| F. Scalability potential | 10% | higher = scales further |

Each architecture is scored 1–5 per criterion. Total = Σ(score × weight), max 5.0.

Scoring is informed judgment grounded in Phase 1 research, not measured data — values can be re-weighted or re-scored if you disagree.

---

## Feature comparison table

| | **Arch 1: Planner–Executor + Playwright** | **Arch 2: Multi-agent + browser-use** | **Arch 3: Hybrid Playwright + Stagehand** |
|---|---|---|---|
| **High-level description** | LLM planner decomposes the user query into per-site search steps; deterministic Playwright modules execute each step. | A CrewAI/LangGraph orchestrator delegates to specialized role-based agents (Intent, Search-per-site, Normalizer, Ranker); each site-search agent uses browser-use to drive the browser via LLM reasoning. | Stagehand wraps Playwright; flows run deterministically when cached, LLM is invoked only when the page changes. A lightweight planner sequences sites and re-plans on failure. |
| **# Agents / Roles** | 1 LLM planner + N deterministic site executors + 1 normalizer + 1 ranker. **~1 LLM agent.** | 1 orchestrator + 1 intent + N site-search agents (each LLM-driven) + normalizer + ranker. **~3–5 LLM agents.** | 1 planner + N Stagehand-wrapped site executors (LLM-aware but mostly cached) + 1 normalizer + 1 ranker. **~1–2 LLM agents in steady state.** |
| **Tooling stack** | Python, Playwright (Apache 2.0), LangGraph or a small custom loop, pydantic, pytest. | Python, browser-use (MIT), CrewAI or LangGraph (MIT/Apache), pydantic, pytest. | Python, Playwright (Apache 2.0), Stagehand-python (MIT, beta), LangGraph or a small custom loop, pydantic, pytest. |
| **Pros** | Cheapest per task. Lowest LLM dependency. Easiest to reason about, test, and debug. Plays well with Claude Code's iterate-and-refactor loop. | Most resilient to UI changes. Adding a new site is mostly a prompt change. Cleanly maps to a multi-agent decomposition the spec already describes. | Best practical reliability over a 6-month horizon (deterministic when stable, AI when changing). Auto-caching keeps steady-state cost near zero. Single mental model for site executors. |
| **Cons** | Per-site selectors break on redesign; each break is a code edit. Less resilient to anti-bot challenges that require contextual interaction. | $0.01–0.05 LLM cost per task plus 30–60s latency. Higher request volume per search → more anti-bot exposure. Multi-agent orchestration is more boilerplate to manage. | Stagehand Python SDK is younger than the TS one — feature-parity risk. Hybrid surface area is larger (you maintain both Playwright primitives and Stagehand prompts). |
| **Est. implementation effort** | **Low** (1–2 weeks to first working end-to-end search across 2 sites) | **Medium–High** (3–4 weeks; multi-agent boilerplate + per-site prompt engineering) | **Medium** (2–3 weeks; Stagehand learning curve, then incremental) |
| **Scalability potential** | High — fast (~5 s/task), trivially parallelizable, near-zero per-task cost. | Low–Medium — slow, expensive, anti-bot-exposed. Parallelism amplifies LLM bill. | High — Playwright-fast in steady state, LLM bursts are rare. |

---

## Weighted scoring matrix

| Criterion (weight) | Arch 1 score | Arch 1 weighted | Arch 2 score | Arch 2 weighted | Arch 3 score | Arch 3 weighted |
|---|---|---|---|---|---|---|
| A. Free / OSS fit (25%) | 5 | 1.25 | 2 | 0.50 | 4 | 1.00 |
| B. Robustness (20%) | 3 | 0.60 | 4 | 0.80 | 5 | 1.00 |
| C. Implementation complexity (20%) | 5 | 1.00 | 3 | 0.60 | 4 | 0.80 |
| D. Maintainability (15%) | 3 | 0.45 | 5 | 0.75 | 5 | 0.75 |
| E. Ethical / legal (10%) | 4 | 0.40 | 2 | 0.20 | 3 | 0.30 |
| F. Scalability (10%) | 4 | 0.40 | 2 | 0.20 | 4 | 0.40 |
| **Total** | | **4.10** | | **3.05** | | **4.25** |

### Reasoning for the closer scores

- **A (Free/OSS fit).** Arch 1 scores top because the planner is the only LLM call; Arch 3 loses a point because Stagehand's self-healing occasionally re-invokes the LLM; Arch 2 loses heavily because every browser action is an LLM call.
- **B (Robustness).** Arch 1 is near-100% on stable pages but brittle to redesigns. Arch 2 is ~70–85% per attempt but adapts to changes. Arch 3 is best-of-both: deterministic when possible, AI-assisted when needed.
- **C (Implementation complexity).** Arch 1 is the simplest mental model. Arch 3 adds Stagehand's four primitives — a real but manageable learning curve. Arch 2 needs multi-agent orchestration *plus* per-agent prompt engineering.
- **D (Maintainability).** Both LLM-aware approaches (2 and 3) win here: they survive UI redesigns. Arch 1 takes a maintenance hit every time a target site changes.
- **E (Ethical / legal).** Per-task request volume drives this. Deterministic flows (Arch 1) generate the fewest extra requests. LLM-driven exploration (Arch 2) generates the most.

---

## Per-architecture summary

### Arch 1: Planner–Executor + Playwright

The simplest credible design. A single LLM planner reads the user's request, decomposes it into per-site search steps, and dispatches each step to a deterministic Playwright module. After execution, results are normalized into a common `FlightResult` shape and ranked. The architecture is cheap, fast, and easy to test — but every time a target site redesigns its UI, the per-site module breaks and needs a code fix. Best fit if you want the lowest LLM bill and don't mind the occasional selector-rewrite weekend.

### Arch 2: Multi-agent role-based + browser-use

A textbook agentic decomposition: an orchestrator delegates to an Intent agent, then one LLM-driven Search agent per site, then a Normalizer and Ranker. Each Search agent uses browser-use, so the LLM literally drives the browser — read the page, decide what to click, type, scroll, repeat. Most resilient to UI changes (the LLM figures out new layouts) and most ergonomic to extend (adding a new site is mostly a prompt). The downside is real: every search consumes meaningful LLM tokens (typical 30–60 s and $0.01–0.05 per task per executor) and the higher request volume increases anti-bot exposure.

### Arch 3: Hybrid Playwright + Stagehand under a planner (recommended)

Stagehand sits on top of Playwright and exposes four primitives (`act`, `extract`, `observe`, `agent`). It auto-caches successful flows and only invokes the LLM when the page actually changes from the cached path. A small planner sequences sites and re-plans on failure. In steady state this behaves like Arch 1 (cheap, fast, deterministic); when a target site changes, it behaves like Arch 2 (self-healing). The trade-off is a slightly larger surface area (you maintain Playwright primitives *and* Stagehand prompts) and dependence on the Stagehand Python SDK, which is younger than its TS sibling.

---

## Recommendation

**Architecture 3 — Hybrid Playwright + Stagehand under a planner.**

Reasoning, briefly:

- It tops the weighted score (4.25), albeit by a narrow margin over Arch 1 (4.10).
- The criterion where it leads decisively is **Robustness (5/5)** — the one that most determines whether the project still works in six months without your weekend attention. For a hobby-scale project run by a single developer, surviving UI change is more valuable than shaving a second off per-task latency.
- The criterion where it lags Arch 1 is **Free/OSS fit (4 vs 5)** — and that gap exists only because Stagehand will occasionally re-invoke the LLM when a cached flow breaks. In steady state, the per-task cost is comparable to Arch 1.
- The implementation effort gap vs Arch 1 (~1 extra week) is small; the Stagehand learning curve pays itself back the first time a target site redesigns.

### When to override the recommendation

- **Pick Arch 1** if you want the absolute minimum LLM dependency, prefer maximum code-level control, or if the Stagehand Python SDK turns out to have blocking gaps when you go to implement.
- **Pick Arch 2** if you want to lean fully into agentic patterns for learning purposes and accept the per-task LLM cost as a feature, not a bug. (Strong educational choice; weak production choice.)
- **Request a hybrid** if you want, for example, Arch 1 for the two main sites (where you control the selectors) plus Arch 2 as a one-off "exotic site" fallback that's only triggered when the deterministic scrapers return nothing.

---

## CHECKPOINT — Your choice

**Which architecture would you like to use (1, 2, or 3)? You may also request a hybrid.**

I'll record your choice at the top of this file and proceed to Phase 3 (Detailed Design) only after you've answered.
