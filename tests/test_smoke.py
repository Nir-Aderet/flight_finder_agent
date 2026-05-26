"""Sanity check for M1: the package imports and exposes a version.

This test exists so ``pytest -q`` reports a non-zero passed count after M1,
proving the scaffold is wired correctly. Real tests start landing in M2.
"""

from __future__ import annotations


def test_package_imports() -> None:
    import flight_finder

    assert hasattr(flight_finder, "__version__")
    assert isinstance(flight_finder.__version__, str)
    assert flight_finder.__version__.count(".") >= 2  # PEP 440-ish


def test_cli_app_constructed() -> None:
    """The typer app is built at import time, so importing must not raise."""
    from flight_finder.cli import app

    assert app.info.name == "ff"
