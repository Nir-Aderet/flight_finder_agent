"""CLI entry point for the flight-finder agent."""

from __future__ import annotations

import asyncio

import typer

from flight_finder import __version__

app = typer.Typer(
    name="ff",
    help=(
        "Find flights across multiple sites using free, open-source browser "
        "automation. Personal-use tool; respect site Terms of Service."
    ),
    no_args_is_help=True,
    add_completion=False,
)


@app.command()
def version() -> None:
    """Print the flight-finder version."""
    typer.echo(f"ff {__version__}")


@app.command()
def search(
    query: str = typer.Argument(
        ...,
        help='Natural-language query, e.g. "SFO to CDG on 2026-06-01".',
    ),
    top: int = typer.Option(
        10,
        "--top",
        "-n",
        min=1,
        max=100,
        help="Number of ranked results to print.",
    ),
    max_stops: int | None = typer.Option(
        None,
        "--max-stops",
        min=0,
        help="Maximum stops (0 = nonstop only).",
    ),
    max_price: float | None = typer.Option(
        None,
        "--max-price",
        help="Maximum price in the search currency.",
    ),
    prefer_airline: list[str] = typer.Option(
        [],
        "--prefer-airline",
        help="Preferred airline name (repeatable).",
    ),
    block_airline: list[str] = typer.Option(
        [],
        "--block-airline",
        help="Blocked airline name (repeatable).",
    ),
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable console logging, Playwright traces, and screenshots on failure.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Print LLM cost ledger and adapter audit after results.",
    ),
) -> None:
    """Search for flights across multiple sites."""
    asyncio.run(_search_async(query, top, max_stops, max_price, prefer_airline, block_airline, debug, verbose))


async def _search_async(
    query: str,
    top: int,
    max_stops: int | None,
    max_price: float | None,
    prefer_airline: list[str],
    block_airline: list[str],
    debug: bool,
    verbose: bool,
) -> None:
    from decimal import Decimal

    from playwright.async_api import async_playwright

    from flight_finder.common.logging import configure_logging
    from flight_finder.config import load_config, load_secrets
    from flight_finder.executors.google_flights import GoogleFlightsAdapter
    from flight_finder.executors.kayak import KayakAdapter
    from flight_finder.executors.wizz_air import WizzAirAdapter
    from flight_finder.llm.anthropic_client import AnthropicClient
    from flight_finder.normalizer.filter import apply_filters
    from flight_finder.orchestrator.orchestrator import Orchestrator
    from flight_finder.planner.planner import Planner, PlannerError
    from flight_finder.ranker.score import score_all

    cfg = load_config()
    secrets = load_secrets()

    configure_logging(
        level="DEBUG" if debug else secrets.log_level,
        json_mode=False,
    )

    if not secrets.anthropic_api_key:
        typer.echo("Error: ANTHROPIC_API_KEY environment variable is not set.", err=True)
        raise typer.Exit(code=1)

    llm = AnthropicClient(
        api_key=secrets.anthropic_api_key,
        default_model=cfg.llm.primary_model,
    )
    planner = Planner(
        llm=llm,
        primary_model=cfg.llm.primary_model,
        fallback_model=cfg.llm.fallback_model,
    )
    orchestrator = Orchestrator(
        adapters=[GoogleFlightsAdapter(), KayakAdapter(), WizzAirAdapter()],
        planner=planner,
        config=cfg.orchestrator,
    )

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not debug)
        try:
            result = await orchestrator.run(query=query, browser=browser, debug=debug)
        except PlannerError as exc:
            typer.echo(f"Planner error: {exc}", err=True)
            raise typer.Exit(code=1)
        finally:
            await browser.close()

    # Apply CLI-flag filters and score/rank results.
    filter_req = result.query
    updates: dict[str, object] = {}
    if max_stops is not None:
        updates["max_stops"] = max_stops
    if max_price is not None:
        updates["max_price"] = Decimal(str(max_price))
    if prefer_airline:
        updates["preferred_airlines"] = list(prefer_airline)
    if block_airline:
        updates["blocked_airlines"] = list(block_airline)
    if updates:
        filter_req = filter_req.model_copy(update=updates)

    flights = score_all(apply_filters(result.flights, filter_req), cfg.ranking.weights, filter_req)

    if not flights:
        typer.echo("No flights found.")
        if debug or verbose:
            for rec in result.audit:
                status = "ok" if rec.success else f"FAIL: {rec.error}"
                typer.echo(f"  [{rec.adapter}] {status} ({rec.duration_ms:.0f}ms)", err=True)
        raise typer.Exit(code=1)

    typer.echo(
        f"\nFound {len(flights)} result(s). "
        f"Showing top {min(top, len(flights))}:\n"
    )
    for i, flight in enumerate(flights[:top], 1):
        seg = flight.segments[0]
        total_s = int(flight.total_duration.total_seconds())
        h, m = divmod(total_s // 60, 60)
        stops_label = "Nonstop" if flight.stops == 0 else f"{flight.stops} stop(s)"
        score_str = f"  score={flight.score:.3f}" if flight.score is not None else ""
        typer.echo(
            f"{i:2}. {seg.airline:<30} "
            f"${flight.price:>8}  "
            f"{h}h{m:02d}m  "
            f"{stops_label}"
            f"{score_str}"
        )

    if verbose:
        typer.echo(f"\nEstimated LLM cost: ${llm.total_cost_usd:.4f} USD")
        typer.echo("Adapter audit:")
        for rec in result.audit:
            status = "ok" if rec.success else f"FAIL: {rec.error}"
            count_str = f"  {rec.result_count} result(s)" if rec.result_count else ""
            typer.echo(f"  [{rec.adapter}] {status}{count_str}  ({rec.duration_ms:.0f}ms)")


if __name__ == "__main__":
    app()
