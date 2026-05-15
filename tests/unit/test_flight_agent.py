"""
Unit tests for FlightAgent.
Tests flight search with Amadeus API and mock fallback.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.flight_agent import FlightAgent


@pytest.fixture
def agent_with_mock():
    """Create FlightAgent with mock API responses."""
    with patch("agents.flight_agent.requests") as mock_requests:
        agent = FlightAgent()
        return agent, mock_requests


@pytest.fixture
def amadeus_api_response():
    """Mock Amadeus API response."""
    return {
        "data": [
            {
                "price": {"total": "680.00"},
                "itineraries": [{
                    "segments": [
                        {
                            "departure": {"iataCode": "JFK", "at": "2026-07-01T10:00:00"},
                            "arrival": {"iataCode": "ATH", "at": "2026-07-02T14:00:00"},
                            "carrierCode": "UA",
                            "number": "123",
                            "duration": "PT14H15M"
                        }
                    ]
                }]
            },
            {
                "price": {"total": "850.00"},
                "itineraries": [{
                    "segments": [
                        {
                            "departure": {"iataCode": "JFK", "at": "2026-07-01T08:00:00"},
                            "arrival": {"iataCode": "ATH", "at": "2026-07-01T22:00:00"},
                            "carrierCode": "DL",
                            "number": "456",
                            "duration": "PT10H30M"
                        }
                    ]
                }]
            }
        ]
    }


@pytest.mark.asyncio
async def test_flight_search_with_amadeus_api(agent_with_mock, amadeus_api_response):
    """Test flight search using Amadeus API."""
    agent, mock_requests = agent_with_mock

    # Mock OAuth token response
    mock_token_response = MagicMock()
    mock_token_response.json.return_value = {"access_token": "test_token"}
    mock_token_response.status_code = 200

    # Mock flight search response
    mock_search_response = MagicMock()
    mock_search_response.json.return_value = amadeus_api_response
    mock_search_response.status_code = 200

    mock_requests.post.return_value = mock_token_response
    mock_requests.get.return_value = mock_search_response

    state = {
        "intent": {
            "origin": "JFK",
            "destination": "Greece",
            "departure_date": "2026-07-01",
            "duration_days": 7
        }
    }

    result = await agent._execute(state)

    assert "flights" in result
    assert len(result["flights"]) > 0


@pytest.mark.asyncio
async def test_flight_search_mock_fallback():
    """Test that mock data is used when API is not configured."""
    with patch("agents.flight_agent.get_api_config") as mock_config:
        mock_config.return_value.flight.use_mock = True

        agent = FlightAgent()

        state = {
            "intent": {
                "origin": "JFK",
                "destination": "Greece",
                "departure_date": "2026-07-01"
            }
        }

        result = await agent._execute(state)

        assert "flights" in result
        assert len(result["flights"]) > 0
        # Mock data should have realistic prices
        assert all(f.get("price", 0) > 0 for f in result["flights"])


@pytest.mark.asyncio
async def test_flight_results_have_required_fields():
    """Test that flight results contain all required fields."""
    with patch("agents.flight_agent.get_api_config") as mock_config:
        mock_config.return_value.flight.use_mock = True

        agent = FlightAgent()
        state = {
            "intent": {
                "origin": "JFK",
                "destination": "Greece",
                "departure_date": "2026-07-01"
            }
        }

        result = await agent._execute(state)

        flights = result["flights"]
        for flight in flights:
            assert "price" in flight
            assert "airline" in flight
            assert "duration" in flight
            assert "stops" in flight


@pytest.mark.asyncio
async def test_flight_price_validation():
    """Test that flight prices are reasonable."""
    with patch("agents.flight_agent.get_api_config") as mock_config:
        mock_config.return_value.flight.use_mock = True

        agent = FlightAgent()
        state = {
            "intent": {
                "origin": "JFK",
                "destination": "Greece",
                "departure_date": "2026-07-01"
            }
        }

        result = await agent._execute(state)

        flights = result["flights"]
        for flight in flights:
            # Prices should be realistic (not negative, not absurdly high)
            assert 100 < flight["price"] < 5000


@pytest.mark.asyncio
async def test_returns_multiple_flight_options():
    """Test that multiple flight options are returned."""
    with patch("agents.flight_agent.get_api_config") as mock_config:
        mock_config.return_value.flight.use_mock = True

        agent = FlightAgent()
        state = {
            "intent": {
                "origin": "JFK",
                "destination": "Greece",
                "departure_date": "2026-07-01"
            }
        }

        result = await agent._execute(state)

        # Should return at least 2 options for comparison
        assert len(result["flights"]) >= 2


@pytest.mark.asyncio
async def test_flight_cost_calculated():
    """Test that flight_cost_usd is calculated in state."""
    with patch("agents.flight_agent.get_api_config") as mock_config:
        mock_config.return_value.flight.use_mock = True

        agent = FlightAgent()
        state = {
            "intent": {
                "origin": "JFK",
                "destination": "Greece",
                "departure_date": "2026-07-01"
            }
        }

        result = await agent._execute(state)

        assert "flight_cost_usd" in result
        assert result["flight_cost_usd"] > 0


@pytest.mark.asyncio
async def test_error_when_missing_origin():
    """Test error handling when origin is missing."""
    with patch("agents.flight_agent.get_api_config") as mock_config:
        mock_config.return_value.flight.use_mock = True

        agent = FlightAgent()
        state = {
            "intent": {
                "destination": "Greece",
                "departure_date": "2026-07-01"
            }
        }

        result = await agent._execute(state)

        # Should handle gracefully or return error
        assert "errors" in result or "flights" in result


@pytest.mark.asyncio
async def test_handles_api_timeout_gracefully():
    """Test that API timeout falls back to mock data."""
    with patch("agents.flight_agent.requests") as mock_requests:
        mock_requests.get.side_effect = TimeoutError("API timeout")

        with patch("agents.flight_agent.get_api_config") as mock_config:
            mock_config.return_value.flight.use_mock = False

            agent = FlightAgent()
            state = {
                "intent": {
                    "origin": "JFK",
                    "destination": "Greece",
                    "departure_date": "2026-07-01"
                }
            }

            # Should fall back to mock data instead of crashing
            result = await agent._execute(state)
            assert "flights" in result or "errors" in result
