from __future__ import annotations

import pytest

from flight_finder.common.logging import configure_logging, estimate_cost_usd


class TestEstimateCostUsd:
    def test_haiku_cost(self) -> None:
        # 1000 * 0.80/1e6 + 100 * 4.00/1e6 = 0.0008 + 0.0004 = 0.0012
        assert estimate_cost_usd("claude-haiku-4-5", 1000, 100) == pytest.approx(0.0012)

    def test_haiku_dated_alias(self) -> None:
        assert estimate_cost_usd("claude-haiku-4-5-20251001", 1000, 100) == pytest.approx(0.0012)

    def test_sonnet_cost(self) -> None:
        # 1000 * 3.00/1e6 + 100 * 15.00/1e6 = 0.003 + 0.0015 = 0.0045
        assert estimate_cost_usd("claude-sonnet-4-6", 1000, 100) == pytest.approx(0.0045)

    def test_unknown_model_uses_default(self) -> None:
        # Default = (3.00, 15.00) — same as Sonnet
        assert estimate_cost_usd("unknown-model-x", 1000, 100) == pytest.approx(0.0045)

    def test_zero_tokens(self) -> None:
        assert estimate_cost_usd("claude-haiku-4-5", 0, 0) == 0.0

    def test_cost_is_additive(self) -> None:
        c1 = estimate_cost_usd("claude-haiku-4-5", 500, 0)
        c2 = estimate_cost_usd("claude-haiku-4-5", 0, 500)
        total = estimate_cost_usd("claude-haiku-4-5", 500, 500)
        assert total == pytest.approx(c1 + c2)


class TestConfigureLogging:
    def test_console_mode_does_not_raise(self) -> None:
        configure_logging(level="WARNING", json_mode=False)

    def test_json_mode_does_not_raise(self) -> None:
        configure_logging(level="INFO", json_mode=True)

    def test_debug_level_does_not_raise(self) -> None:
        configure_logging(level="DEBUG", json_mode=False)
