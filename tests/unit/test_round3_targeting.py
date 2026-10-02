"""Unit tests for Round-3 resolver targeting (Refs #11).

`research_round_3` must re-run only the designated resolver for each surviving
conflict type (agents.conflicts.CONFLICT_RESOLVER) — not every participant in
the conflict — and the hub must route its feedback messages through the same
map so routing and Round-3 targeting cannot drift.

Agent singletons are monkeypatched to record calls; no API or network access.
"""

import os

import pytest

from agents.conflicts import CONFLICT_RESOLVER


@pytest.fixture(scope="module")
def travel_graph_module():
    """Import the graph once with a test API key (agent singletons construct
    Anthropic clients at import time)."""
    prior = os.environ.get("ANTHROPIC_API_KEY")
    os.environ["ANTHROPIC_API_KEY"] = "ci-test-key"
    try:
        from graph import travel_graph

        return travel_graph
    finally:
        if prior is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = prior


@pytest.fixture
def agent_calls(travel_graph_module, monkeypatch):
    """Track which research agents re-run during Round 3."""
    calls = {"flight": 0, "hotel": 0, "experience": 0}

    for name in calls:
        async def _record(state, _name=name):
            calls[_name] += 1
            return {}

        monkeypatch.setattr(getattr(travel_graph_module, f"_{name}"), "run", _record)
    return calls


def _state(conflicts):
    return {
        "conflicts": conflicts,
        "collaboration_round": 2,
        "agent_messages": [],
        "run_metrics": {},
        "enable_refinement": True,
    }


LOCATION = {"type": "location_mismatch", "agents": ["hotel", "experience"]}
TIMING = {"type": "timing_inefficiency", "agents": ["flight"]}
WEATHER = {"type": "weather_activity_mismatch", "agents": ["weather", "experience"]}


@pytest.mark.asyncio
async def test_location_conflict_reruns_hotel_only(travel_graph_module, agent_calls):
    result = await travel_graph_module.research_round_3(_state([LOCATION]))
    assert agent_calls == {"flight": 0, "hotel": 1, "experience": 0}
    assert result["run_metrics"]["round_3_agents_rerun"] == ["hotel"]
    assert result["run_metrics"]["round_3_agents_rerun_count"] == 1


@pytest.mark.asyncio
async def test_timing_conflict_reruns_flight_only(travel_graph_module, agent_calls):
    result = await travel_graph_module.research_round_3(_state([TIMING]))
    assert agent_calls == {"flight": 1, "hotel": 0, "experience": 0}
    assert result["run_metrics"]["round_3_agents_rerun"] == ["flight"]
    assert result["run_metrics"]["round_3_agents_rerun_count"] == 1


@pytest.mark.asyncio
async def test_weather_conflict_reruns_experience_only(travel_graph_module, agent_calls):
    result = await travel_graph_module.research_round_3(_state([WEATHER]))
    assert agent_calls == {"flight": 0, "hotel": 0, "experience": 1}
    assert result["run_metrics"]["round_3_agents_rerun"] == ["experience"]
    assert result["run_metrics"]["round_3_agents_rerun_count"] == 1


@pytest.mark.asyncio
async def test_mixed_conflicts_rerun_union_of_resolvers(travel_graph_module, agent_calls):
    result = await travel_graph_module.research_round_3(_state([LOCATION, TIMING]))
    assert agent_calls == {"flight": 1, "hotel": 1, "experience": 0}
    assert result["run_metrics"]["round_3_agents_rerun"] == ["flight", "hotel"]
    assert result["run_metrics"]["round_3_agents_rerun_count"] == 2


@pytest.mark.asyncio
async def test_round_3_rerun_count_reflects_resolver_set(travel_graph_module, agent_calls):
    # Duplicate surviving conflicts of one type collapse to a single resolver.
    result = await travel_graph_module.research_round_3(_state([WEATHER, WEATHER]))
    assert agent_calls == {"flight": 0, "hotel": 0, "experience": 1}
    assert result["run_metrics"]["round_3_agents_rerun"] == ["experience"]
    assert result["run_metrics"]["round_3_agents_rerun_count"] == 1


@pytest.mark.asyncio
async def test_unknown_conflict_type_reruns_nothing(travel_graph_module, agent_calls):
    result = await travel_graph_module.research_round_3(_state(
        [{"type": "unknown_rule", "agents": ["hotel", "experience"]}]
    ))
    assert agent_calls == {"flight": 0, "hotel": 0, "experience": 0}
    assert result["run_metrics"]["round_3_agents_rerun"] == []
    assert result["run_metrics"]["round_3_agents_rerun_count"] == 0


# ── Hub/map consistency ───────────────────────────────────────────────────────

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
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hub analysis narrative.")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
        mock_client.messages.create.return_value = mock_response

        agent = CollaborationHubAgent()
        agent.client = mock_client
        yield agent


def _hub_state(conflicts_setup: str) -> dict:
    base = {
        "intent": {"destination": "Greece", "budget_usd": 2000, "interests": ["beaches"]},
        "collaboration_round": 1,
        "flights": [], "hotels": [], "agent_messages": [], "conflicts": [],
    }
    if conflicts_setup == "location":
        base.update({
            "selected_hotel": {"name": "Aegean Bliss", "location": "Beachfront", "total_usd": 595},
            "experiences": [
                {"name": "Sunset", "category": "culture", "location": "Oia, Santorini"},
                {"name": "Boat Tour", "category": "outdoor", "location": "Fira center"},
                {"name": "Dinner", "category": "food", "location": "Oia village"},
            ],
            "selected_flight": {"airline": "UA", "arrival": "2026-07-01T14:00:00", "price_usd": 680},
            "weather": {"avg_temp_c": 25, "summary": "warm", "precipitation_mm": 5},
        })
    elif conflicts_setup == "timing":
        base.update({
            "selected_hotel": {"name": "Santorini Resort", "location": "Santorini", "total_usd": 700},
            "experiences": [
                {"name": "Red Beach", "category": "beach", "location": "Santorini"},
                {"name": "Oia Walk", "category": "culture", "location": "Santorini"},
                {"name": "Taverna", "category": "food", "location": "Santorini"},
            ],
            "selected_flight": {"airline": "UA", "arrival": "2026-07-01T22:00:00", "price_usd": 680},
            "weather": {"avg_temp_c": 28, "summary": "warm", "precipitation_mm": 2},
        })
    elif conflicts_setup == "weather":
        base.update({
            "selected_hotel": {"name": "Santorini Resort", "location": "Santorini", "total_usd": 700},
            "experiences": [
                {"name": "Red Beach", "category": "beach", "location": "Santorini"},
                {"name": "Sunset Beach", "category": "beach", "location": "Santorini"},
                {"name": "Taverna", "category": "food", "location": "Santorini"},
            ],
            "selected_flight": {"airline": "LH", "arrival": "2026-07-01T13:00:00", "price_usd": 890},
            "weather": {"avg_temp_c": 35, "summary": "hot", "precipitation_mm": 0},
        })
    return base


@pytest.mark.parametrize(
    ("setup", "conflict_type"),
    [
        ("location", "location_mismatch"),
        ("timing", "timing_inefficiency"),
        ("weather", "weather_activity_mismatch"),
    ],
)
def test_hub_message_route_matches_resolver_map(hub, setup, conflict_type):
    messages = hub._generate_collaboration_messages(_hub_state(setup), round=1)
    assert len(messages) == 1
    assert messages[0]["to_agent"] == CONFLICT_RESOLVER[conflict_type]


def test_resolver_map_covers_all_routed_conflict_types():
    # Every conflict type the hub can route must have exactly one resolver, and
    # that resolver must be re-runnable (round-3 filter includes it).
    assert set(CONFLICT_RESOLVER) == {"location_mismatch", "timing_inefficiency", "weather_activity_mismatch"}
    assert set(CONFLICT_RESOLVER.values()) <= {"flight", "hotel", "experience"}