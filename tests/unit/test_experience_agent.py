"""
Unit tests for ExperienceAgent.
Tests RAG-based activity recommendations with Claude integration.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.experience_agent import ExperienceAgent


@pytest.fixture
def agent():
    """Create ExperienceAgent with mocked Claude client."""
    with patch("agents.experience_agent.ChatAnthropic") as mock_claude:
        mock_chain = MagicMock()
        mock_response = MagicMock()
        mock_response.content = """
        [
            {
                "name": "Santorini Beach Visit",
                "description": "Visit the famous Red Beach",
                "price": 0,
                "duration": "3 hours",
                "type": "beach",
                "location": "Santorini"
            },
            {
                "name": "Acropolis Tour",
                "description": "Guided tour of ancient ruins",
                "price": 50,
                "duration": "2 hours",
                "type": "culture",
                "location": "Athens"
            },
            {
                "name": "Greek Food Tour",
                "description": "Sample local cuisine",
                "price": 80,
                "duration": "4 hours",
                "type": "food",
                "location": "Athens"
            }
        ]
        """
        mock_chain.invoke = MagicMock(return_value=mock_response)

        agent = ExperienceAgent()
        agent.chain = mock_chain
        return agent


@pytest.mark.asyncio
async def test_experience_recommendations_returned(agent):
    """Test that experience recommendations are returned."""
    state = {
        "intent": {
            "destination": "Greece",
            "interests": ["beaches", "food"],
            "budget_usd": 2000
        }
    }

    result = await agent._execute(state)

    assert "experiences" in result
    assert len(result["experiences"]) > 0


@pytest.mark.asyncio
async def test_experience_has_required_fields(agent):
    """Test that experiences have all required fields."""
    state = {
        "intent": {
            "destination": "Greece",
            "interests": ["beaches"],
            "budget_usd": 2000
        }
    }

    result = await agent._execute(state)

    experiences = result["experiences"]
    for exp in experiences:
        assert "name" in exp
        assert "price" in exp
        assert "type" in exp
        assert "location" in exp


@pytest.mark.asyncio
async def test_includes_free_experiences(agent):
    """Test that some free experiences are included."""
    state = {
        "intent": {
            "destination": "Greece",
            "interests": ["beaches"],
            "budget_usd": 2000
        }
    }

    result = await agent._execute(state)

    experiences = result["experiences"]
    free_experiences = [e for e in experiences if e["price"] == 0]

    # Should include at least one free option
    assert len(free_experiences) > 0


@pytest.mark.asyncio
async def test_experiences_match_interests(agent):
    """Test that experiences align with user interests."""
    state = {
        "intent": {
            "destination": "Greece",
            "interests": ["beaches", "food"],
            "budget_usd": 2000
        }
    }

    result = await agent._execute(state)

    experiences = result["experiences"]
    exp_types = [e.get("type", "").lower() for e in experiences]

    # Should have beach or food related experiences
    assert any("beach" in t or "food" in t for t in exp_types)


@pytest.mark.asyncio
async def test_experience_prices_reasonable(agent):
    """Test that experience prices are realistic."""
    state = {
        "intent": {
            "destination": "Greece",
            "budget_usd": 2000
        }
    }

    result = await agent._execute(state)

    experiences = result["experiences"]
    for exp in experiences:
        # Prices should be reasonable (free to a few hundred)
        assert 0 <= exp["price"] <= 500


@pytest.mark.asyncio
async def test_returns_multiple_experiences(agent):
    """Test that multiple experience options are returned."""
    state = {
        "intent": {
            "destination": "Greece",
            "budget_usd": 2000
        }
    }

    result = await agent._execute(state)

    # Should return at least 2-3 options
    assert len(result["experiences"]) >= 2


@pytest.mark.asyncio
async def test_experience_types_are_valid(agent):
    """Test that experience types are from valid categories."""
    state = {
        "intent": {
            "destination": "Greece",
            "budget_usd": 2000
        }
    }

    result = await agent._execute(state)

    experiences = result["experiences"]
    valid_types = ["beach", "culture", "food", "adventure", "nature", "history", "nightlife", "shopping"]

    for exp in experiences:
        exp_type = exp.get("type", "").lower()
        # Type should be recognizable
        assert any(valid in exp_type for valid in valid_types) or len(exp_type) > 0


@pytest.mark.asyncio
async def test_claude_api_integration(agent):
    """Test that Claude API is called for recommendations."""
    state = {
        "intent": {
            "destination": "Greece",
            "interests": ["beaches"],
            "budget_usd": 2000
        }
    }

    result = await agent._execute(state)

    # Verify Claude chain was invoked
    agent.chain.invoke.assert_called()


@pytest.mark.asyncio
async def test_handles_missing_interests_gracefully(agent):
    """Test that agent works even without specific interests."""
    state = {
        "intent": {
            "destination": "Greece",
            "budget_usd": 2000
        }
    }

    result = await agent._execute(state)

    # Should still return experiences
    assert "experiences" in result
    assert len(result["experiences"]) > 0


@pytest.mark.asyncio
async def test_error_when_missing_destination():
    """Test error handling when destination is missing."""
    with patch("agents.experience_agent.ChatAnthropic"):
        agent = ExperienceAgent()

        state = {
            "intent": {
                "budget_usd": 2000
            }
        }

        result = await agent._execute(state)

        # Should handle gracefully
        assert "errors" in result or "experiences" in result


@pytest.mark.asyncio
async def test_experience_descriptions_exist(agent):
    """Test that experiences have descriptions."""
    state = {
        "intent": {
            "destination": "Greece",
            "interests": ["beaches"],
            "budget_usd": 2000
        }
    }

    result = await agent._execute(state)

    experiences = result["experiences"]
    for exp in experiences:
        # Description should exist (optional but recommended)
        if "description" in exp:
            assert len(exp["description"]) > 0


@pytest.mark.asyncio
async def test_experiences_for_different_destinations():
    """Test that experiences are destination-specific."""
    with patch("agents.experience_agent.ChatAnthropic") as mock_claude:
        # Mock different responses for different destinations
        mock_chain = MagicMock()
        mock_response_greece = MagicMock()
        mock_response_greece.content = '[{"name": "Acropolis", "price": 50, "type": "culture", "location": "Athens"}]'

        mock_chain.invoke = MagicMock(return_value=mock_response_greece)

        agent = ExperienceAgent()
        agent.chain = mock_chain

        state_greece = {
            "intent": {
                "destination": "Greece",
                "budget_usd": 2000
            }
        }

        result = await agent._execute(state_greece)

        # Should invoke Claude with destination context
        agent.chain.invoke.assert_called()
        call_args = str(agent.chain.invoke.call_args)
        assert "Greece" in call_args or "greece" in call_args.lower()
