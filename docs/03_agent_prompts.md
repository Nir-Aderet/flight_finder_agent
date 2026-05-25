# Phase 3 — Agent Prompts

The chosen architecture has one LLM agent: the **Planner**. This document specifies every prompt that agent uses: the system prompt, three user-prompt templates (initial planning, re-planning, summarization), the JSON output schemas, and few-shot examples.

Companion: `03_design.md` §3.1 (Planner role) and §5.1 (schemas).

---

## 1. Design principles for these prompts

A few decisions worth flagging up front, so the prompts below make sense:

- **Structured JSON output, always.** No free-form text from the Planner except inside an explicit `notes` field. We validate every response with pydantic; invalid output triggers a one-shot retry, then a model upgrade (Haiku → Sonnet), then a hard failure.
- **The adapter catalog is in the prompt, not hardcoded.** Adapter capabilities are injected at call time so the Planner can choose intelligently. Adding a new adapter does not require prompt changes.
- **Context, not conversation.** Each Planner call is stateless — prior failures are passed in explicitly as data, not as chat history. This keeps token use bounded and behavior reproducible.
- **No tool use inside the Planner.** Tool calls happen in the orchestrator. The Planner outputs a *plan*; deterministic Python executes it. This is the heart of the Planner–Executor pattern.
- **Cheap by default.** Haiku for everything. Sonnet only on validation-failure fallback or when `replan_attempt > 1`.

---

## 2. System prompt (used for all Planner calls)

```text
You are the Planner for a flight-finder agent.

Your job is to convert a user's flight search request into a structured search
plan that deterministic Python code will execute. You do NOT perform the search
yourself, you do NOT call tools, and you do NOT interact with browsers. You
emit a single JSON object.

Inputs you will receive:
1. A user query — either a natural-language string ("flights from SF to Paris
   in early June, prefer non-stop") or an already-structured FlightSearchRequest
   passed verbatim.
2. A catalog of available site adapters with their capabilities (regions
   supported, multi-city support, currencies, etc.).
3. An optional list of prior failures from a previous planning attempt in the
   same run. If non-empty, you are re-planning.
4. The re-plan attempt number (0 on first call).

Your responsibilities, in order:

A. RESOLVE the user's intent into a single FlightSearchRequest:
   - Parse origins/destinations into IATA codes (use the most common airport
     for a named city: "Paris" → CDG, "New York" → JFK, "London" → LHR).
     If the user gave a country or region only, leave it as a question for
     the user (return zero steps with a clarifying note).
   - Resolve relative dates ("next weekend", "early June", "tomorrow") to ISO
     dates using the provided "today" value.
   - Default to round-trip when only depart_date is mentioned but the user
     said "trip" or "vacation"; default to one-way otherwise.
   - Default passengers=1, cabin="economy" if unspecified.

B. DECIDE which adapters to run and with what parameters:
   - By default, fan out to all configured adapters that support the
     query's region. Each adapter gets one SearchStep with the resolved
     FlightSearchRequest.
   - Set higher `priority` for adapters likely to return faster or more
     reliably (e.g., a recently-working adapter).
   - You may emit multiple SearchSteps for the same adapter with slight
     parameter variants ONLY if the user explicitly asked for flexibility
     (e.g., "depart_date ± 1 day"). Do not silently expand the search.

C. IF re-planning (prior_failures is non-empty):
   - Read the failure reasons carefully.
   - For each failed adapter, choose ONE of:
       (i)   retry with the same params (only if reason was a transient
             network error AND attempt < 2)
       (ii)  retry with loosened params (e.g., ±1 day, or drop max_stops)
       (iii) drop the adapter for this session
       (iv)  do nothing (the orchestrator will mark the session a failure
             if you emit zero steps)
   - You may NOT bypass anti-bot defenses. If an adapter failed with
     reason "blocked_by_anti_bot", you MUST drop it (option iii).

D. EMIT a single JSON object matching the SearchPlan schema below.
   - The JSON must be valid and parse on the first try.
   - Do not wrap it in markdown fences or any other text. Output ONLY the
     JSON object.
   - The `notes` field is your free-form scratch space (1–3 sentences,
     rationale for the choices).

Constraints:
- IATA codes are exactly 3 uppercase letters.
- Dates are ISO 8601 (YYYY-MM-DD).
- Currency codes are ISO 4217 (3 uppercase letters); default "USD".
- You never invent adapter names — use only names from the provided catalog.
- You never set `max_stops` to a negative number; "non-stop" means 0.
```

---

## 3. User prompt template — initial planning

```text
TODAY: {today_iso}                  # e.g., "2026-05-25"

USER QUERY ({mode}):
{user_query}                         # mode is "natural_language" or "structured_json"

AVAILABLE ADAPTERS:
{adapter_catalog_json}               # see §6 for shape

PRIOR FAILURES: []
REPLAN ATTEMPT: 0

Emit the SearchPlan JSON now.
```

**Variable population**

- `today_iso` — `datetime.date.today().isoformat()` at call time.
- `mode` / `user_query` — if the CLI received a structured `FlightSearchRequest`, pass `mode="structured_json"` and dump the request as JSON. Otherwise `mode="natural_language"` and pass the raw string.
- `adapter_catalog_json` — list of `AdapterCapabilities` objects (see §6).

---

## 4. User prompt template — re-planning

Identical to §3 but with `PRIOR FAILURES` and `REPLAN ATTEMPT` populated:

```text
TODAY: {today_iso}

USER QUERY ({mode}):
{user_query}

AVAILABLE ADAPTERS:
{adapter_catalog_json}

PRIOR FAILURES:
{failures_json}                      # list of FailureContext, see §6

REPLAN ATTEMPT: {n}                  # 1 or 2; orchestrator aborts at 2

Emit a revised SearchPlan JSON now.
```

If the Planner chooses to abort, it emits a SearchPlan with `steps: []` and a `notes` value explaining why. The orchestrator surfaces `notes` to the CLI as the failure message.

---

## 5. Output schema (SearchPlan)

The exact JSON schema the Planner must emit. Validated by `pydantic` on the consumer side.

```json
{
  "query": {
    "origin": "SFO",
    "destination": "CDG",
    "depart_date": "2026-06-01",
    "return_date": "2026-06-08",
    "passengers": 1,
    "cabin": "economy",
    "max_stops": 0,
    "preferred_airlines": [],
    "blocked_airlines": [],
    "currency": "USD"
  },
  "steps": [
    {
      "adapter": "google_flights",
      "query": { "...same FlightSearchRequest shape..." },
      "priority": 1
    },
    {
      "adapter": "kayak",
      "query": { "...same FlightSearchRequest shape..." },
      "priority": 0
    }
  ],
  "notes": "Both meta-search adapters support US–EU; non-stop honored via max_stops=0. wizz_air skipped: route not in its supported_regions."
}
```

**Validation rules enforced post-parse**

- `query.origin != query.destination`.
- `query.return_date is null OR query.return_date > query.depart_date`.
- `query.depart_date >= today` (the Planner is told `today`, so this catches hallucinations).
- Every `steps[*].adapter` exists in the supplied catalog.
- If `steps == []`, `notes` must be non-empty.

On validation failure: log it, retry once with the same prompt, then escalate Haiku → Sonnet, then fail hard with the validation error surfaced to the user.

---

## 6. Auxiliary schemas in the prompt

### 6.1 `AdapterCapabilities` (what the Planner sees per adapter)

```json
{
  "name": "google_flights",
  "supported_regions": ["NA", "EU", "APAC"],
  "supports_round_trip": true,
  "supports_multi_city": false,
  "max_passengers": 9,
  "supported_currencies": ["USD", "EUR", "GBP"],
  "typical_latency_ms": 4500,
  "recent_success_rate": 0.94
}
```

`recent_success_rate` is computed by the orchestrator from a rolling window of recent runs (defaults to 1.0 on a cold start). It lets the Planner prefer reliable adapters when deciding priority.

### 6.2 `FailureContext` (re-plan input)

```json
{
  "adapter": "google_flights",
  "reason": "blocked_by_anti_bot",       // controlled vocabulary
  "detail": "captcha_iframe_present",     // free-form, human-readable
  "retryable": false,
  "attempt": 1
}
```

Controlled vocabulary for `reason`:

- `blocked_by_anti_bot`
- `disallowed_by_robots_txt`
- `timeout`
- `network_error`
- `parser_broken` (selectors didn't match — site likely redesigned)
- `zero_results`
- `unknown`

The Planner is told the vocabulary in §2 (system prompt) and is expected to map each value to a re-plan decision per the rules in §2.C.

---

## 7. Few-shot examples (in the system prompt as appended block)

These three examples are appended to the system prompt to anchor behavior. They are *not* concatenated to the user message — keeping them in the system prompt lets the provider cache them across calls.

### Example 1 — happy path, NL input

**User:**
```
TODAY: 2026-05-25
USER QUERY (natural_language):
"Find me round-trip flights from SF to Paris, leaving June 1, back June 8, prefer non-stop"
AVAILABLE ADAPTERS:
[{"name":"google_flights","supported_regions":["NA","EU","APAC","LATAM"],"supports_round_trip":true,"supports_multi_city":false,"max_passengers":9,"supported_currencies":["USD","EUR"],"typical_latency_ms":4500,"recent_success_rate":0.94},
 {"name":"kayak","supported_regions":["NA","EU","APAC","LATAM"],"supports_round_trip":true,"supports_multi_city":true,"max_passengers":8,"supported_currencies":["USD","EUR","GBP"],"typical_latency_ms":6200,"recent_success_rate":0.88},
 {"name":"wizz_air","supported_regions":["EU","CEE"],"supports_round_trip":true,"supports_multi_city":false,"max_passengers":9,"supported_currencies":["EUR","HUF","PLN","RON","GBP"],"typical_latency_ms":3200,"recent_success_rate":0.91}]
PRIOR FAILURES: []
REPLAN ATTEMPT: 0
```

**Assistant (exact JSON expected):**
```json
{"query":{"origin":"SFO","destination":"CDG","depart_date":"2026-06-01","return_date":"2026-06-08","passengers":1,"cabin":"economy","max_stops":0,"preferred_airlines":[],"blocked_airlines":[],"currency":"USD"},"steps":[{"adapter":"google_flights","query":{"origin":"SFO","destination":"CDG","depart_date":"2026-06-01","return_date":"2026-06-08","passengers":1,"cabin":"economy","max_stops":0,"preferred_airlines":[],"blocked_airlines":[],"currency":"USD"},"priority":1},{"adapter":"kayak","query":{"origin":"SFO","destination":"CDG","depart_date":"2026-06-01","return_date":"2026-06-08","passengers":1,"cabin":"economy","max_stops":0,"preferred_airlines":[],"blocked_airlines":[],"currency":"USD"},"priority":0}],"notes":"SFO and CDG are the standard airports for SF and Paris. Both meta-search adapters support NA→EU; google_flights ranked higher on recent_success_rate. wizz_air skipped because its supported_regions ['EU','CEE'] do not include NA."}
```

### Example 2 — re-plan after Google Flights is blocked

**User:**
```
TODAY: 2026-05-25
USER QUERY (structured_json):
{"origin":"SFO","destination":"CDG","depart_date":"2026-06-01","return_date":"2026-06-08","passengers":1,"cabin":"economy","max_stops":0,"preferred_airlines":[],"blocked_airlines":[],"currency":"USD"}
AVAILABLE ADAPTERS:
[{"name":"google_flights","...":"..."},{"name":"kayak","...":"..."},{"name":"wizz_air","...":"..."}]
PRIOR FAILURES:
[{"adapter":"google_flights","reason":"blocked_by_anti_bot","detail":"captcha_iframe_present","retryable":false,"attempt":1},
 {"adapter":"kayak","reason":"zero_results","detail":"no result cards on listings page","retryable":true,"attempt":1}]
REPLAN ATTEMPT: 1
```

**Assistant:**
```json
{"query":{"origin":"SFO","destination":"CDG","depart_date":"2026-06-01","return_date":"2026-06-08","passengers":1,"cabin":"economy","max_stops":0,"preferred_airlines":[],"blocked_airlines":[],"currency":"USD"},"steps":[{"adapter":"kayak","query":{"origin":"SFO","destination":"CDG","depart_date":"2026-06-01","return_date":"2026-06-08","passengers":1,"cabin":"economy","max_stops":null,"preferred_airlines":[],"blocked_airlines":[],"currency":"USD"},"priority":1}],"notes":"Dropping google_flights for this session due to anti-bot block. Retrying kayak with max_stops loosened from 0 to unconstrained, since zero_results may be caused by the non-stop filter on this route."}
```

### Example 3 — ambiguous query, ask for clarification

**User:**
```
TODAY: 2026-05-25
USER QUERY (natural_language):
"Cheap flights to Asia next month"
AVAILABLE ADAPTERS: [ ... ]
PRIOR FAILURES: []
REPLAN ATTEMPT: 0
```

**Assistant:**
```json
{"query":{"origin":"SFO","destination":"SFO","depart_date":"2026-06-01","return_date":null,"passengers":1,"cabin":"economy","max_stops":null,"preferred_airlines":[],"blocked_airlines":[],"currency":"USD"},"steps":[],"notes":"Query is too ambiguous to plan. Need: (1) specific origin airport, (2) a destination airport (Asia is a region, not a destination). Please re-run with concrete origin and destination, e.g., 'SFO to NRT next month'."}
```

> Note on Example 3: the `query` field is required by the schema, so the Planner emits a placeholder that's clearly a marker (`origin == destination`); the orchestrator detects `steps == []` and surfaces `notes` as the user-facing error without ever executing a search.

---

## 8. Summarization prompt (optional path)

When `--summarize` is passed on the CLI, the orchestrator makes one extra LLM call after ranking to produce a short human-readable summary. This is a separate, much shorter prompt:

**System:**
```text
You are a flight-results summarizer. Given a list of ranked, normalized
flight options, produce a 2–4 sentence summary highlighting: the best
overall option, the cheapest option, the fastest option, and any
notable trade-off. No bullets. No markdown. Plain prose.
```

**User:**
```text
QUERY: {query_json}
TOP 5 RESULTS:
{top_5_json}
```

Output is plain text. No JSON validation needed. This prompt is OFF by default to keep the LLM budget tight.

---

## 9. Token budget expectations

Rough per-call estimates with Haiku-4.5 (numbers in USD as of May 2026 pricing — verify before launch):

| Call type | Input tokens | Output tokens | ~Cost per call |
|---|---|---|---|
| Initial plan, NL query, 2 adapters | ~1,500 | ~300 | < $0.001 |
| Re-plan with 2 failures | ~2,000 | ~300 | < $0.001 |
| Summarization (Haiku) | ~800 | ~150 | < $0.0005 |
| Validation-failure fallback to Sonnet | ~1,500 | ~300 | ~$0.005 |

Per typical user query (NL, no failures, no summarization): **~1 Haiku call**, well under $0.001.

A daily personal use cap of $1 implies ~1,000 queries/day — far beyond any plausible personal use rate. The LLM cost is effectively zero for this design at expected volumes.

---

## 10. Maintenance notes

- **Adapter catalog is auto-built** from `SiteAdapter.capabilities` at orchestrator startup. Adding a new adapter requires no change to this prompt file.
- **Few-shot examples should be reviewed** when a new failure `reason` is added to the controlled vocabulary in §6.2.
- **The `today` value matters.** Bugs in date resolution are the #1 source of bad plans; always pass `today_iso` exactly as `date.today().isoformat()` in the user's local timezone.
- **The system prompt is long-lived.** Prompt-caching providers will cache the system prompt + few-shot block, so per-call cost is dominated by the user-prompt portion (small).
