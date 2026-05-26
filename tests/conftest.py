"""Shared pytest fixtures.

Populated as later milestones land (fake adapters in M4, browser fixtures in M3).
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-live",
        action="store_true",
        default=False,
        help="Run live tests that hit real flight sites (skipped by default).",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-live"):
        return
    skip_live = pytest.mark.skip(reason="Live tests require --run-live flag.")
    for item in items:
        if item.get_closest_marker("live"):
            item.add_marker(skip_live)
