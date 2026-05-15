"""
Unit tests for CollaborationHubAgent.
Tests conflict detection, message generation, and multi-round coordination.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.collaboration_hub import CollaborationHubAgent
from graph.state import TravelState


@pytest.fixture
def agent():
    """Create CollaborationHubAgent with mocked Anthropic client."""
    with patch("agents.collaboration_hub.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Mock the messages.create response
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Analysis: Hotel location conflicts with activities.")]
        mock_client.messages.create.return_value = mock_response

        agent = CollaborationHubAgent()
        agent.client = mock_client
        return agent


@pytest.fixture
def state_with_location_conflict():
    """State with hotel in Athens but activities in Santorini."""
    return {
        "intent": {
            "destination": "Greece",
            "budget_usd": 2000,
            "interests": ["beaches", "local food"]
        },
        "collaboration_round": 1,
        "hotel_recommendations": [{
            "name": "Athens Downtown Hotel",
            "location": "Athens",
            "price_per_night_usd": 90
        }],
        "experiences": [
            {
                "name": "Santorini Day Trip",
                "location": "Santorini",
                "price_usd": 150,
                "type": "beach"
            }
        ],
        "flight_options": [{
            "price_usd": 680,
            "arrival_time": "14:00"
        }],
        "weather_forecast": {
            "avg_temp_c": 33,
            "conditions": "sunny"
        },
        "visa_info": {
            "visa_required": False
        }
    }


@pytest.fixture
def state_no_conflicts():
    """State with no conflicts - hotel and activities in same location."""
    return {
        "intent": {
            "destination": "Greece",
            "budget_usd": 2000,
            "interests": ["beaches"]
        },
        "collaboration_round": 1,
        "hotel_recommendations": [{
            "name": "Santorini Beach Resort",
            "location": "Santorini",
            "price_per_night_usd": 85
        }],
        "experiences": [
            {
                "name": "Red Beach Visit",
                "location": "Santorini",
                "price_usd": 0,
                "type": "beach"
            }
        ],
        "flight_options": [{
            "price_usd": 680,
            "arrival_time": "14:00"
        }]
    }


@pytest.mark.asyncio
async def test_round_1_identifies_location_conflict(agent, state_with_location_conflict):
    """Test that Round 1 identifies hotel/activity location mismatch."""
    result = await agent._execute(state_with_location_conflict)

    assert result["collaboration_round"] == 1
    assert "conflicts" in result
    assert len(result["conflicts"]) > 0

    # Should identify location mismatch
    conflict_types = [c.get("type") for c in result["conflicts"]]
    assert "location_mismatch" in conflict_types


@pytest.mark.asyncio
async def test_round_1_generates_messages_for_conflicts(agent, state_with_location_conflict):
    """Test that Round 1 generates messages to relevant agents."""
    result = await agent._execute(state_with_location_conflict)

    assert "agent_messages" in result
    messages = result["agent_messages"]

    # Should send messages to hotel or experience agents
    recipient_agents = [msg.get("to_agent") for msg in messages]
    assert any(agent in recipient_agents for agent in ["hotel", "experience"])


@pytest.mark.asyncio
async def test_round_1_identifies_synergies(agent, state_no_conflicts):
    """Test that Round 1 identifies synergies when hotel and activities align."""
    result = await agent._execute(state_no_conflicts)

    assert "synergies" in result
    # With same location, should find synergies
    assert isinstance(result["synergies"], list)


@pytest.mark.asyncio
async def test_round_2_checks_conflict_resolution(agent):
    """Test that Round 2 checks if conflicts from Round 1 are resolved."""
    # State after Round 1 with conflicts
    state_round_2 = {
        "intent": {"destination": "Greece"},
        "collaboration_round": 2,
        "conflicts": [
            {"type": "location_mismatch", "resolved": False}
        ],
        "agent_messages": [],
        "hotel_recommendations": [{
            "name": "Santorini Resort",
            "location": "Santorini"
        }],
        "experiences": [{
            "name": "Santorini Beach",
            "location": "Santorini"
        }]
    }

    result = await agent._execute(state_round_2)

    assert result["collaboration_round"] == 2
    # Should detect conflict resolution
    assert "conflicts" in result


@pytest.mark.asyncio
async def test_round_2_no_new_messages_if_resolved(agent, state_no_conflicts):
    """Test that Round 2 doesn't generate new messages if conflicts are resolved."""
    state_no_conflicts["collaboration_round"] = 2
    state_no_conflicts["conflicts"] = []  # No conflicts from Round 1

    result = await agent._execute(state_no_conflicts)

    assert result["collaboration_round"] == 2
    # Should not generate new messages if everything is good
    messages = result.get("agent_messages", [])
    assert len(messages) == 0


@pytest.mark.asyncio
async def test_identifies_flight_timing_conflict(agent):
    """Test detection of late flight arrival wasting first day."""
    state = {
        "intent": {"destination": "Greece"},
        "collaboration_round": 1,
        "flight_options": [{
            "arrival_time": "23:00",  # Very late arrival
            "price_usd": 650
        }],
        "experiences": [
            {"name": "Morning Activity", "time": "morning"}
        ],
        "hotel_recommendations": [{"name": "Hotel"}]
    }

    result = await agent._execute(state)

    conflicts = result.get("conflicts", [])
    conflict_types = [c.get("type") for c in conflicts]

    # Should identify timing inefficiency
    assert any("timing" in str(c.get("type", "")).lower() for c in conflicts)


@pytest.mark.asyncio
async def test_identifies_weather_activity_conflict(agent):
    """Test detection of outdoor activities during rainy season."""
    state = {
        "intent": {"destination": "Greece", "interests": ["beaches"]},
        "collaboration_round": 1,
        "weather_forecast": {
            "avg_temp_c": 15,
            "conditions": "rainy",
            "precipitation_mm": 150
        },
        "experiences": [
            {"name": "Beach Day", "type": "outdoor", "location": "Santorini"}
        ],
        "hotel_recommendations": [{"name": "Hotel", "location": "Santorini"}],
        "flight_options": [{"price_usd": 600}]
    }

    result = await agent._execute(state)

    conflicts = result.get("conflicts", [])

    # Should identify weather conflicts with outdoor activities
    assert len(conflicts) > 0


@pytest.mark.asyncio
async def test_message_types_are_valid(agent, state_with_location_conflict):
    """Test that generated messages have valid message types."""
    result = await agent._execute(state_with_location_conflict)

    messages = result.get("agent_messages", [])

    valid_types = ["insight", "constraint", "question", "proposal", "conflict"]

    for msg in messages:
        assert "message_type" in msg
        assert msg["message_type"] in valid_types
        assert "from_agent" in msg
        assert msg["from_agent"] == "collaboration_hub"
        assert "to_agent" in msg
        assert "content" in msg


@pytest.mark.asyncio
async def test_shared_discoveries_extraction(agent, state_no_conflicts):
    """Test that shared insights are extracted from agent findings."""
    result = await agent._execute(state_no_conflicts)

    assert "shared_discoveries" in result
    # Should extract common themes or insights
    assert isinstance(result["shared_discoveries"], (list, dict))


@pytest.mark.asyncio
async def test_anthropic_api_called_with_correct_params(agent, state_with_location_conflict):
    """Test that Anthropic API is called with correct model and parameters."""
    await agent._execute(state_with_location_conflict)

    # Verify Anthropic client was called
    agent.client.messages.create.assert_called()

    call_args = agent.client.messages.create.call_args[1]
    assert "model" in call_args
    assert "messages" in call_args
    assert call_args["temperature"] <= 0.5  # Should use low temp for analysis
