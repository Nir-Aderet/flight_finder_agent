"""Convenience loader for RankingWeights. The canonical class lives in config."""
from __future__ import annotations

from flight_finder.config import AppConfig, RankingWeights, load_config

__all__ = ["RankingWeights", "load_weights"]


def load_weights(cfg: AppConfig | None = None) -> RankingWeights:
    if cfg is None:
        cfg = load_config()
    return cfg.ranking.weights
