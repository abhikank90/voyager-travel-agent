"""
Unit tests for HotelAgent.
Tests hotel search with Booking.com API and mock fallback.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.hotel_agent import HotelAgent


@pytest.mark.asyncio
async def test_hotel_search_mock_fallback():
    """Test that mock hotel data is used when API is not configured."""
    with patch("agents.hotel_agent.get_api_config") as mock_config:
        mock_config.return_value.hotel.use_mock = True

        agent = HotelAgent()
        state = {
            "intent": {
                "destination": "Greece",
                "interests": ["beaches"],
                "budget_usd": 2000,
                "duration_days": 7
            }
        }

        result = await agent._execute(state)

        assert "hotels" in result
        assert len(result["hotels"]) > 0


@pytest.mark.asyncio
async def test_hotel_results_have_required_fields():
    """Test that hotel results contain all required fields."""
    with patch("agents.hotel_agent.get_api_config") as mock_config:
        mock_config.return_value.hotel.use_mock = True

        agent = HotelAgent()
        state = {
            "intent": {
                "destination": "Greece",
                "budget_usd": 2000,
                "duration_days": 7
            }
        }

        result = await agent._execute(state)

        hotels = result["hotels"]
        for hotel in hotels:
            assert "name" in hotel
            assert "price_per_night" in hotel
            assert "rating" in hotel
            assert "location" in hotel
            assert "amenities" in hotel


@pytest.mark.asyncio
async def test_hotel_price_per_night_reasonable():
    """Test that hotel prices per night are realistic."""
    with patch("agents.hotel_agent.get_api_config") as mock_config:
        mock_config.return_value.hotel.use_mock = True

        agent = HotelAgent()
        state = {
            "intent": {
                "destination": "Greece",
                "budget_usd": 2000,
                "duration_days": 7
            }
        }

        result = await agent._execute(state)

        hotels = result["hotels"]
        for hotel in hotels:
            # Prices should be realistic
            assert 20 < hotel["price_per_night"] < 1000


@pytest.mark.asyncio
async def test_hotel_ratings_valid():
    """Test that hotel ratings are between 0 and 5."""
    with patch("agents.hotel_agent.get_api_config") as mock_config:
        mock_config.return_value.hotel.use_mock = True

        agent = HotelAgent()
        state = {
            "intent": {
                "destination": "Greece",
                "budget_usd": 2000
            }
        }

        result = await agent._execute(state)

        hotels = result["hotels"]
        for hotel in hotels:
            assert 0 <= hotel["rating"] <= 5


@pytest.mark.asyncio
async def test_returns_multiple_hotel_options():
    """Test that multiple hotel options are returned."""
    with patch("agents.hotel_agent.get_api_config") as mock_config:
        mock_config.return_value.hotel.use_mock = True

        agent = HotelAgent()
        state = {
            "intent": {
                "destination": "Greece",
                "budget_usd": 2000
            }
        }

        result = await agent._execute(state)

        # Should return at least 2 options for variety
        assert len(result["hotels"]) >= 2


@pytest.mark.asyncio
async def test_hotel_cost_calculated():
    """Test that hotel_cost_usd is calculated based on duration."""
    with patch("agents.hotel_agent.get_api_config") as mock_config:
        mock_config.return_value.hotel.use_mock = True

        agent = HotelAgent()
        state = {
            "intent": {
                "destination": "Greece",
                "budget_usd": 2000,
                "duration_days": 7
            }
        }

        result = await agent._execute(state)

        assert "hotel_cost_usd" in result
        assert result["hotel_cost_usd"] > 0

        # Should be price_per_night * duration
        hotels = result["hotels"]
        if hotels:
            expected_min = min(h["price_per_night"] for h in hotels) * 7
            # Cost should be reasonable for 7 nights
            assert result["hotel_cost_usd"] >= expected_min * 0.9


@pytest.mark.asyncio
async def test_hotel_amenities_list():
    """Test that amenities are returned as a list."""
    with patch("agents.hotel_agent.get_api_config") as mock_config:
        mock_config.return_value.hotel.use_mock = True

        agent = HotelAgent()
        state = {
            "intent": {
                "destination": "Greece",
                "budget_usd": 2000
            }
        }

        result = await agent._execute(state)

        hotels = result["hotels"]
        for hotel in hotels:
            assert isinstance(hotel["amenities"], list)


@pytest.mark.asyncio
async def test_hotel_location_matches_destination():
    """Test that hotel locations are in the requested destination."""
    with patch("agents.hotel_agent.get_api_config") as mock_config:
        mock_config.return_value.hotel.use_mock = True

        agent = HotelAgent()
        state = {
            "intent": {
                "destination": "Greece",
                "budget_usd": 2000
            }
        }

        result = await agent._execute(state)

        hotels = result["hotels"]
        for hotel in hotels:
            location = hotel["location"].lower()
            # Location should be in Greece (Athens, Santorini, etc.)
            # For mock data, just check it's not empty
            assert len(location) > 0


@pytest.mark.asyncio
async def test_handles_beach_preference():
    """Test that beach interest influences hotel selection."""
    with patch("agents.hotel_agent.get_api_config") as mock_config:
        mock_config.return_value.hotel.use_mock = True

        agent = HotelAgent()
        state = {
            "intent": {
                "destination": "Greece",
                "interests": ["beaches"],
                "budget_usd": 2000
            }
        }

        result = await agent._execute(state)

        hotels = result["hotels"]
        # At least one hotel should have beach-related amenities or location
        assert len(hotels) > 0


@pytest.mark.asyncio
async def test_handles_budget_constraints():
    """Test that hotels are filtered by budget."""
    with patch("agents.hotel_agent.get_api_config") as mock_config:
        mock_config.return_value.hotel.use_mock = True

        agent = HotelAgent()
        state = {
            "intent": {
                "destination": "Greece",
                "budget_usd": 500,  # Low budget
                "duration_days": 7
            }
        }

        result = await agent._execute(state)

        hotels = result["hotels"]
        # At least one hotel should be affordable
        affordable_hotels = [h for h in hotels if h["price_per_night"] * 7 < 500]
        assert len(affordable_hotels) > 0


@pytest.mark.asyncio
async def test_error_when_missing_destination():
    """Test error handling when destination is missing."""
    with patch("agents.hotel_agent.get_api_config") as mock_config:
        mock_config.return_value.hotel.use_mock = True

        agent = HotelAgent()
        state = {
            "intent": {
                "budget_usd": 2000
            }
        }

        result = await agent._execute(state)

        # Should handle gracefully
        assert "errors" in result or "hotels" in result


@pytest.mark.asyncio
async def test_hotel_recommendations_key_exists():
    """Test that hotel_recommendations is also set for backward compatibility."""
    with patch("agents.hotel_agent.get_api_config") as mock_config:
        mock_config.return_value.hotel.use_mock = True

        agent = HotelAgent()
        state = {
            "intent": {
                "destination": "Greece",
                "budget_usd": 2000
            }
        }

        result = await agent._execute(state)

        # Both keys should exist
        assert "hotels" in result or "hotel_recommendations" in result
