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
    debug: bool = typer.Option(
        False,
        "--debug",
        help="Enable verbose output.",
    ),
) -> None:
    """Search for flights across multiple sites."""
    asyncio.run(_search_async(query, top, debug))


async def _search_async(query: str, top: int, debug: bool) -> None:
    from playwright.async_api import async_playwright

    from flight_finder.config import load_config, load_secrets
    from flight_finder.executors.google_flights import GoogleFlightsAdapter
    from flight_finder.executors.kayak import KayakAdapter
    from flight_finder.llm.anthropic_client import AnthropicClient
    from flight_finder.orchestrator.orchestrator import Orchestrator
    from flight_finder.planner.planner import Planner, PlannerError

    cfg = load_config()
    secrets = load_secrets()

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
        adapters=[GoogleFlightsAdapter(), KayakAdapter()],
        planner=planner,
        config=cfg.orchestrator,
    )

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not debug)
        try:
            result = await orchestrator.run(query=query, browser=browser)
        except PlannerError as exc:
            typer.echo(f"Planner error: {exc}", err=True)
            raise typer.Exit(code=1)
        finally:
            await browser.close()

    if not result.flights:
        notes = ""
        # Surface planner clarification notes if available via audit
        typer.echo("No flights found.")
        if debug:
            for rec in result.audit:
                status = "ok" if rec.success else f"FAIL: {rec.error}"
                typer.echo(f"  [{rec.adapter}] {status} ({rec.duration_ms:.0f}ms)", err=True)
        raise typer.Exit(code=1)

    typer.echo(
        f"\nFound {len(result.flights)} result(s). "
        f"Showing top {min(top, len(result.flights))}:\n"
    )
    for i, flight in enumerate(result.flights[:top], 1):
        seg = flight.segments[0]
        total_s = int(flight.total_duration.total_seconds())
        h, m = divmod(total_s // 60, 60)
        stops_label = "Nonstop" if flight.stops == 0 else f"{flight.stops} stop(s)"
        typer.echo(
            f"{i:2}. {seg.airline:<30} "
            f"${flight.price:>8}  "
            f"{h}h{m:02d}m  "
            f"{stops_label}"
        )


if __name__ == "__main__":
    app()
