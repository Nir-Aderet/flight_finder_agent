"""CLI entry point for the flight-finder agent.

Phase 4, Milestone M1 — skeleton only. The ``search`` command is a stub; it
will be wired to the orchestrator in M4.
"""

from __future__ import annotations

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
        help='Natural-language or structured query, e.g. "SFO to CDG on 2026-06-01".',
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
        help="Enable Playwright traces and screenshots on failure.",
    ),
) -> None:
    """Search for flights. *Stub* — the orchestrator wires up in M4."""
    typer.echo(
        f'search not yet implemented (M4). received: query="{query}", top={top}, debug={debug}'
    )
    raise typer.Exit(code=2)


if __name__ == "__main__":
    app()
