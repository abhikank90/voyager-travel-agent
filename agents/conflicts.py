"""
Conflict identity and lifecycle tracking.

Deterministic rule-based conflict detection (see `collaboration_hub`) produces
plain dicts. This module gives every conflict a *stable identity* across rounds
so the benchmark can answer a single question: **does targeted re-execution
converge, or does it oscillate?**

A conflict's identity is its fingerprint — a short SHA-256 digest over a
canonical rendering of (conflict_type, agents, normalized evidence ``data``).
Prose (``description``) and the round number are deliberately excluded so the
*same* logical conflict keeps the *same* fingerprint when it reappears after
refinement.

``data`` participates in identity so fingerprints are content-addressed per
query: two genuinely different conflicts (different activity locations, a heat
vs. rain advisory) hash to different fingerprints, making ``introduced``,
``resolved``, and ``reopened`` meaningful rather than vacuous. Because the
rules emit at most one conflict per type per audit, the evidence value is what
separates one query's conflict from another's. If refinement genuinely changes
the evidence (e.g. the experience set is replaced), that is treated as a
different conflict — an honest signal, not noise to be suppressed.

Lifecycle tracking then diffs the fingerprint set between successive hub audits
and classifies each conflict as ``new``, ``persisting``, ``resolved``, or
``reopened``.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

# ISO-8601 durations (e.g. "PT14H30M") canonicalized to total minutes so the
# same duration expressed with different formatting keeps one identity.
_ISO_DURATION = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?$")


def _canonical_scalar(value: Any) -> Any:
    """Return a round-independent, unit-canonical rendering of a scalar."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        # Round floats so tiny numeric noise between rounds never splits an identity.
        return round(float(value), 2) if isinstance(value, float) else value
    if isinstance(value, str):
        stripped = value.strip()
        m = _ISO_DURATION.match(stripped.upper())
        if m:
            hours = int(m.group(1) or 0)
            minutes = int(m.group(2) or 0)
            return f"duration_minutes:{hours * 60 + minutes}"
        return stripped.lower()
    return value


def deep_normalize(value: Any) -> Any:
    """Recursively normalize a payload so order, formatting, and rounding
    differences do not split a conflict identity.

    - dict keys are sorted and values normalized recursively.
    - lists are sorted after normalization (order-independent by contract).
    - floats are rounded; ISO-8601 durations become minutes; strings are
      lowercased/stripped.
    """
    if isinstance(value, dict):
        return {k: deep_normalize(v) for k, v in sorted(value.items())}
    if isinstance(value, list | tuple | set):
        normalized = [deep_normalize(v) for v in value]
        try:
            return sorted(normalized, key=lambda x: json.dumps(x, sort_keys=True))
        except TypeError:
            return normalized
    return _canonical_scalar(value)


@dataclass(frozen=True)
class Conflict:
    """A typed conflict between two or more agents.

    ``data`` carries structured, order-independent evidence (locations,
    thresholds, advisories) — never prose narrative — and participates in the
    identity fingerprint so it is content-addressed per query. ``description``
    is human-facing prose and is excluded from identity.
    """

    conflict_type: str
    agents: tuple[str, ...]
    data: dict[str, Any] = field(default_factory=dict)
    severity: str = "normal"
    description: str = ""

    @property
    def fingerprint(self) -> str:
        canonical = {
            "type": self.conflict_type,
            "agents": sorted(set(self.agents)),
            "data": deep_normalize(self.data),
        }
        return hashlib.sha256(
            json.dumps(canonical, sort_keys=True).encode("utf-8")
        ).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.conflict_type,
            "agents": list(self.agents),
            "data": dict(self.data),
            "severity": self.severity,
            "description": self.description,
            "fingerprint": self.fingerprint,
        }


def conflict_fingerprint(conflict: dict[str, Any]) -> str:
    """Fingerprint for a plain-dict conflict (the shape `_identify_conflicts` emits)."""
    return Conflict(
        conflict_type=conflict.get("type", ""),
        agents=tuple(conflict.get("agents", [])),
        data=conflict.get("data", {}),
        severity=conflict.get("severity", "normal"),
        description=conflict.get("description", ""),
    ).fingerprint


def attach_fingerprint(conflict: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of the conflict dict with a stable ``fingerprint`` key."""
    out = dict(conflict)
    out["fingerprint"] = conflict_fingerprint(conflict)
    return out


class ConflictLifecycleTracker:
    """Tracks conflict identity and lifecycle across hub audits.

    State is fully serializable so it can travel through the LangGraph state
    dict between nodes without a long-lived object.
    """

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._previous_fingerprints: set[str] = set()
        self._resolved_fingerprints: set[str] = set()
        self._round_fingerprints: dict[int, set[str]] = {}

    # ── Serialization ───────────────────────────────────────────────────────
    @classmethod
    def from_state(cls, state: dict[str, Any] | None) -> ConflictLifecycleTracker:
        tracker = cls()
        if not state:
            return tracker
        tracker._records = {
            fp: dict(rec) for fp, rec in (state.get("records") or {}).items()
        }
        tracker._previous_fingerprints = set(state.get("previous_fingerprints") or [])
        tracker._resolved_fingerprints = set(state.get("resolved_fingerprints") or [])
        tracker._round_fingerprints = {
            int(r): set(fps)
            for r, fps in (state.get("round_fingerprints") or {}).items()
        }
        return tracker

    def to_state(self) -> dict[str, Any]:
        return {
            "records": {fp: dict(rec) for fp, rec in self._records.items()},
            "previous_fingerprints": sorted(self._previous_fingerprints),
            "resolved_fingerprints": sorted(self._resolved_fingerprints),
            "round_fingerprints": {
                r: sorted(fps) for r, fps in sorted(self._round_fingerprints.items())
            },
        }

    # ── Lifecycle audit ─────────────────────────────────────────────────────
    def audit(
        self,
        current_conflicts: list[dict[str, Any]],
        round_num: int,
        introduced_after_agents: list[str] | None = None,
    ) -> dict[str, Any]:
        """Diff current conflicts against the previous round and return the
        state updates to merge (``conflicts_current``, ``conflict_lifecycle``,
        ``conflicts_introduced``, ``conflicts_resolved``, ``conflicts_persisting``,
        ``conflicts_reopened``)."""
        current = [attach_fingerprint(c) for c in current_conflicts]
        current_fps = {c["fingerprint"] for c in current}

        introduced: list[dict[str, Any]] = []
        resolved: list[dict[str, Any]] = []
        persisting: list[dict[str, Any]] = []
        reopened: list[dict[str, Any]] = []

        for conflict in current:
            fp = conflict["fingerprint"]
            rec = self._records.get(fp)

            if rec is None:
                # Truly new conflict (never seen before).
                rec = self._new_record(conflict, round_num, introduced_after_agents)
                rec["status"] = "new"
                self._records[fp] = rec
                introduced.append(rec)
                continue

            was_resolved = fp in self._resolved_fingerprints
            if was_resolved:
                # A conflict that had resolved and has now reappeared.
                self._resolved_fingerprints.discard(fp)
                rec["status"] = "reopened"
                rec["last_seen_round"] = round_num
                rec["resolved_in_round"] = None
                rec["introduced_after_agents"] = introduced_after_agents
                rec["persistence_count"] += 1
                reopened.append(rec)
            else:
                rec["status"] = "persisting"
                rec["last_seen_round"] = round_num
                rec["persistence_count"] += 1
                persisting.append(rec)

        # Conflicts present previously but absent now have resolved this round.
        for fp in self._previous_fingerprints - current_fps:
            rec = self._records[fp]
            rec["status"] = "resolved"
            rec["resolved_in_round"] = round_num
            self._resolved_fingerprints.add(fp)
            resolved.append(rec)

        self._previous_fingerprints = current_fps
        self._round_fingerprints[round_num] = current_fps

        return {
            "conflicts_current": current,
            "conflict_lifecycle": list(self._records.values()),
            "conflicts_introduced": introduced,
            "conflicts_resolved": resolved,
            "conflicts_persisting": persisting,
            "conflicts_reopened": reopened,
            "conflict_lifecycle_state": self.to_state(),
        }

    @staticmethod
    def _new_record(
        conflict: dict[str, Any],
        round_num: int,
        introduced_after_agents: list[str] | None,
    ) -> dict[str, Any]:
        return {
            "fingerprint": conflict["fingerprint"],
            "type": conflict.get("type", ""),
            "agents": sorted(conflict.get("agents", [])),
            "first_seen_round": round_num,
            "last_seen_round": round_num,
            "status": "new",
            "resolved_in_round": None,
            "persistence_count": 0,
            "introduced_after_agents": introduced_after_agents,
        }

    # ── Convergence summary ─────────────────────────────────────────────────
    def convergence_summary(self) -> dict[str, Any]:
        """Emit the churn/convergence metrics the collector surfaces.

        ``converged_round`` is the earliest round after which no Round-1
        conflict remains, or ``None`` if at least one Round-1 conflict is still
        unresolved at the final audit.
        """
        rounds = sorted(self._round_fingerprints)
        r1 = self._round_fingerprints.get(1, set())
        r2 = self._round_fingerprints.get(2, set())
        final_round = rounds[-1] if rounds else 1
        final = self._round_fingerprints.get(final_round, set())

        introduced_post = sum(
            1 for rec in self._records.values() if rec.get("first_seen_round", 1) > 1
        )
        reopened = sum(
            1 for rec in self._records.values() if rec.get("status") == "reopened"
        )

        resolved_by_round_2 = (
            len(r1) - len(r1 & r2) if 2 in self._round_fingerprints else 0
        )
        resolved_by_round_3 = (
            len(r1 & r2) - len(r1 & final) if final_round >= 3 else 0
        )

        if not r1:
            converged_round = 1
        elif 2 in self._round_fingerprints and not (r1 & r2):
            converged_round = 2
        elif not (r1 & final):
            converged_round = final_round
        else:
            converged_round = None

        return {
            "round_1_conflicts": len(r1),
            "round_2_conflicts_remaining": len(r1 & r2) if 2 in self._round_fingerprints else len(r1),
            "round_3_conflicts_remaining": len(r1 & final),
            "resolved_by_round_2": resolved_by_round_2,
            "resolved_by_round_3": resolved_by_round_3,
            "introduced_post_refinement": introduced_post,
            "reopened": reopened,
            "persisting_at_final_audit": len(r1 & final),
            "converged_round": converged_round,
        }
