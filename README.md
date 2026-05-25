# Flight Finder Agent

A multi-agent AI system that searches for flights using only free or open-source tools. The agent relies on browser automation and scraping (Playwright, browser-use, etc.) against public travel sites instead of paid flight APIs, and is designed to be built incrementally with Claude Code by a single developer.

## Status

Early scaffolding. No application code yet — currently in **Phase 0: Project Setup**.

## Project layout

- `flight_finder_system_prompt.txt` — the authoritative spec describing goals, constraints, and the two-phase workflow (architecture selection → detailed design).
- `TODO.md` — phased roadmap with named deliverables and exit checkpoints.
- `docs/` — research notes, architecture comparison, and design documents (populated through Phases 1–3).
- `src/` — application source (populated in Phase 4).
- `tests/` — unit and integration tests (populated in Phase 4).
- `scripts/` — helper scripts.

## Constraints

- No paid flight APIs. Free / open-source tooling only, or services with a free tier.
- Respect target sites' Terms of Service and `robots.txt`.
- Python-first (Playwright + browser-use are the leading candidates).
- Implementable on a typical developer machine or a low-cost cloud VM.

## How to follow along

Start with `flight_finder_system_prompt.txt` for the spec, then `TODO.md` for the current phase and next concrete tasks.

## License

MIT — see `LICENSE`.
