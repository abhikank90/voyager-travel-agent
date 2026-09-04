"""
Hybrid LLM conflict detector — "propose, verify, never route directly".

The deterministic rule-based detector (see `collaboration_hub._identify_conflicts`)
is the authoritative routing layer. This module lets an LLM *propose* candidate
conflicts that the rules may not enumerate (cultural-calendar mismatches,
multi-hop loops, budget sums across components), but a candidate only earns
routing authority if a deterministic validator accepts it.

Architectural rule:

    candidate -> validator -> routing        (correct)
    candidate -> routing                     (forbidden)

Candidates are kept in separate state fields (`llm_candidate_conflicts`,
`validated_llm_conflicts`, `unverified_llm_conflicts`) and are never merged into
`conflicts`/`deterministic_conflicts` directly.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import BaseModel, Field

from agents.conflicts import Conflict, conflict_fingerprint


# ── Strict LLM output schema ──────────────────────────────────────────────────
class ConflictCandidate(BaseModel):
    """A single candidate conflict proposed by the LLM."""

    conflict_type: str
    agents: list[str]
    hypothesis: str
    evidence: list[str]
    suggested_rule: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class LLMConflictResponse(BaseModel):
    """The complete LLM output. Schema-invalid output is rejected wholesale."""

    candidates: list[ConflictCandidate]


# ── Validation outcomes ───────────────────────────────────────────────────────
@dataclass
class ValidatedConflict:
    """A candidate accepted by a deterministic validator. Routing-eligible."""

    conflict_type: str
    agents: list[str]
    fingerprint: str
    data: dict[str, Any]
    confidence: float
    suggested_rule: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.conflict_type,
            "agents": sorted(self.agents),
            "fingerprint": self.fingerprint,
            "data": self.data,
            "confidence": self.confidence,
            "suggested_rule": self.suggested_rule,
        }


@dataclass
class UnverifiedConflict:
    """A candidate that no deterministic validator could confirm.

    Must never trigger targeted feedback or produce an agent message.
    """

    candidate: ConflictCandidate
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.candidate.conflict_type,
            "agents": sorted(self.candidate.agents),
            "hypothesis": self.candidate.hypothesis,
            "reason": self.reason,
            "confidence": self.candidate.confidence,
        }


class ConflictValidator(Protocol):
    """Deterministic validator for a proposed candidate."""

    def validate(
        self, candidate: ConflictCandidate, state: dict[str, Any]
    ) -> ValidatedConflict | UnverifiedConflict: ...


# ── Deterministic validators ─────────────────────────────────────────────────
# Conflict types the deterministic rules can independently prove. A candidate
# naming any other type has no deterministic validator and is always unverified.
DETERMINISTIC_CONFLICT_TYPES = frozenset({
    "location_mismatch",
    "timing_inefficiency",
    "weather_activity_mismatch",
})


class RuleBackedValidator:
    """Accepts a candidate only if the deterministic rules independently fire.

    The candidate must name a conflict type the rules already detect, and the
    rules must actually detect it in the current state. This is the strongest
    possible confirmation: the LLM re-derives what a rule can prove.
    """

    def __init__(self, hub) -> None:
        self._hub = hub

    def accepts(self, candidate: ConflictCandidate) -> bool:
        """Only known deterministic rule types can be rule-validated."""
        return candidate.conflict_type in DETERMINISTIC_CONFLICT_TYPES

    def validate(
        self, candidate: ConflictCandidate, state: dict[str, Any]
    ) -> ValidatedConflict | UnverifiedConflict:
        try:
            detected = self._hub.detect_conflicts_only(state)
        except Exception as exc:  # pragma: no cover - defensive
            return UnverifiedConflict(candidate, reason=f"validator error: {exc}")

        match = next(
            (c for c in detected if c.get("type") == candidate.conflict_type), None
        )
        if match is None:
            return UnverifiedConflict(
                candidate,
                reason=(
                    f"rule for {candidate.conflict_type!r} did not fire — "
                    "candidate not independently confirmable"
                ),
            )
        return ValidatedConflict(
            conflict_type=match["type"],
            agents=list(match.get("agents", candidate.agents)),
            fingerprint=conflict_fingerprint(match),
            data=match.get("data", {}),
            confidence=candidate.confidence,
            suggested_rule=candidate.suggested_rule,
        )


class BudgetViolationValidator:
    """Deterministic budget validator: derives the alleged violation from actual
    budget/price fields. If the sum cannot be derived, the candidate is
    unverified — never routed on an LLM's say-so alone."""

    def accepts(self, candidate: ConflictCandidate) -> bool:
        return candidate.conflict_type == "budget_violation"

    def validate(
        self, candidate: ConflictCandidate, state: dict[str, Any]
    ) -> ValidatedConflict | UnverifiedConflict:
        intent = state.get("intent", {})
        budget = intent.get("budget_usd")
        flight_cost = state.get("flight_cost_usd")
        hotel_cost = state.get("hotel_cost_usd")

        if budget is None or flight_cost is None or hotel_cost is None:
            return UnverifiedConflict(
                candidate,
                reason="budget/price fields missing — violation not derivable",
            )

        total = flight_cost + hotel_cost
        if total > budget:
            conflict = Conflict(
                conflict_type="budget_violation",
                agents=("flight", "hotel"),
                data={
                    "budget_usd": round(float(budget), 2),
                    "flight_hotel_sum_usd": round(float(total), 2),
                },
            )
            return ValidatedConflict(
                conflict_type="budget_violation",
                agents=["flight", "hotel"],
                fingerprint=conflict.fingerprint,
                data=conflict.data,
                confidence=candidate.confidence,
                suggested_rule=candidate.suggested_rule,
            )
        return UnverifiedConflict(
            candidate, reason=f"total {total:.2f} within budget {budget:.2f}"
        )


# ── Detector ─────────────────────────────────────────────────────────────────
class HybridConflictDetector:
    """Proposes candidate conflicts via the LLM and validates each against
    deterministic validators before anything is allowed to route."""

    def __init__(self, hub, validators: list[ConflictValidator] | None = None) -> None:
        self._hub = hub
        self._validators = validators or [RuleBackedValidator(hub), BudgetViolationValidator()]

    def validate(
        self, candidates: list[ConflictCandidate], state: dict[str, Any]
    ) -> tuple[list[ValidatedConflict], list[UnverifiedConflict]]:
        validated: list[ValidatedConflict] = []
        unverified: list[UnverifiedConflict] = []
        for candidate in candidates:
            result = self._validate_one(candidate, state)
            if isinstance(result, ValidatedConflict):
                validated.append(result)
            else:
                unverified.append(result)
        return validated, unverified

    def _validate_one(
        self, candidate: ConflictCandidate, state: dict[str, Any]
    ) -> ValidatedConflict | UnverifiedConflict:
        applicable = [
            v for v in self._validators
            if getattr(v, "accepts", lambda c: True)(candidate)
        ]
        if not applicable:
            return UnverifiedConflict(
                candidate, reason=f"no deterministic validator for {candidate.conflict_type!r}"
            )
        last_unverified: UnverifiedConflict | None = None
        for validator in applicable:
            result = validator.validate(candidate, state)
            if isinstance(result, ValidatedConflict):
                return result
            last_unverified = result
        return last_unverified or UnverifiedConflict(
            candidate, reason=f"candidate {candidate.conflict_type!r} failed validation"
        )


def parse_llm_candidates(text: str) -> list[ConflictCandidate] | None:
    """Parse LLM output into candidates, rejecting schema-invalid output.

    Returns ``None`` when the payload cannot be parsed into a valid
    ``LLMConflictResponse`` (markdown fences are tolerated).
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`").lstrip("json").strip()
    try:
        data = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict) and "candidates" in data:
        data = data["candidates"]
    if not isinstance(data, list):
        return None
    try:
        return [
            ConflictCandidate.model_validate(c)
            for c in data
        ]
    except Exception:
        return None
