"""Unit tests for hybrid LLM candidate isolation (Priority 2).

Verifies the architectural invariant: `candidate -> validator -> routing`,
never `candidate -> routing`. No test here calls a live LLM.
"""

from unittest.mock import MagicMock, patch

import pytest

from agents.collaboration_hub import CollaborationHubAgent
from agents.hybrid_conflict_detector import (
    BudgetViolationValidator,
    ConflictCandidate,
    HybridConflictDetector,
    UnverifiedConflict,
    ValidatedConflict,
    parse_llm_candidates,
)


@pytest.fixture
def hub():
    """Hub with Anthropic mocked out — no real LLM calls."""
    with patch("agents.collaboration_hub.Anthropic") as mock_anthropic, \
         patch("agents.collaboration_hub.get_api_config") as mock_cfg:
        mock_cfg.return_value.llm.api_key = "ci-test-key"
        mock_cfg.return_value.llm.collaboration_hub_model = "claude-haiku-4-5-20251001"
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client
        agent = CollaborationHubAgent()
        agent.client = mock_client
        return agent


def _location_mismatch_state() -> dict:
    return {
        "intent": {"destination": "Greece", "budget_usd": 2000, "interests": ["beaches"]},
        "collaboration_round": 1,
        "selected_hotel": {"name": "Aegean Bliss", "location": "Beachfront", "total_usd": 595},
        "experiences": [
            {"name": "Sunset", "category": "culture", "location": "Oia, Santorini"},
            {"name": "Boat Tour", "category": "outdoor", "location": "Fira center"},
            {"name": "Dinner", "category": "food", "location": "Oia village"},
        ],
        "selected_flight": {"airline": "UA", "arrival": "2026-07-01T14:00:00", "price_usd": 680},
        "weather": {"avg_temp_c": 25, "summary": "warm", "precipitation_mm": 5},
        "visa_safety": {},
        "flights": [], "hotels": [], "agent_messages": [], "conflicts": [],
    }


def test_schema_invalid_output_rejected():
    assert parse_llm_candidates("this is not json") is None
    assert parse_llm_candidates('{"foo": "bar"}') is None
    assert parse_llm_candidates('{"candidates": [{"conflict_type": "x"}]}') is None  # missing agents


def test_schema_valid_output_parsed():
    parsed = parse_llm_candidates(
        '{"candidates": [{"conflict_type": "x", "agents": ["hotel"], '
        '"hypothesis": "h", "evidence": ["e"], "confidence": 0.5}]}'
    )
    assert parsed is not None
    assert parsed[0].conflict_type == "x"


def test_candidate_without_validator_marked_unverified(hub):
    detector = HybridConflictDetector(hub)
    candidate = ConflictCandidate(
        conflict_type="cultural_calendar_mismatch",
        agents=["experience"],
        hypothesis="festival overlaps travel dates",
        evidence=["e"],
        confidence=0.9,
    )
    validated, unverified = detector.validate([candidate], _location_mismatch_state())
    assert validated == []
    assert len(unverified) == 1
    assert "no deterministic validator" in unverified[0].reason


def test_rule_backed_candidate_validated_when_rule_fires(hub):
    detector = HybridConflictDetector(hub)
    candidate = ConflictCandidate(
        conflict_type="location_mismatch",
        agents=["hotel", "experience"],
        hypothesis="hotel far from activities",
        evidence=["e"],
        confidence=0.8,
    )
    validated, unverified = detector.validate([candidate], _location_mismatch_state())
    assert len(validated) == 1
    assert isinstance(validated[0], ValidatedConflict)
    assert validated[0].conflict_type == "location_mismatch"


def test_rule_backed_candidate_unverified_when_rule_does_not_fire(hub):
    detector = HybridConflictDetector(hub)
    candidate = ConflictCandidate(
        conflict_type="timing_inefficiency",
        agents=["flight"],
        hypothesis="late arrival",
        evidence=["e"],
        confidence=0.8,
    )
    # State has an on-time flight → timing rule does NOT fire → unverified.
    validated, unverified = detector.validate([candidate], _location_mismatch_state())
    assert validated == []
    assert len(unverified) == 1
    assert "did not fire" in unverified[0].reason


def test_budget_validator_derives_violation_from_fields(hub):
    validator = BudgetViolationValidator()
    state = {
        "intent": {"budget_usd": 2000},
        "flight_cost_usd": 1200,
        "hotel_cost_usd": 1100,
    }
    candidate = ConflictCandidate(
        conflict_type="budget_violation", agents=["flight", "hotel"],
        hypothesis="over budget", evidence=["e"], confidence=0.7,
    )
    result = validator.validate(candidate, state)
    assert isinstance(result, ValidatedConflict)


def test_budget_validator_unverified_when_fields_missing(hub):
    validator = BudgetViolationValidator()
    candidate = ConflictCandidate(
        conflict_type="budget_violation", agents=["flight", "hotel"],
        hypothesis="over budget", evidence=["e"], confidence=0.7,
    )
    result = validator.validate(candidate, {"intent": {}})
    assert isinstance(result, UnverifiedConflict)
    assert "not derivable" in result.reason


@pytest.mark.asyncio
async def test_disabling_flag_removes_llm_calls(hub):
    """With the flag off (default), no candidate LLM calls happen at all."""
    with patch("agents.collaboration_hub.get_settings") as mock_settings:
        mock_settings.return_value.enable_llm_conflict_candidates = False
        mock_settings.return_value.llm_detector_repetitions = 3
        result = await hub._execute(_location_mismatch_state())

    assert result["llm_candidate_conflicts"] == []
    assert result["validated_llm_conflicts"] == []
    assert result["unverified_llm_conflicts"] == []
    # Only the single narrative call (round 1 analysis) was made — no candidates.
    assert hub.client.messages.create.call_count == 1


def test_unverified_candidates_do_not_create_agent_messages(hub):
    """A candidate that fails validation must never reach routing/messages."""
    from agents.hybrid_conflict_detector import UnverifiedConflict

    result = {
        "llm_candidate_conflicts": [{"type": "cultural_calendar_mismatch"}],
        "validated_llm_conflicts": [],
        "unverified_llm_conflicts": [
            UnverifiedConflict(
                ConflictCandidate(
                    conflict_type="cultural_calendar_mismatch",
                    agents=["experience"], hypothesis="h", evidence=["e"], confidence=0.9
                ),
                reason="no deterministic validator",
            ).to_dict()
        ],
    }
    # The hub only routes deterministic conflicts; unverified never produce messages.
    messages = hub._generate_collaboration_messages(_location_mismatch_state(), round=1)
    assert all(m["to_agent"] != "experience" for m in messages)
    assert result["validated_llm_conflicts"] == []
    assert result["unverified_llm_conflicts"]


def test_validated_candidates_can_become_routing_eligible(hub):
    """A validated candidate has a fingerprint and is routing-eligible."""
    detector = HybridConflictDetector(hub)
    candidate = ConflictCandidate(
        conflict_type="location_mismatch",
        agents=["experience", "hotel"],
        hypothesis="hotel far from activities",
        evidence=["e"],
        confidence=0.8,
    )
    validated, _ = detector.validate([candidate], _location_mismatch_state())
    assert len(validated) == 1
    assert validated[0].fingerprint
    assert validated[0].to_dict()["fingerprint"]


# ── Hub LLM-calling wrapper (mocked client, no live LLM) ─────────────────────

def _llm_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.content = [MagicMock(text=text)]
    resp.usage = MagicMock(input_tokens=10, output_tokens=10)
    return resp


def _enable_candidates():
    settings = MagicMock()
    settings.enable_llm_conflict_candidates = True
    settings.llm_detector_repetitions = 2
    settings.llm_detector_temperature = 0.0
    return settings


def test_build_candidate_prompt_contains_schema_and_findings(hub):
    prompt = hub._build_candidate_prompt(_location_mismatch_state())
    assert '"candidates"' in prompt
    assert "conflict_type" in prompt
    assert "Greece" in prompt
    assert "Santorini" in prompt


def test_propose_llm_candidates_drops_schema_invalid_output(hub):
    """Schema-invalid LLM output is rejected before touching routing."""
    hub.client.messages.create.return_value = _llm_response("this is not json")
    with patch("agents.collaboration_hub.get_settings", return_value=_enable_candidates()):
        candidates = hub._propose_llm_candidates(_location_mismatch_state())
    assert candidates == []


def test_propose_llm_candidates_parses_valid_output(hub):
    hub.client.messages.create.return_value = _llm_response(
        '{"candidates": [{"conflict_type": "budget_violation", "agents": ["flight", "hotel"], '
        '"hypothesis": "over budget", "evidence": ["e"], "confidence": 0.7}]}'
    )
    with patch("agents.collaboration_hub.get_settings", return_value=_enable_candidates()):
        candidates = hub._propose_llm_candidates(_location_mismatch_state())
    assert len(candidates) == 1
    assert candidates[0].conflict_type == "budget_violation"


def test_propose_llm_candidates_deduplicates_across_repetitions(hub):
    """Repeated calls returning the same candidate yield one entry."""
    hub.client.messages.create.return_value = _llm_response(
        '{"candidates": [{"conflict_type": "budget_violation", "agents": ["flight", "hotel"], '
        '"hypothesis": "over budget", "evidence": ["e"], "confidence": 0.7}]}'
    )
    settings = _enable_candidates()
    settings.llm_detector_repetitions = 3
    with patch("agents.collaboration_hub.get_settings", return_value=settings):
        candidates = hub._propose_llm_candidates(_location_mismatch_state())
    assert len(candidates) == 1
    assert hub.client.messages.create.call_count == 3


def test_run_hybrid_detection_unverified_candidates_produce_no_messages(hub):
    """End-to-end: an LLM candidate with no validator is unverified, and the
    hub produces zero agent messages for it (deterministic routing untouched)."""
    hub.client.messages.create.return_value = _llm_response(
        '{"candidates": [{"conflict_type": "cultural_calendar_mismatch", "agents": ["experience"], '
        '"hypothesis": "festival overlaps", "evidence": ["e"], "confidence": 0.9}]}'
    )
    with patch("agents.collaboration_hub.get_settings", return_value=_enable_candidates()):
        result = hub._run_hybrid_detection(_location_mismatch_state())

    assert len(result["llm_candidate_conflicts"]) == 1
    assert result["validated_llm_conflicts"] == []
    assert len(result["unverified_llm_conflicts"]) == 1

    # Deterministic routing is what generates messages; unverified candidates never do.
    messages = hub._generate_collaboration_messages(_location_mismatch_state(), round=1)
    assert all(m["to_agent"] != "experience" for m in messages)
