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

    # ── Hybrid LLM conflict detector ───────────────────────────────────────
    enable_llm_conflict_candidates: bool = False
    llm_detector_repetitions: int = 3
    llm_detector_temperature: float = 0.0

    # ── Live inventory capture/replay ─────────────────────────────────────
    inventory_mode: Literal["mock", "capture", "replay"] = "mock"
    inventory_dir: str = "fixtures/live_inventory"


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
