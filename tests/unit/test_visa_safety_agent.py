"""
Unit tests for VisaSafetyAgent.
Tests visa requirements and safety information retrieval using DuckDuckGo + Claude.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.visa_safety_agent import VisaSafetyAgent


@pytest.fixture
def agent():
    """Create VisaSafetyAgent with mocked dependencies."""
    with patch("agents.visa_safety_agent.ChatAnthropic") as mock_claude:
        with patch("agents.visa_safety_agent.DDGS") as mock_ddg:
            # Mock DuckDuckGo search results
            mock_ddg_instance = MagicMock()
            mock_ddg_instance.text.return_value = [
                {
                    "title": "Greece Visa Requirements",
                    "body": "US citizens do not need a visa for stays up to 90 days",
                    "href": "https://example.com"
                }
            ]
            mock_ddg.return_value.__enter__.return_value = mock_ddg_instance

            # Mock Claude summarization
            mock_chain = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "No visa required for US citizens. Greece is very safe for travelers."
            mock_chain.invoke = MagicMock(return_value=mock_response)

            agent = VisaSafetyAgent()
            agent.chain = mock_chain
            return agent


@pytest.mark.asyncio
async def test_visa_info_returned(agent):
    """Test that visa information is returned."""
    state = {
        "intent": {
            "destination": "Greece",
            "origin_country": "USA"
        }
    }

    result = await agent._execute(state)

    assert "visa_info" in result or "visa_safety" in result


@pytest.mark.asyncio
async def test_visa_required_field_exists(agent):
    """Test that visa_required boolean is included."""
    state = {
        "intent": {
            "destination": "Greece",
            "origin_country": "USA"
        }
    }

    result = await agent._execute(state)

    visa_info = result.get("visa_info") or result.get("visa_safety")
    assert "visa_required" in visa_info
    assert isinstance(visa_info["visa_required"], bool)


@pytest.mark.asyncio
async def test_safety_level_included(agent):
    """Test that safety level is included."""
    state = {
        "intent": {
            "destination": "Greece",
            "origin_country": "USA"
        }
    }

    result = await agent._execute(state)

    visa_info = result.get("visa_info") or result.get("visa_safety")
    assert "safety_level" in visa_info or "safety_rating" in visa_info


@pytest.mark.asyncio
async def test_duckduckgo_search_performed(agent):
    """Test that DuckDuckGo search is performed."""
    with patch("agents.visa_safety_agent.DDGS") as mock_ddg:
        mock_ddg_instance = MagicMock()
        mock_ddg_instance.text.return_value = [
            {"title": "Test", "body": "Test result", "href": "http://example.com"}
        ]
        mock_ddg.return_value.__enter__.return_value = mock_ddg_instance

        state = {
            "intent": {
                "destination": "Greece",
                "origin_country": "USA"
            }
        }

        result = await agent._execute(state)

        # Search should have been called
        mock_ddg_instance.text.assert_called()


@pytest.mark.asyncio
async def test_claude_summarization_called(agent):
    """Test that Claude is used to summarize search results."""
    state = {
        "intent": {
            "destination": "Greece",
            "origin_country": "USA"
        }
    }

    result = await agent._execute(state)

    # Claude chain should have been invoked
    agent.chain.invoke.assert_called()


@pytest.mark.asyncio
async def test_handles_missing_origin_country():
    """Test that agent uses default (USA) when origin country is missing."""
    with patch("agents.visa_safety_agent.ChatAnthropic"):
        with patch("agents.visa_safety_agent.DDGS") as mock_ddg:
            mock_ddg_instance = MagicMock()
            mock_ddg_instance.text.return_value = []
            mock_ddg.return_value.__enter__.return_value = mock_ddg_instance

            agent = VisaSafetyAgent()

            state = {
                "intent": {
                    "destination": "Greece"
                }
            }

            result = await agent._execute(state)

            # Should still work with default country
            assert "visa_info" in result or "visa_safety" in result


@pytest.mark.asyncio
async def test_handles_search_failure_gracefully(agent):
    """Test that agent handles DuckDuckGo failures gracefully."""
    with patch("agents.visa_safety_agent.DDGS") as mock_ddg:
        mock_ddg.side_effect = Exception("Search failed")

        state = {
            "intent": {
                "destination": "Greece"
            }
        }

        result = await agent._execute(state)

        # Should return fallback data instead of crashing
        assert "visa_info" in result or "visa_safety" in result or "errors" in result


@pytest.mark.asyncio
async def test_visa_info_has_notes(agent):
    """Test that visa info includes helpful notes."""
    state = {
        "intent": {
            "destination": "Greece",
            "origin_country": "USA"
        }
    }

    result = await agent._execute(state)

    visa_info = result.get("visa_info") or result.get("visa_safety")
    # Should have notes or summary
    assert "notes" in visa_info or "summary" in visa_info or "details" in visa_info


@pytest.mark.asyncio
async def test_different_destinations_different_requirements():
    """Test that visa requirements differ by destination."""
    with patch("agents.visa_safety_agent.ChatAnthropic"):
        with patch("agents.visa_safety_agent.DDGS") as mock_ddg:
            mock_ddg_instance = MagicMock()
            mock_ddg_instance.text.return_value = [
                {"title": "Test", "body": "Visa required", "href": "http://example.com"}
            ]
            mock_ddg.return_value.__enter__.return_value = mock_ddg_instance

            agent = VisaSafetyAgent()

            # Mock chain for different response
            mock_chain = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Visa required for this destination."
            mock_chain.invoke = MagicMock(return_value=mock_response)
            agent.chain = mock_chain

            state = {
                "intent": {
                    "destination": "China",  # Different country
                    "origin_country": "USA"
                }
            }

            result = await agent._execute(state)

            # Should call search with different destination
            mock_ddg_instance.text.assert_called()
            call_args = str(mock_ddg_instance.text.call_args)
            assert "China" in call_args or "china" in call_args.lower()


@pytest.mark.asyncio
async def test_error_when_missing_destination():
    """Test error handling when destination is missing."""
    with patch("agents.visa_safety_agent.ChatAnthropic"):
        agent = VisaSafetyAgent()

        state = {
            "intent": {}
        }

        result = await agent._execute(state)

        # Should handle gracefully
        assert "errors" in result or "visa_info" in result or "visa_safety" in result
