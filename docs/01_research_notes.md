# Phase 1 — Architecture Research Notes

Survey of AI agent architectures, free/open-source browser-automation stacks, and the scraping posture of major travel sites. Inputs for Phase 2 (architecture selection).

Research conducted: May 2026. Sources cited inline; full list at the bottom.

---

## 1. Executive summary

- The agent-architecture space has consolidated around five reusable patterns; for a browser-driven flight finder the **planner–executor** and **multi-agent (role-based)** patterns are the most relevant, with **tool-calling** as the underlying execution primitive.
- For browser automation there is a clear three-way trade-off: **deterministic scripts** (Playwright) are fast and cheap but break on UI change; **LLM-driven browser agents** (browser-use, Skyvern) survive UI change but are 6–12× slower and incur per-task LLM cost; **hybrid frameworks** (Stagehand) split the work and are emerging as the 2026 default.
- **No major flight site has a clean, free-tier API for an individual developer.** Kiwi.com's Tequila API is the closest, but practical free access now requires a project with ≥50k MAU. ToS at Google Flights, Kayak, Skyscanner, and most airline sites restrict scraping; robots.txt and active anti-bot measures must be checked per-site at implementation time.
- Practical implication for Phase 2: the chosen architecture will almost certainly be browser-automation-first, target 1–3 of the *least restrictive* sites, and rate-limit aggressively. A small free-tier API may be added as a sanity-check source.

---

## 2. Agent architecture patterns

Five patterns are most often cited in 2025–2026 surveys. Each is summarized with a short definition, fit for browser-driven flight search, and source.

### 2.1 Single-agent / ReAct loop

**Definition.** One LLM in a Reasoning-then-Acting loop: think, call a tool, observe, repeat until done. Originated as the ReAct framework from Google Research. Tool output is parsed from free-form strings.

**Fit.** Lowest implementation overhead. Works well when the task is well-bounded and few tools are needed. Weak for long horizons (it re-reasons after every step, which is slow and expensive when many sub-tasks are involved).

**Source.** [ReAct agents vs function calling agents — LeewayHertz](https://www.leewayhertz.com/react-agents-vs-function-calling-agents/), [From Basic Tool Calling to Advanced ReAct Agents — TheDataGuy](https://thedataguy.pro/blog/2025/08/llm-tool-calling-to-react-agent/).

### 2.2 Tool-calling / function-calling agent

**Definition.** Same loop shape as ReAct, but the LLM emits structured JSON tool calls (OpenAI/Anthropic function calling, native to most providers since 2023). Faster, cheaper, and less brittle than ReAct's string parsing; can request multiple tool calls per turn.

**Fit.** The de-facto execution primitive in 2026 — most "agents" today are tool-calling agents underneath. Strong default for any node in a larger architecture (e.g., the executors in a planner–executor design).

**Source.** [Vibe Engineering: LangChain's Tool-Calling Agent vs. ReAct Agent — Medium](https://medium.com/@dzianisv/vibe-engineering-langchains-tool-calling-agent-vs-react-agent-and-modern-llm-agent-architectures-bdd480347692), [Building AI Agents from Scratch — DEV](https://dev.to/pockit_tools/building-ai-agents-from-scratch-a-deep-dive-into-function-calling-tool-use-and-agentic-patterns-382g).

### 2.3 Planner–executor (and PEV variants)

**Definition.** A planner LLM produces a multi-step plan up front; one or more executors carry out individual steps with tool calls; a re-planning loop runs after execution. Variants add a Verifier or Critic between planner and executor (Plan–Execute–Verify, Plan–Critic–Execute).

**Fit.** Strong fit for flight search: the user query naturally decomposes into (a) parse intent, (b) for each candidate site, run a search, (c) normalize, (d) rank. The planner can fan out site-specific search steps in parallel, and the verifier guards against bad scrapes. LangGraph has first-class support for this pattern.

**Source.** [Plan-and-Execute Agents — LangChain](https://www.langchain.com/blog/planning-agents), [Build Dynamic Plan-and-Execute Agents with LangGraph — Medium](https://medium.com/@ujjwal-basnet-ml/build-dynamic-plan-and-execute-agents-with-langgraph-1b4dfee9d08c), [Plan-Execute-Validate template — DEV](https://dev.to/manjunathgovindaraju/building-a-reliable-langgraph-workflow-plan-execute-validate-pev-automated-retries-and-mcp-1pik), [Planner-Executor Agentic Framework — emergentmind](https://www.emergentmind.com/topics/planner-executor-agentic-framework).

### 2.4 Multi-agent (role-based) orchestration

**Definition.** Several specialized agents (each with a role, goal, and tools) coordinated by an orchestrator. Two dominant frameworks in 2026: **CrewAI** (role/goal/backstory DSL, low boilerplate) and **AutoGen v1.0** (conversational GroupChat with a selector). **LangGraph** is positioned as the production-grade orchestrator with state, persistence, and human-in-the-loop.

**Fit.** Maps cleanly onto a flight-finder decomposition: `IntentAgent` → `SearchAgent` (one per site, or one parameterized) → `NormalizerAgent` → `RankerAgent`. Setup cost is higher than a single-agent loop but each component is independently testable. CrewAI is the lowest-friction starting point for a solo developer; LangGraph is the better target if production observability matters.

**Source.** [AI Agent Frameworks Compared: LangGraph vs CrewAI vs AutoGen (2026) — pecollective](https://pecollective.com/blog/ai-agent-frameworks-compared/), [CrewAI vs AutoGen 2026: Honest Comparison — cordum](https://cordum.io/blog/crewai-vs-autogen-2026), [How I Built a Multi-Agent AI Travel Planner — Medium](https://medium.com/@arpandas65/how-i-built-a-multi-agent-ai-travel-planner-and-what-claudes-architecture-certification-taught-me-438e7692df03), [Agentic AI: Multi-Agent Travel Planner with Gemini + CrewAI — Google Cloud / Medium](https://medium.com/google-cloud/agentic-ai-building-a-multi-agent-ai-travel-planner-using-gemini-llm-crew-ai-6d2e93f72008).

### 2.5 RAG-augmented agent

**Definition.** An agent whose tool calls include retrieval from a vector store / SQL DB / keyword index. Useful when the agent needs grounded knowledge that isn't in the prompt.

**Fit.** Of limited use for the *search* path itself (live flight prices change too quickly for retrieval to add value), but useful adjacent to it: airport-code lookup, airline-alliance facts, visa/seasonality context, historical fare patterns, user preferences. Worth keeping as a small auxiliary tool, not the spine of the architecture.

**Source.** [Applying RAG Architectures to Travel Knowledge Bases — DEV](https://dev.to/airtruffle/applying-rag-architectures-to-travel-knowledge-bases-a-practitioners-view-27fh), [What is Agentic RAG? — IBM](https://www.ibm.com/think/topics/agentic-rag), [TP-RAG benchmark — arXiv 2504.08694](https://arxiv.org/pdf/2504.08694).

### 2.6 Browser-using agent (cross-cutting capability)

Not a separate architecture so much as a *tool* that fits inside any of the above. A browser-using agent gives the LLM a browser via primitives like `navigate`, `click`, `type`, `extract`, `observe`. Implementations: browser-use, Skyvern, Stagehand, Anthropic Computer Use, OpenAI Operator. See §3 for stack-by-stack notes.

**Source.** [Skyvern blog — Automate Travel Booking with Browser Agents 2026](https://www.skyvern.com/blog/automate-travel-booking-browser-agents/), [11 Best AI Browser Agents in 2026 — Firecrawl](https://www.firecrawl.dev/blog/best-browser-agents).

---

## 3. Browser-automation stacks

Free / open-source options ranked by relevance to this project. All work with Python.

### 3.1 Playwright

- **License.** Apache 2.0.
- **Model.** Deterministic, code-driven. CSS / XPath / role selectors.
- **Speed / cost.** ~5 s/task, no LLM cost.
- **Reliability.** Near-100% on known pages; **breaks on UI change**; requires selector maintenance.
- **Use as.** The low-level driver underneath an LLM-aware layer, or for the predictable 80% of steps in a hybrid design.
- **Source.** [Browser Tools for AI Agents Part 1: Playwright, Puppeteer — DEV](https://dev.to/stevengonsalvez/browser-tools-for-ai-agents-part-1-playwright-puppeteer-and-why-your-agent-picked-playwright-k71).

### 3.2 browser-use (`browser-use/browser-use`)

- **License.** MIT.
- **Stars.** ~79k (May 2026), one of the fastest-growing OSS AI projects.
- **Model.** Python library that turns any LLM into a full browser-control agent (the LLM decides what to click/type/scroll).
- **Speed / cost.** ~30–60 s/task, $0.01–0.05/task in LLM API calls.
- **Reliability.** 70–85% on novel tasks but resilient to UI change.
- **Use as.** The primary executor for site-specific search agents, or as a fallback when deterministic scripts break.
- **Source.** [browser-use GitHub](https://github.com/browser-use/browser-use), [browser-use Open Source intro](https://docs.browser-use.com/open-source/introduction), [Stagehand vs Browser Use vs Playwright (2026) — NxCode](https://www.nxcode.io/resources/news/stagehand-vs-browser-use-vs-playwright-ai-browser-automation-2026), [browser-use vs Playwright for scraping — CodeCut](https://codecut.ai/browser-use-ai-browser-agent/).

### 3.3 Stagehand (`browserbase/stagehand`)

- **License.** MIT. (TypeScript-first; Python port available at `browserbase/stagehand-python`.)
- **Model.** Built on Playwright. Exposes four primitives: `act`, `extract`, `observe`, `agent`. Auto-caches successful flows and re-runs them without LLM inference; falls back to AI only when the page changes.
- **Use as.** The strongest hybrid candidate — you keep Playwright's speed for known flows and only pay for LLM cycles when the UI changes.
- **Caveat.** Python SDK is newer than the TS one; check feature parity before committing.
- **Source.** [Stagehand GitHub](https://github.com/browserbase/stagehand), [Stagehand Python](https://github.com/browserbase/stagehand-python), [stagehand.dev](https://www.stagehand.dev/), [Browser Automation AI Agents: Playwright vs Stagehand — DigitalApplied](https://www.digitalapplied.com/blog/browser-automation-ai-agents-playwright-stagehand-2026).

### 3.4 Skyvern (`Skyvern-AI/skyvern`)

- **License.** **AGPL-3.0** — usable for a self-hosted personal project, but viral copyleft if ever redistributed as a network service. Worth flagging.
- **Model.** Computer-vision + LLMs reading pages by *meaning* rather than DOM structure. State-of-the-art on the WebVoyager eval (85.85%).
- **Use as.** Most resilient option for booking-style flows across heterogeneous airline portals. The licensing posture (AGPL) is the main reason to prefer browser-use or Stagehand unless you specifically need Skyvern's robustness.
- **Source.** [Skyvern GitHub](https://github.com/Skyvern-AI/skyvern), [Skyvern 2.0 SoTA blog](https://www.skyvern.com/blog/skyvern-2-0-state-of-the-art-web-navigation-with-85-8-on-webvoyager-eval/), [Automate Travel Booking with Browser Agents 2026](https://www.skyvern.com/blog/automate-travel-booking-browser-agents/).

### 3.5 Selenium / Puppeteer

Mature, well-known. Both viable as the underlying driver, but in 2026 Playwright has clearly won as the default for new Python projects (Selenium remains common in QA; Puppeteer is JS-first). No reason to choose them over Playwright here.

### 3.6 Bright Data scraping browser

Listed in the project spec as a free-tier option. Free trial credits exist but the *steady-state* tier is paid; the free credits are not sufficient for sustained operation. Useful as a fallback for anti-bot-heavy sites if/when needed, **not** as a primary tool given the "free" constraint.

---

## 4. Travel sites: scraping viability audit

Per-site posture as of May 2026. Sources cited inline; **robots.txt and ToS must be re-verified at implementation time on the host** (these files change without notice).

| Site | Has free API? | ToS posture on scraping | Anti-bot intensity | Practical viability |
|---|---|---|---|---|
| Google Flights | No (deprecated) | Restrictive; ToS may be violated by aggressive scraping. Public data, but no explicit allowance. | High (rate limiting, CAPTCHA) | Risky. Light, rate-limited use possible; production-scale scraping not viable. |
| Kayak | No | Restrictive; ToS should be checked. | Medium–high | Risky; many guides describe scraping but acknowledge it's against ToS. |
| Skyscanner | Partner API only (gated) | ToS generally **prohibits** scraping. | Medium | Avoid for primary scraping. Has a partner / affiliate program — worth checking access. |
| Momondo | No public API | Restrictive (sister of Kayak, owned by Booking Holdings). | Medium | Similar posture to Kayak. |
| ITA Matrix (matrix.itasoftware.com) | No | Google actively discourages scraping; barriers in place. | High | Avoid. |
| Kiwi.com (Tequila API) | **Yes, in name** | Tequila API has a free tier but practical access in 2026 requires ≥50k MAU project commitment. | N/A for API path | API path: gated. Site scraping: similar restrictions to others. |
| Direct airline sites (united.com, lufthansa.com, etc.) | Most have B2B APIs, not consumer | Many have **hard bans** on automated access in ToS. | Variable; often high. | Avoid unless an airline has an explicit developer program. |
| Smaller meta-search sites (Skiplagged, Flyiin, etc.) | Mixed | Lighter ToS in some cases; smaller audiences. | Lower | Worth investigating in Phase 2 if more permissive. |

**Sources.** [Google Flights scraping legality — Octoparse](https://www.octoparse.com/blog/how-to-scrape-google-flights-data), [Scraping Google Flights — Proxyway](https://proxyway.com/guides/scrape-google-flights), [Flight Scraper Guide — RapidSeedbox](https://www.rapidseedbox.com/blog/flight-scraper-guide), [Kayak scraping guide — PromptCloud](https://www.promptcloud.com/blog/scrape-kayak-flight-data/), [Is web scraping airline sites illegal — Quora](https://www.quora.com/Is-it-illegal-to-web-scrape-airline-ticket-websites-Expedia-Skyscanner-etc), [Is Web Scraping Legal — Zembra](https://zembratech.com/is-web-scraping-legal/), [ITA Matrix scrape thread — FlyerTalk](https://www.flyertalk.com/forum/travel-tools/1943861-ita-software-scrape.html), [Google Flights API alternative — FlightAPI.io](https://www.flightapi.io/blog/google-flight-api-history-and-alternative/), [Top 5 Flight APIs in 2026 — ScrapingBee](https://www.scrapingbee.com/blog/top-flights-apis-for-travel-apps/), [10 Best Flight APIs with Free Tiers 2026 — Thunderbit](https://thunderbit.com/blog/best-flight-api-with-free-tiers), [Lesser-known flight search engines — Mighty Travels](https://www.mightytravels.com/2024/05/7-lesser-known-flight-search-engines-that-could-save-you-money/), [Matrix airfare alternatives — AlternativeTo](https://alternativeto.net/software/matrix-airfare-search-/).

### Universal rules to encode in the design

- Always read `robots.txt` for the target host *before* every scrape session, in code.
- Respect `Crawl-delay` and disallow rules even when not legally binding — it's the only credible "good-faith" defense.
- Cap requests per minute and per day; add jitter; back off on 429/503.
- Set an honest, identifiable `User-Agent` and a contact `From:` header.
- Cache aggressively; never re-scrape a (origin, destination, date) tuple already seen within an hour.

---

## 5. The free-vs-reliable tension

The project spec forbids paid APIs and asks for browser-automation-based search. Honest assessment from this research:

- **Truly free, reliable, and ToS-clean is a pick-two.** The most ToS-clean path (a flight-data API with a personal free tier) doesn't exist in a useful form for an individual developer in 2026. The most reliable path (Playwright on a stable selector) breaks every time a site redesigns. The most resilient path (LLM-driven browser agents) costs $0.01–0.05 per task in LLM calls.
- **A realistic free-ish design** for a single developer is:
  - Hybrid Playwright + LLM-fallback (Stagehand pattern).
  - Target 2 sites with the lightest anti-bot posture and acceptable ToS posture.
  - Aggressive caching + rate limiting.
  - LLM API budget acknowledged as the one non-zero cost (the spec forbids paid flight-data APIs but allows free-tier services; per-task LLM calls fall in a grey zone — flag explicitly to the user in Phase 2).
- **GitHub Models or local LLMs** could close the LLM-cost gap. Worth surveying in Phase 2 if the per-task LLM cost is unacceptable.

---

## 6. Provisional shortlist for Phase 2

Three architectures emerge as the strongest candidates to compare formally in Phase 2:

1. **Planner–Executor with Playwright executors** (single-LLM planner, deterministic site-specific scrapers).
2. **Multi-agent (role-based) with browser-use executors** (CrewAI or LangGraph orchestrator, one LLM-driven browser agent per site).
3. **Hybrid Playwright + Stagehand under a planner** (Playwright for the predictable 80%, Stagehand for the dynamic 20%; planner decides which lane each step takes).

Phase 2 will score these against the rubric in `TODO.md` and present the comparison table.

---

## Sources (consolidated)

- [AI travel planners are reshaping trips in 2026 — The Traveler](https://www.thetraveler.org/ai-travel-planners-are-reshaping-trips-in-2026/)
- [March 2026: The Month Agentic Travel Gets Real — OAG](https://www.oag.com/blog/march-2026-the-month-agentic-travel-gets-real)
- [How I Built a Multi-Agent AI Travel Planner — Arpan, Medium](https://medium.com/@arpandas65/how-i-built-a-multi-agent-ai-travel-planner-and-what-claudes-architecture-certification-taught-me-438e7692df03)
- [Agentic AI: Multi-Agent Travel Planner with Gemini + CrewAI — Google Cloud, Medium](https://medium.com/google-cloud/agentic-ai-building-a-multi-agent-ai-travel-planner-using-gemini-llm-crew-ai-6d2e93f72008)
- [Stagehand vs Browser Use vs Playwright (2026) — NxCode](https://www.nxcode.io/resources/news/stagehand-vs-browser-use-vs-playwright-ai-browser-automation-2026)
- [Browser Use vs Playwright (2026) — Respan](https://www.respan.ai/market-map/compare/browser-use-vs-playwright)
- [Browser Use vs Playwright — TheNeuralBase](https://theneuralbase.com/browser-use/qna/browser-use-vs-playwright-comparison/)
- [Browser Tools for AI Agents Part 1: Playwright, Puppeteer — DEV](https://dev.to/stevengonsalvez/browser-tools-for-ai-agents-part-1-playwright-puppeteer-and-why-your-agent-picked-playwright-k71)
- [browser-use vs Playwright for scraping — CodeCut](https://codecut.ai/browser-use-ai-browser-agent/)
- [Browser Automation in Claude Code: 5 Tools Compared (2026) — heyuan110](https://www.heyuan110.com/posts/ai/2026-01-28-claude-code-browser-automation/)
- [Browser Automation AI Agents: Playwright vs Stagehand — DigitalApplied](https://www.digitalapplied.com/blog/browser-automation-ai-agents-playwright-stagehand-2026)
- [11 Best AI Browser Agents in 2026 — Firecrawl](https://www.firecrawl.dev/blog/best-browser-agents)
- [Plan-and-Execute Agents — LangChain](https://www.langchain.com/blog/planning-agents)
- [Build Dynamic Plan-and-Execute Agents with LangGraph — Medium](https://medium.com/@ujjwal-basnet-ml/build-dynamic-plan-and-execute-agents-with-langgraph-1b4dfee9d08c)
- [Building a Reliable LangGraph Workflow: Plan-Execute-Validate (PEV) — DEV](https://dev.to/manjunathgovindaraju/building-a-reliable-langgraph-workflow-plan-execute-validate-pev-automated-retries-and-mcp-1pik)
- [Planner-Executor Agentic Framework — emergentmind](https://www.emergentmind.com/topics/planner-executor-agentic-framework)
- [What is Agentic AI Planning Pattern? — Analytics Vidhya](https://www.analyticsvidhya.com/blog/2024/11/agentic-ai-planning-pattern/)
- [Google Flights scraping legality — Octoparse](https://www.octoparse.com/blog/how-to-scrape-google-flights-data)
- [Scraping Google Flights with Python — Proxyway](https://proxyway.com/guides/scrape-google-flights)
- [How to Scrape Google Flights — Scrapeless](https://www.scrapeless.com/en/blog/scrape-google-flights)
- [Flight Scraper Guide — RapidSeedbox](https://www.rapidseedbox.com/blog/flight-scraper-guide)
- [Google Flights API alternative — FlightAPI.io](https://www.flightapi.io/blog/google-flight-api-history-and-alternative/)
- [How to Scrape Google Flights — Oxylabs](https://oxylabs.io/blog/how-to-scrape-google-flights)
- [Skyvern: Automate Travel Booking with Browser Agents 2026](https://www.skyvern.com/blog/automate-travel-booking-browser-agents/)
- [Skyvern 2.0 SoTA evals](https://www.skyvern.com/blog/skyvern-2-0-state-of-the-art-web-navigation-with-85-8-on-webvoyager-eval/)
- [Skyvern GitHub](https://github.com/Skyvern-AI/skyvern)
- [browser-use GitHub](https://github.com/browser-use/browser-use)
- [browser-use Open Source intro](https://docs.browser-use.com/open-source/introduction)
- [Stagehand GitHub](https://github.com/browserbase/stagehand)
- [Stagehand Python](https://github.com/browserbase/stagehand-python)
- [stagehand.dev](https://www.stagehand.dev/)
- [ReAct agents vs function calling agents — LeewayHertz](https://www.leewayhertz.com/react-agents-vs-function-calling-agents/)
- [Vibe Engineering: LangChain Tool-Calling vs ReAct — Medium](https://medium.com/@dzianisv/vibe-engineering-langchains-tool-calling-agent-vs-react-agent-and-modern-llm-agent-architectures-bdd480347692)
- [From Basic Tool Calling to Advanced ReAct Agents — TheDataGuy](https://thedataguy.pro/blog/2025/08/llm-tool-calling-to-react-agent/)
- [Building AI Agents from Scratch — DEV](https://dev.to/pockit_tools/building-ai-agents-from-scratch-a-deep-dive-into-function-calling-tool-use-and-agentic-patterns-382g)
- [AI Agent Frameworks Compared: LangGraph vs CrewAI vs AutoGen (2026) — pecollective](https://pecollective.com/blog/ai-agent-frameworks-compared/)
- [CrewAI vs AutoGen 2026: Honest Comparison — cordum](https://cordum.io/blog/crewai-vs-autogen-2026)
- [10 AI Agent Frameworks You Should Know in 2026 — ATNO, Medium](https://medium.com/@atnoforgenai/10-ai-agent-frameworks-you-should-know-in-2026-langgraph-crewai-autogen-more-2e0be4055556)
- [Applying RAG Architectures to Travel Knowledge Bases — DEV](https://dev.to/airtruffle/applying-rag-architectures-to-travel-knowledge-bases-a-practitioners-view-27fh)
- [What is Agentic RAG? — IBM](https://www.ibm.com/think/topics/agentic-rag)
- [TP-RAG benchmark — arXiv 2504.08694](https://arxiv.org/pdf/2504.08694)
- [Kayak scraping guide — PromptCloud](https://www.promptcloud.com/blog/scrape-kayak-flight-data/)
- [Is web scraping airline sites illegal — Quora](https://www.quora.com/Is-it-illegal-to-web-scrape-airline-ticket-websites-Expedia-Skyscanner-etc)
- [Is Web Scraping Legal — Zembra](https://zembratech.com/is-web-scraping-legal/)
- [ITA Matrix scrape thread — FlyerTalk](https://www.flyertalk.com/forum/travel-tools/1943861-ita-software-scrape.html)
- [Top 5 Flight APIs in 2026 — ScrapingBee](https://www.scrapingbee.com/blog/top-flights-apis-for-travel-apps/)
- [10 Best Flight APIs with Free Tiers 2026 — Thunderbit](https://thunderbit.com/blog/best-flight-api-with-free-tiers)
- [Kiwi Tequila API guide 2026 — phptravels](https://phptravels.com/blog/comprehensive-guide-to-flights-api-integration)
- [Tequila API — Kiwi.com](https://tequila.kiwi.com/)
- [Matrix airfare alternatives — AlternativeTo](https://alternativeto.net/software/matrix-airfare-search-/)
- [Lesser-known flight search engines — Mighty Travels](https://www.mightytravels.com/2024/05/7-lesser-known-flight-search-engines-that-could-save-you-money/)
