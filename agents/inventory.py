"""
Live-inventory capture and deterministic replay for API-backed agents.

The synthetic mock fixtures are realistic enough for UI development, but they
cannot prove that targeted re-execution behaves the same on real inventory.
This module adds three provider modes per API-backed agent:

    - ``mock``    — current deterministic fixture (default, offline).
    - ``capture`` — call the real API once, write a sanitized response fixture.
    - ``replay``  — read a captured fixture and never touch the network.

Selection-time constraints are deliberately NOT moved into query construction:
a replay consumes the *same broad candidate list* a capture would, and the
agent applies hub constraints during selection — so live and replay inventories
exercise identical agent behaviour.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from config.settings import get_settings

_MANIFEST_NAME = "manifest.json"


def _fixtures_dir() -> Path:
    return Path(get_settings().inventory_dir)


def _sanitize(payload: Any) -> Any:
    """Recursively drop credential/identity-bearing fields from a fixture.

    The sanitizer removes known secret keys and any key hinting at credentials,
    tokens, or PII. Everything else is preserved verbatim so replay is faithful.
    """
    secret_hints = ("key", "secret", "token", "password", "authorization", "api", "email", "phone")
    if isinstance(payload, dict):
        out = {}
        for k, v in payload.items():
            lk = k.lower()
            if any(hint in lk for hint in secret_hints):
                continue
            out[k] = _sanitize(v)
        return out
    if isinstance(payload, list):
        return [_sanitize(v) for v in payload]
    return payload


def fixture_hash(payload: Any) -> str:
    """Stable SHA-256 over the sanitized, canonical fixture."""
    canonical = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _query_key(source: str, **query_params: Any) -> str:
    """Deterministic query id from (source, canonical query params)."""
    canonical = json.dumps({"source": source, **query_params}, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def capture(source: str, payload: Any, query_id: str, run_label: str) -> Path:
    """Write a sanitized fixture plus a manifest entry. Returns the fixture path."""
    base = _fixtures_dir()
    base.mkdir(parents=True, exist_ok=True)

    sanitized = _sanitize(payload)
    path = base / f"{query_id}_{source}.json"
    path.write_text(json.dumps(sanitized, indent=2, default=str) + "\n")

    manifest = _load_manifest()
    entry = {
        "query_id": query_id,
        "captured_at": datetime.now(UTC).isoformat(),
        "source": source,
        "fixture_hash": fixture_hash(sanitized),
        "sanitized": True,
        "run_label": run_label,
    }
    manifest.setdefault("fixtures", {})[f"{query_id}_{source}"] = entry
    _write_manifest(manifest)
    return path


def replay(source: str, query_id: str, *, verify_hash: bool = True) -> dict[str, Any]:
    """Read a captured fixture, raising a clear error if missing or mismatched."""
    base = _fixtures_dir()
    path = base / f"{query_id}_{source}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Replay fixture not found: {path}. Run with inventory_mode='capture' first."
        )
    payload = json.loads(path.read_text())

    manifest = _load_manifest()
    entry = (manifest.get("fixtures") or {}).get(f"{query_id}_{source}")
    if verify_hash and entry is not None:
        recorded = entry.get("fixture_hash")
        actual = fixture_hash(payload)
        if recorded and recorded != actual:
            raise ValueError(
                f"Fixture hash mismatch for {path.name}: manifest={recorded}, file={actual}"
            )
    return payload


def load_manifest() -> dict[str, Any]:
    """Public accessor for the capture/replay manifest."""
    return _load_manifest()


def _load_manifest() -> dict[str, Any]:
    path = _fixtures_dir() / _MANIFEST_NAME
    if not path.exists():
        return {"fixtures": {}}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"fixtures": {}}


def _write_manifest(manifest: dict[str, Any]) -> None:
    base = _fixtures_dir()
    base.mkdir(parents=True, exist_ok=True)
    (base / _MANIFEST_NAME).write_text(json.dumps(manifest, indent=2, default=str) + "\n")


def inventory_query_id(source: str, **query_params: Any) -> str:
    """Public helper for agents to derive a stable query id."""
    return _query_key(source, **query_params)
