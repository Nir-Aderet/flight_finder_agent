"""Allow ``python -m flight_finder`` to invoke the CLI."""

from __future__ import annotations

from flight_finder.cli import app


def main() -> None:
    app()


if __name__ == "__main__":
    main()
