"""Unit tests for HotelAgent — tested against actual mock data (no BOOKING_API_KEY)."""

import pytest

from agents.hotel_agent import HotelAgent, _mock_hotel_data

INTENT_BASE = {
    "destination": "Greece",
    "budget_usd": 2000,
    "duration_days": 7,
    "travel_year": 2026,
    "group_size": 1,
}


@pytest.mark.asyncio
async def test_execute_returns_required_state_keys():
    agent = HotelAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    assert "hotels" in result
    assert "selected_hotel" in result
    assert "hotel_cost_usd" in result


@pytest.mark.asyncio
async def test_hotels_have_correct_field_names():
    agent = HotelAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    for hotel in result["hotels"]:
        assert "name" in hotel
        assert "price_per_night_usd" in hotel
        assert "total_usd" in hotel
        assert "rating" in hotel
        assert "amenities" in hotel
        assert "location" in hotel


@pytest.mark.asyncio
async def test_total_usd_uses_actual_duration():
    agent = HotelAgent()
    result = await agent._execute({"intent": {**INTENT_BASE, "duration_days": 7}})
    for hotel in result["hotels"]:
        expected = hotel["price_per_night_usd"] * 7
        assert hotel["total_usd"] == expected, (
            f"{hotel['name']}: total_usd={hotel['total_usd']} ≠ {hotel['price_per_night_usd']}×7"
        )


@pytest.mark.asyncio
async def test_hotel_cost_usd_matches_selected_hotel():
    agent = HotelAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    assert result["hotel_cost_usd"] == result["selected_hotel"]["total_usd"]


@pytest.mark.asyncio
async def test_returns_multiple_hotel_options():
    agent = HotelAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    assert len(result["hotels"]) >= 2


@pytest.mark.asyncio
async def test_hotel_ratings_in_valid_range():
    agent = HotelAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    for hotel in result["hotels"]:
        assert 0 <= hotel["rating"] <= 5


@pytest.mark.asyncio
async def test_hotel_prices_realistic():
    agent = HotelAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    for hotel in result["hotels"]:
        assert 20 < hotel["price_per_night_usd"] < 1000


@pytest.mark.asyncio
async def test_amenities_are_lists():
    agent = HotelAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    for hotel in result["hotels"]:
        assert isinstance(hotel["amenities"], list)


@pytest.mark.asyncio
async def test_location_hint_selects_matching_hotel():
    """After hub sends a location constraint, HotelAgent should prefer a hotel
    whose location matches the hint over a cheaper one that doesn't."""
    agent = HotelAgent()
    state = {
        "intent": INTENT_BASE,
        "collaboration_round": 2,
        "agent_messages": [
            {
                "to_agent": "hotel",
                "message_type": "constraint",
                "data": {"activity_locations": ["Oia, Santorini"]},
                "round": 1,
            }
        ],
    }
    result = await agent._execute(state)
    assert result["selected_hotel"]["location"] == "Oia, Santorini"


@pytest.mark.asyncio
async def test_no_location_hint_selects_first_affordable():
    agent = HotelAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    hotels = result["hotels"]
    hotel_budget = INTENT_BASE["budget_usd"] * 0.45
    affordable = [h for h in hotels if h["total_usd"] <= hotel_budget]
    assert result["selected_hotel"] == affordable[0]


@pytest.mark.asyncio
async def test_missing_intent_returns_error():
    agent = HotelAgent()
    result = await agent._execute({})
    assert "errors" in result


def test_mock_hotel_data_location_hint_inserts_at_front():
    data = _mock_hotel_data("Greece", "2026-07-01", "2026-07-08", 1, 7, "Oia, Santorini")
    assert data["hotels"][0]["location"] == "Oia, Santorini"


def test_mock_hotel_data_no_hint_returns_base_hotels():
    data = _mock_hotel_data("Greece", "2026-07-01", "2026-07-08", 1, 7)
    assert len(data["hotels"]) == 2
