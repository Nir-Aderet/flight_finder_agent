"""structlog configuration and LLM cost estimation for flight-finder."""

from __future__ import annotations

import logging

import structlog
from structlog.stdlib import BoundLogger

# ---------------------------------------------------------------------------
# LLM pricing (USD per 1M tokens, as of 2026-05)
# ---------------------------------------------------------------------------

_LLM_PRICES: dict[str, tuple[float, float]] = {
    # model-id: (input_price_per_Mtok, output_price_per_Mtok)
    "claude-haiku-4-5": (0.80, 4.00),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-sonnet-4-6": (3.00, 15.00),
    "claude-sonnet-4-6-20251022": (3.00, 15.00),
    "claude-opus-4-7": (15.00, 75.00),
    "claude-opus-4-7-20251101": (15.00, 75.00),
}
_DEFAULT_PRICE: tuple[float, float] = (3.00, 15.00)


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated cost in USD for a single LLM call."""
    inp, out = _LLM_PRICES.get(model, _DEFAULT_PRICE)
    return (input_tokens * inp + output_tokens * out) / 1_000_000


# ---------------------------------------------------------------------------
# structlog configuration
# ---------------------------------------------------------------------------


def configure_logging(level: str = "INFO", json_mode: bool = False) -> None:
    """Configure structlog. Call once at application startup.

    Args:
        level:     Python logging level name (e.g. "DEBUG", "INFO").
        json_mode: True → JSON renderer (production/piped); False → console renderer.
    """
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer: structlog.types.Processor
    if json_mode:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level.upper())
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


def get_logger(name: str = "flight_finder") -> BoundLogger:
    """Return a structlog bound logger for the given name."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
