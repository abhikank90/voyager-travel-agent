"""Unit tests for the conflict-type routing maps (Refs #14).

agents.conflicts is the single source of truth for conflict routing:
CONFLICT_RESOLVER (who resolves), CONFLICT_MESSAGE_TYPE (how the hub asks), and
the derived CONFLICT_TYPES and CONFLICT_ROUTE. The hub, the metrics collector,
and the hybrid detector read from these maps; these tests fail if any of them
drift apart.

No API or network access: the hub's Anthropic client is mocked and the
collector writes to a tmp_path sessions file.
"""

import json

import pytest

from agents import hybrid_conflict_detector
from agents.conflicts import (
    CONFLICT_MESSAGE_TYPE,
    CONFLICT_RESOLVER,
    CONFLICT_ROUTE,
    CONFLICT_TYPES,
)
from metrics import collector
from tests.unit.test_round3_targeting import _hub_state

EXPECTED_ROUTES = {
    "location_mismatch": ("hotel", "constraint"),
    "timing_inefficiency": ("flight", "insight"),
    "weather_activity_mismatch": ("experience", "constraint"),
}


# ── Map consistency ───────────────────────────────────────────────────────────

def test_maps_cover_the_same_conflict_types():
    assert set(CONFLICT_MESSAGE_TYPE) == set(CONFLICT_RESOLVER) == set(CONFLICT_TYPES) == set(EXPECTED_ROUTES)


def test_route_is_derived_from_resolver_and_message_type():
    assert set(CONFLICT_ROUTE) == CONFLICT_TYPES
    for conflict_type in CONFLICT_TYPES:
        assert CONFLICT_ROUTE[conflict_type] == (
            CONFLICT_RESOLVER[conflict_type],
            CONFLICT_MESSAGE_TYPE[conflict_type],
        )


def test_routes_match_current_values():
    # Guards the "no behaviour change" promise of the #14 refactor.
    assert CONFLICT_ROUTE == EXPECTED_ROUTES


def test_hybrid_detector_types_come_from_conflict_map():
    assert hybrid_conflict_detector.DETERMINISTIC_CONFLICT_TYPES == CONFLICT_TYPES


# ── Hub routing ───────────────────────────────────────────────────────────────

@pytest.fixture
def hub():
    """CollaborationHubAgent with Anthropic client mocked out."""
    from unittest.mock import MagicMock, patch

    from agents.collaboration_hub import CollaborationHubAgent

    with patch("agents.collaboration_hub.Anthropic") as mock_anthropic, \
         patch("agents.collaboration_hub.get_api_config") as mock_cfg:
        mock_cfg.return_value.llm.api_key = "ci-test-key"
        mock_cfg.return_value.llm.collaboration_hub_model = "claude-haiku-4-5-20251001"

        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        agent = CollaborationHubAgent()
        agent.client = mock_client
        yield agent


@pytest.mark.parametrize(
    ("setup", "conflict_type"),
    [
        ("location", "location_mismatch"),
        ("timing", "timing_inefficiency"),
        ("weather", "weather_activity_mismatch"),
    ],
)
def test_hub_message_uses_conflict_route(hub, setup, conflict_type):
    messages = hub._generate_collaboration_messages(_hub_state(setup), round=1)
    assert len(messages) == 1
    msg = messages[0]
    assert (msg["to_agent"], msg["message_type"]) == CONFLICT_ROUTE[conflict_type]


# ── Collector evidence join ───────────────────────────────────────────────────

@pytest.mark.parametrize("conflict_type", sorted(EXPECTED_ROUTES))
def test_collector_attaches_evidence_from_routed_message(tmp_path, monkeypatch, conflict_type):
    sessions_file = tmp_path / "sessions.jsonl"
    monkeypatch.setattr(collector, "_SESSIONS_FILE", sessions_file)

    to_agent, message_type = CONFLICT_ROUTE[conflict_type]
    final_state = {
        "conflicts": [{"type": conflict_type, "severity": "medium"}],
        "agent_messages": [
            {
                "from_agent": "collaboration_hub",
                "to_agent": to_agent,
                "message_type": message_type,
                "data": {"evidence": conflict_type},
                "round": 1,
            },
            # Same recipient, different message type: must not be picked up.
            {
                "from_agent": "collaboration_hub",
                "to_agent": to_agent,
                "message_type": "proposal",
                "data": {"decoy": True},
                "round": 1,
            },
        ],
        "run_metrics": {},
    }

    collector.record_session(final_state, query="q", duration_s=1.0)

    record = json.loads(sessions_file.read_text().strip())
    assert record["round_1_conflicts_evidence"] == [
        {"type": conflict_type, "severity": "medium", "data": {"evidence": conflict_type}}
    ]
