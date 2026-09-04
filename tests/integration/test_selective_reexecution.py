"""Graph-level tests for selective re-execution (Priority 1 + acceptance criteria).

These run the actual graph node functions with the LLM and non-targeted agents
mocked, so they verify routing and lifecycle behaviour without any API keys or
network access.

  1. location mismatch → only hotel receives a message and re-runs.
  2. weather/experience/visa remain dormant during hotel re-execution.
  3. lifecycle marks the conflict resolved after hotel selects a qualifying candidate.
  4. no qualifying candidate → agent keeps original selection, audit reports
     unsatisfiable/persisting rather than a false success.
"""

from unittest.mock import MagicMock, patch

import pytest

from graph import travel_graph
from graph.travel_graph import (
    collaboration_hub_1_node,
    collaboration_hub_2_node,
    final_conflict_audit_node,
    research_round_2,
)


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
        "visa_safety": {"visa_required": False, "safety_level": "safe"},
        "flights": [], "hotels": [], "agent_messages": [], "conflicts": [],
        "synergies": [], "run_metrics": {}, "enable_refinement": True,
        "conflict_lifecycle_state": None,
    }


@pytest.fixture
def mocked_hub():
    """Replace the graph's hub singleton with a real hub whose LLM is mocked."""
    from agents.collaboration_hub import CollaborationHubAgent

    with patch("agents.collaboration_hub.Anthropic") as mock_anthropic, \
         patch("agents.collaboration_hub.get_api_config") as mock_cfg:
        mock_cfg.return_value.llm.api_key = "ci-test-key"
        mock_cfg.return_value.llm.collaboration_hub_model = "claude-haiku-4-5-20251001"
        client = MagicMock()
        mock_anthropic.return_value = client

        resp = MagicMock()
        resp.content = [MagicMock(text="Hub analysis narrative.")]
        resp.usage = MagicMock(input_tokens=100, output_tokens=50)
        client.messages.create.return_value = resp

        hub = CollaborationHubAgent()
        hub.client = client
        yield hub


@pytest.fixture
def dormant_agents(monkeypatch):
    """Track which research agents re-run; hotel applies a location hint for real."""
    calls = {"flight": 0, "hotel": 0, "experience": 0, "weather": 0, "visa_safety": 0}

    async def _noop(state):
        return {}

    for name in ("flight", "experience", "weather", "visa_safety"):
        async def _record(state, _n=name):
            calls[_n] += 1
            return {}
        monkeypatch.setattr(getattr(travel_graph, f"_{name}"), "run", _record)

    # Hotel re-runs for real (offline mock path) so it can resolve the mismatch.
    from agents.hotel_agent import HotelAgent
    hotel = HotelAgent()
    async def _hotel_run(state):
        calls["hotel"] += 1
        return await hotel._execute(state)
    monkeypatch.setattr(travel_graph._hotel, "run", _hotel_run)

    return calls


@pytest.mark.asyncio
async def test_location_mismatch_routes_only_hotel_and_resolves(mocked_hub, dormant_agents, monkeypatch):
    monkeypatch.setattr(travel_graph, "_collaboration_hub", mocked_hub)

    state = _location_mismatch_state()
    hub1 = await collaboration_hub_1_node(state)
    merged = {**state, **hub1}

    # Only the hotel should have been sent a constraint message.
    recipients = {m["to_agent"] for m in merged["agent_messages"]}
    assert "hotel" in recipients
    assert "experience" not in recipients

    await research_round_2(merged)

    # Only the hotel re-ran; weather, experience, visa, flight stayed dormant.
    assert dormant_agents["hotel"] == 1
    assert dormant_agents["weather"] == 0
    assert dormant_agents["experience"] == 0
    assert dormant_agents["visa_safety"] == 0
    assert dormant_agents["flight"] == 0


@pytest.mark.asyncio
async def test_lifecycle_marks_conflict_resolved_after_qualifying_hotel(mocked_hub, dormant_agents, monkeypatch):
    monkeypatch.setattr(travel_graph, "_collaboration_hub", mocked_hub)

    state = _location_mismatch_state()
    hub1 = await collaboration_hub_1_node(state)
    merged = {**state, **hub1}

    # Hotel re-run returns a hotel at the activity location (qualifying).
    from agents.hotel_agent import HotelAgent
    hotel = HotelAgent()
    async def _qualifying(state):
        return await hotel._execute(state)
    monkeypatch.setattr(travel_graph._hotel, "run", _qualifying)

    round2 = await research_round_2(merged)
    merged2 = {**merged, **round2}

    hub2 = await collaboration_hub_2_node(merged2)
    merged3 = {**merged2, **hub2}

    final = await final_conflict_audit_node(merged3)

    # The location_mismatch conflict is now resolved in the lifecycle.
    records = final["conflict_lifecycle"]
    loc_recs = [r for r in records if r["type"] == "location_mismatch"]
    assert loc_recs and loc_recs[0]["status"] == "resolved"
    assert loc_recs[0]["resolved_in_round"] is not None


@pytest.mark.asyncio
async def test_no_qualifying_candidate_reports_unsatisfiable(mocked_hub, dormant_agents, monkeypatch):
    monkeypatch.setattr(travel_graph, "_collaboration_hub", mocked_hub)

    state = _location_mismatch_state()
    hub1 = await collaboration_hub_1_node(state)
    merged = {**state, **hub1}

    # Hotel re-run cannot find a qualifying option and keeps its original far
    # selection, reporting an unsatisfiable feedback condition.
    async def _stubborn(state):
        return {
            "selected_hotel": {"name": "Aegean Bliss", "location": "Beachfront", "total_usd": 595},
            "hotels": state.get("hotels", []),
            "hotel_cost_usd": 595,
            "feedback_metrics": {
                "feedback_applied": True,
                "feedback_satisfiable": False,
                "fallback_to_original_selection": True,
                "reason": "no_qualifying_option",
            },
        }
    monkeypatch.setattr(travel_graph._hotel, "run", _stubborn)

    round2 = await research_round_2(merged)
    merged2 = {**merged, **round2}
    hub2 = await collaboration_hub_2_node(merged2)
    merged3 = {**merged2, **hub2}
    final = await final_conflict_audit_node(merged3)

    # Conflict persists (NOT resolved) — an honest "unsatisfiable" outcome.
    records = final["conflict_lifecycle"]
    loc_recs = [r for r in records if r["type"] == "location_mismatch"]
    assert loc_recs and loc_recs[0]["status"] == "persisting"
    assert merged3.get("feedback_metrics", {}).get("fallback_to_original_selection") is True
