"""Layered configuration for flight-finder.

Resolution order (later wins):
  1. Hard-coded defaults (pydantic field defaults below).
  2. Bundled YAML at ``config/flight_finder.yaml`` (shipped with the package).
  3. User YAML at ``~/.flight_finder/config.yaml`` (if present).
  4. Environment variables prefixed ``FLIGHT_FINDER_*``.
  5. CLI flags (applied by ``cli.py`` after loading this config).

Secrets (``ANTHROPIC_API_KEY``) are read from env only — never bundled.

Usage::

    from flight_finder.config import load_config, AppConfig

    cfg = load_config()
    print(cfg.llm.primary_model)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Sub-models (nested sections in flight_finder.yaml)
# ---------------------------------------------------------------------------


class LLMConfig(BaseModel):
    """Settings for the Planner's LLM calls."""

    primary_model: str = "claude-haiku-4-5"
    fallback_model: str = "claude-sonnet-4-6"
    request_timeout_seconds: int = 30


class AdapterEntry(BaseModel):
    """A single entry in the ``adapters.enabled`` list."""

    name: str
    enabled: bool = True


class AdaptersConfig(BaseModel):
    """Adapter registry section."""

    enabled: list[AdapterEntry] = Field(default_factory=list)

    def active_names(self) -> list[str]:
        """Return names of adapters that are enabled."""
        return [a.name for a in self.enabled if a.enabled]


class RankingWeights(BaseModel):
    """Scoring weights; must sum to 1.0 (validated on load)."""

    price: Annotated[float, Field(ge=0.0, le=1.0)] = 0.45
    duration: Annotated[float, Field(ge=0.0, le=1.0)] = 0.25
    stops: Annotated[float, Field(ge=0.0, le=1.0)] = 0.15
    depart_time: Annotated[float, Field(ge=0.0, le=1.0)] = 0.10
    airline: Annotated[float, Field(ge=0.0, le=1.0)] = 0.05

    @field_validator("airline", mode="after")
    @classmethod
    def weights_sum_to_one(cls, airline: float, info: object) -> float:
        # info.data holds the already-validated sibling fields.
        data = getattr(info, "data", {})
        total = (
            data.get("price", 0.0)
            + data.get("duration", 0.0)
            + data.get("stops", 0.0)
            + data.get("depart_time", 0.0)
            + airline
        )
        if abs(total - 1.0) > 0.001:
            raise ValueError(
                f"Ranking weights must sum to 1.0, got {total:.4f}. "
                "Check config/flight_finder.yaml or your override file."
            )
        return airline


class RankingConfig(BaseModel):
    weights: RankingWeights = Field(default_factory=RankingWeights)


class CacheConfig(BaseModel):
    ttl_seconds: int = 3600
    path: str = "~/.flight_finder/cache.db"

    def resolved_path(self) -> Path:
        return Path(self.path).expanduser()


class RateLimitConfig(BaseModel):
    default_per_host_min_interval_seconds: float = 2.0


class OrchestratorConfig(BaseModel):
    per_step_timeout_seconds: int = 90
    total_run_timeout_seconds: int = 300
    max_replan_attempts: int = 2


# ---------------------------------------------------------------------------
# Root config model
# ---------------------------------------------------------------------------


class AppConfig(BaseModel):
    """Root application config, mirroring ``config/flight_finder.yaml``."""

    llm: LLMConfig = Field(default_factory=LLMConfig)
    adapters: AdaptersConfig = Field(default_factory=AdaptersConfig)
    ranking: RankingConfig = Field(default_factory=RankingConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    orchestrator: OrchestratorConfig = Field(default_factory=OrchestratorConfig)


# ---------------------------------------------------------------------------
# Secrets (env-only — never in YAML files)
# ---------------------------------------------------------------------------


class Secrets(BaseSettings):
    """API keys and other secrets sourced exclusively from environment variables.

    Pydantic-settings reads ``ANTHROPIC_API_KEY`` automatically.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_api_key: str = ""
    """Anthropic API key. Required when the Planner is active (M4+)."""

    log_level: str = "INFO"
    """Structlog level. Override with FLIGHT_FINDER_LOG_LEVEL (via env) or LOG_LEVEL."""

    # Allow bare LOG_LEVEL as well as the ANTHROPIC_API_KEY standard name.
    model_config = SettingsConfigDict(
        env_prefix="",          # keys above match env vars exactly
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

_BUNDLED_YAML = Path(__file__).parent.parent.parent / "config" / "flight_finder.yaml"
_USER_YAML = Path("~/.flight_finder/config.yaml").expanduser()


def _load_yaml(path: Path) -> dict:
    """Return parsed YAML dict, or {} if the file does not exist."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base* (override wins on conflicts)."""
    merged = dict(base)
    for key, val in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(val, dict):
            merged[key] = _deep_merge(merged[key], val)
        else:
            merged[key] = val
    return merged


def load_config(user_yaml: Path | None = None) -> AppConfig:
    """Build and return the application config using the layered resolution order.

    Args:
        user_yaml: Override path for the user config file. Defaults to
                   ``~/.flight_finder/config.yaml``.

    Returns:
        A fully validated :class:`AppConfig` instance.
    """
    bundled = _load_yaml(_BUNDLED_YAML)
    user = _load_yaml(user_yaml or _USER_YAML)

    merged = _deep_merge(bundled, user)

    # Environment variable overrides for the most common knobs.
    # Full section overrides are not supported via env vars; use a user YAML for that.
    env_overrides: dict = {}

    def _env(key: str) -> str | None:
        return os.environ.get(f"FLIGHT_FINDER_{key}")

    if (v := _env("PLANNER_MODEL")):
        env_overrides.setdefault("llm", {})["primary_model"] = v
    if (v := _env("PLANNER_FALLBACK_MODEL")):
        env_overrides.setdefault("llm", {})["fallback_model"] = v
    if (v := _env("CACHE_PATH")):
        env_overrides.setdefault("cache", {})["path"] = v
    if (v := _env("CACHE_TTL_SECONDS")):
        env_overrides.setdefault("cache", {})["ttl_seconds"] = int(v)
    if (v := _env("RATE_LIMIT_INTERVAL")):
        env_overrides.setdefault("rate_limit", {})["default_per_host_min_interval_seconds"] = float(v)

    final = _deep_merge(merged, env_overrides)
    return AppConfig.model_validate(final)


def load_secrets() -> Secrets:
    """Load API keys and secrets from environment / .env file."""
    return Secrets()
