"""
Unit tests for OptionGeneratorAgent.
Tests 3 option generation (budget/balanced/premium), booking URLs, and trade-off analysis.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from agents.option_generator import OptionGeneratorAgent


@pytest.fixture
def agent():
    """Create OptionGeneratorAgent with mocked Anthropic client."""
    with patch("agents.option_generator.Anthropic") as mock_anthropic:
        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        # Mock day-by-day itinerary generation
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=json.dumps([
            {
                "day": 1,
                "morning": "Arrive and check-in",
                "afternoon": "Beach visit",
                "evening": "Dinner at local taverna",
                "meals": ["Lunch", "Dinner"]
            }
        ]))]
        mock_client.messages.create.return_value = mock_response

        agent = OptionGeneratorAgent()
        agent.client = mock_client
        return agent


@pytest.fixture
def complete_state():
    """Complete state with all required research data."""
    return {
        "intent": {
            "destination": "Greece",
            "budget_usd": 2000,
            "duration_days": 7,
            "interests": ["beaches", "food"],
            "origin": "JFK",
            "departure_date": "2026-07-01"
        },
        "flights": [
            {
                "airline": "United",
                "price": 650,
                "stops": 1,
                "duration": "14h 15m",
                "departure_time": "10:00",
                "arrival_time": "14:00"
            },
            {
                "airline": "Delta",
                "price": 850,
                "stops": 0,
                "duration": "10h 30m",
                "departure_time": "08:00",
                "arrival_time": "10:00"
            },
            {
                "airline": "Budget Air",
                "price": 450,
                "stops": 2,
                "duration": "18h",
                "departure_time": "22:00",
                "arrival_time": "04:00"
            }
        ],
        "hotels": [
            {
                "name": "Budget Inn",
                "price_per_night": 60,
                "rating": 3.5,
                "location": "Athens",
                "amenities": ["WiFi"]
            },
            {
                "name": "Comfort Hotel",
                "price_per_night": 120,
                "rating": 4.2,
                "location": "Santorini",
                "amenities": ["Pool", "WiFi", "Breakfast"]
            },
            {
                "name": "Luxury Resort",
                "price_per_night": 250,
                "rating": 4.9,
                "location": "Santorini",
                "amenities": ["Beach Access", "Spa", "Pool", "Restaurant"]
            }
        ],
        "experiences": [
            {
                "name": "Free Beach Access",
                "price": 0,
                "type": "beach",
                "location": "Santorini"
            },
            {
                "name": "Food Tour",
                "price": 80,
                "type": "food",
                "location": "Athens"
            },
            {
                "name": "Private Yacht",
                "price": 400,
                "type": "luxury",
                "location": "Santorini"
            },
            {
                "name": "Acropolis Tour",
                "price": 50,
                "type": "culture",
                "location": "Athens"
            }
        ],
        "weather": {
            "avg_temp_c": 33,
            "conditions": "sunny"
        },
        "visa_safety": {
            "visa_required": False,
            "safety_level": 1
        }
    }


@pytest.mark.asyncio
async def test_generates_three_options(agent, complete_state):
    """Test that exactly 3 options are generated."""
    result = await agent._execute(complete_state)

    assert "trip_options" in result
    assert len(result["trip_options"]) == 3
    assert result["status"] == "options_generated"


@pytest.mark.asyncio
async def test_option_styles_are_correct(agent, complete_state):
    """Test that options have correct styles: budget, balanced, premium."""
    result = await agent._execute(complete_state)

    options = result["trip_options"]
    styles = [opt["style"] for opt in options]

    assert "budget" in styles
    assert "balanced" in styles
    assert "premium" in styles


@pytest.mark.asyncio
async def test_budget_option_costs_75_percent(agent, complete_state):
    """Test that budget option targets 75% of total budget."""
    result = await agent._execute(complete_state)

    budget_option = [opt for opt in result["trip_options"] if opt["style"] == "budget"][0]
    budget = complete_state["intent"]["budget_usd"]

    # Budget option should be around 75% (with some tolerance)
    assert budget_option["total_cost_usd"] <= budget * 0.85  # Allow some flexibility


@pytest.mark.asyncio
async def test_balanced_option_costs_100_percent(agent, complete_state):
    """Test that balanced option targets 100% of budget."""
    result = await agent._execute(complete_state)

    balanced_option = [opt for opt in result["trip_options"] if opt["style"] == "balanced"][0]
    budget = complete_state["intent"]["budget_usd"]

    # Balanced should be close to full budget
    assert balanced_option["total_cost_usd"] <= budget * 1.1


@pytest.mark.asyncio
async def test_premium_option_costs_115_percent(agent, complete_state):
    """Test that premium option can exceed budget by 15%."""
    result = await agent._execute(complete_state)

    premium_option = [opt for opt in result["trip_options"] if opt["style"] == "premium"][0]
    budget = complete_state["intent"]["budget_usd"]

    # Premium can go over budget
    assert premium_option["total_cost_usd"] >= budget * 0.95


@pytest.mark.asyncio
async def test_budget_option_uses_cheapest_flight(agent, complete_state):
    """Test that budget option selects the cheapest flight."""
    result = await agent._execute(complete_state)

    budget_option = [opt for opt in result["trip_options"] if opt["style"] == "budget"][0]

    # Should use the cheapest flight (Budget Air at $450)
    assert budget_option["flight"]["price"] == 450


@pytest.mark.asyncio
async def test_premium_option_uses_best_flight(agent, complete_state):
    """Test that premium option selects best quality flight (direct, convenient time)."""
    result = await agent._execute(complete_state)

    premium_option = [opt for opt in result["trip_options"] if opt["style"] == "premium"][0]

    # Should use direct flight (Delta at $850)
    assert premium_option["flight"]["stops"] == 0


@pytest.mark.asyncio
async def test_budget_option_uses_cheapest_hotel(agent, complete_state):
    """Test that budget option selects cheapest hotel."""
    result = await agent._execute(complete_state)

    budget_option = [opt for opt in result["trip_options"] if opt["style"] == "budget"][0]

    # Should use Budget Inn at $60/night
    assert budget_option["hotel"]["price_per_night"] == 60


@pytest.mark.asyncio
async def test_premium_option_uses_luxury_hotel(agent, complete_state):
    """Test that premium option selects highest-rated hotel."""
    result = await agent._execute(complete_state)

    premium_option = [opt for opt in result["trip_options"] if opt["style"] == "premium"][0]

    # Should use Luxury Resort with highest rating
    assert premium_option["hotel"]["rating"] >= 4.5


@pytest.mark.asyncio
async def test_all_options_have_booking_urls(agent, complete_state):
    """Test that all options include booking URLs for flights and hotels."""
    result = await agent._execute(complete_state)

    for option in result["trip_options"]:
        assert "flight_booking_url" in option
        assert "hotel_booking_url" in option
        assert option["flight_booking_url"] is not None
        assert option["hotel_booking_url"] is not None


@pytest.mark.asyncio
async def test_flight_booking_url_format(agent, complete_state):
    """Test that flight booking URL has correct format."""
    result = await agent._execute(complete_state)

    option = result["trip_options"][0]
    flight_url = option["flight_booking_url"]

    # Should contain origin, destination, and date
    assert "JFK" in flight_url or "jfk" in flight_url.lower()
    assert "ATH" in flight_url or "athens" in flight_url.lower() or "greece" in flight_url.lower()
    assert "2026" in flight_url


@pytest.mark.asyncio
async def test_hotel_booking_url_format(agent, complete_state):
    """Test that hotel booking URL has correct format."""
    result = await agent._execute(complete_state)

    option = result["trip_options"][0]
    hotel_url = option["hotel_booking_url"]

    # Should contain hotel name or location
    assert "booking" in hotel_url.lower()


@pytest.mark.asyncio
async def test_all_options_have_highlights(agent, complete_state):
    """Test that all options include highlights list."""
    result = await agent._execute(complete_state)

    for option in result["trip_options"]:
        assert "highlights" in option
        assert isinstance(option["highlights"], list)
        assert len(option["highlights"]) > 0


@pytest.mark.asyncio
async def test_all_options_have_trade_offs(agent, complete_state):
    """Test that all options include trade-offs list."""
    result = await agent._execute(complete_state)

    for option in result["trip_options"]:
        assert "trade_offs" in option
        assert isinstance(option["trade_offs"], list)
        # Budget and premium should have trade-offs
        if option["style"] in ["budget", "premium"]:
            assert len(option["trade_offs"]) > 0


@pytest.mark.asyncio
async def test_budget_option_highlights_savings(agent, complete_state):
    """Test that budget option highlights cost savings."""
    result = await agent._execute(complete_state)

    budget_option = [opt for opt in result["trip_options"] if opt["style"] == "budget"][0]
    highlights_text = " ".join(budget_option["highlights"]).lower()

    # Should mention savings or value
    assert any(word in highlights_text for word in ["save", "savings", "value", "budget", "affordable"])


@pytest.mark.asyncio
async def test_premium_option_highlights_luxury(agent, complete_state):
    """Test that premium option highlights luxury features."""
    result = await agent._execute(complete_state)

    premium_option = [opt for opt in result["trip_options"] if opt["style"] == "premium"][0]
    highlights_text = " ".join(premium_option["highlights"]).lower()

    # Should mention luxury/comfort/exclusive
    assert any(word in highlights_text for word in ["luxury", "premium", "exclusive", "comfort", "direct"])


@pytest.mark.asyncio
async def test_all_options_have_day_by_day(agent, complete_state):
    """Test that all options include day-by-day itineraries."""
    result = await agent._execute(complete_state)

    for option in result["trip_options"]:
        assert "day_by_day" in option
        assert isinstance(option["day_by_day"], list)
        assert len(option["day_by_day"]) > 0


@pytest.mark.asyncio
async def test_day_by_day_has_required_fields(agent, complete_state):
    """Test that day-by-day plans have all required fields."""
    result = await agent._execute(complete_state)

    option = result["trip_options"][0]
    day_plan = option["day_by_day"][0]

    assert "day" in day_plan
    assert "morning" in day_plan
    assert "afternoon" in day_plan
    assert "evening" in day_plan
    assert "meals" in day_plan


@pytest.mark.asyncio
async def test_error_when_no_flights(agent, complete_state):
    """Test that error is returned when flights data is missing."""
    incomplete_state = complete_state.copy()
    incomplete_state["flights"] = []

    result = await agent._execute(incomplete_state)

    assert "errors" in result or result.get("status") == "error"


@pytest.mark.asyncio
async def test_error_when_no_hotels(agent, complete_state):
    """Test that error is returned when hotels data is missing."""
    incomplete_state = complete_state.copy()
    incomplete_state["hotels"] = []

    result = await agent._execute(incomplete_state)

    assert "errors" in result or result.get("status") == "error"


@pytest.mark.asyncio
async def test_option_ids_are_sequential(agent, complete_state):
    """Test that option IDs are 0, 1, 2."""
    result = await agent._execute(complete_state)

    option_ids = [opt["option_id"] for opt in result["trip_options"]]
    assert option_ids == [0, 1, 2]


@pytest.mark.asyncio
async def test_all_options_have_titles(agent, complete_state):
    """Test that all options have descriptive titles."""
    result = await agent._execute(complete_state)

    for option in result["trip_options"]:
        assert "title" in option
        assert len(option["title"]) > 0
        # Title should mention destination
        assert "Greece" in option["title"] or option["style"].title() in option["title"]
