"""
Runtime feature flags and behaviour settings for Voyager.

Kept separate from `api_config.py` (external API credentials/templates) because
these flags control *how* the system behaves — LLM-augmented conflict detection,
live-inventory capture/replay — rather than *where* it connects.

Values are read from environment variables (or a `.env` file via `load_dotenv`)
with safe defaults that preserve deterministic, rule-based behaviour out of the
box.
"""

from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    """Runtime behaviour settings.

    ``enable_llm_conflict_candidates`` gates the hybrid detector behind a flag.
    When disabled (default), routing uses deterministic conflicts only — the LLM
    never proposes and never spends tokens on candidate generation.
    """

    model_config = SettingsConfigDict(env_prefix="VOYAGER_", extra="ignore")

    # ── Decoding (sampling) ────────────────────────────────────────────────
    # When set, this overrides every agent's LLM temperature regardless of
    # mode (VOYAGER_TEMPERATURE_OVERRIDE). Recommended value for deterministic
    # runs is 0.0.
    temperature_override: float | None = None

    # ── Hybrid LLM conflict detector ───────────────────────────────────────
    enable_llm_conflict_candidates: bool = False
    llm_detector_repetitions: int = 3
    llm_detector_temperature: float = 0.0

    # ── Live inventory capture/replay ─────────────────────────────────────
    inventory_mode: Literal["mock", "capture", "replay"] = "mock"
    inventory_dir: str = "fixtures/live_inventory"


def effective_temperature(default_temperature: float) -> float:
    """Resolve the decoding temperature an agent should use for an LLM call.

    Priority:
      1. ``VOYAGER_TEMPERATURE_OVERRIDE`` if set — forces every agent to that
         value (use 0.0 for deterministic decoding).
      2. 0.0 when ``inventory_mode == "replay"`` — replay must reproduce the
         captured run exactly, so sampling temperature is pinned to zero.
      3. The agent's documented default (capture/mock/live-app behaviour).
    """
    settings = get_settings()
    if settings.temperature_override is not None:
        return settings.temperature_override
    if settings.inventory_mode == "replay":
        return 0.0
    return default_temperature


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the global settings instance (lazily constructed)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Force reload settings from environment (used by tests)."""
    global _settings
    _settings = Settings()
    return _settings


def _env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment flag with a safe default."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}
