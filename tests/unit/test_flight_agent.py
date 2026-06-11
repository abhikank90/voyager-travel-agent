"""Unit tests for FlightAgent — tested against actual mock data (no AMADEUS keys)."""

import pytest

from agents.flight_agent import FlightAgent, _arrival_hour, _mock_flight_data

INTENT_BASE = {
    "destination": "Greece",
    "origin": "New York",
    "budget_usd": 2000,
    "travel_year": 2026,
    "travel_month": "July",
    "group_size": 1,
}


@pytest.mark.asyncio
async def test_execute_returns_required_state_keys():
    agent = FlightAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    assert "flights" in result
    assert "selected_flight" in result
    assert "flight_cost_usd" in result


@pytest.mark.asyncio
async def test_flights_have_correct_field_names():
    agent = FlightAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    for flight in result["flights"]:
        assert "price_usd" in flight
        assert "airline" in flight
        assert "departure" in flight
        assert "arrival" in flight
        assert "stops" in flight
        assert "duration" in flight


@pytest.mark.asyncio
async def test_flight_cost_usd_matches_selected_flight():
    agent = FlightAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    assert result["flight_cost_usd"] == result["selected_flight"]["price_usd"]


@pytest.mark.asyncio
async def test_returns_multiple_flight_options():
    agent = FlightAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    assert len(result["flights"]) >= 2


@pytest.mark.asyncio
async def test_prices_realistic():
    agent = FlightAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    for f in result["flights"]:
        assert 100 < f["price_usd"] < 5000


@pytest.mark.asyncio
async def test_selects_cheapest_by_default():
    agent = FlightAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    cheapest = min(result["flights"], key=lambda f: f["price_usd"])
    assert result["selected_flight"]["price_usd"] == cheapest["price_usd"]


@pytest.mark.asyncio
async def test_preferred_arrival_constraint_selects_on_time_flight():
    """After hub sends a timing constraint, FlightAgent should prefer the flight
    arriving before the threshold even if it costs more."""
    agent = FlightAgent()
    state = {
        "intent": INTENT_BASE,
        "collaboration_round": 2,
        "agent_messages": [
            {
                "to_agent": "flight",
                "message_type": "insight",
                "data": {"preferred_arrival": "before 14:00"},
                "round": 1,
            }
        ],
    }
    result = await agent._execute(state)
    arrival_h = _arrival_hour(result["selected_flight"]["arrival"])
    assert arrival_h < 14, f"Expected arrival before 14:00, got hour {arrival_h}"


@pytest.mark.asyncio
async def test_missing_intent_returns_error():
    agent = FlightAgent()
    result = await agent._execute({})
    assert "errors" in result


def test_mock_adds_well_timed_option_when_constrained():
    data = _mock_flight_data("JFK", "ATH", "2026-07-01", "2026-07-14", 1, preferred_arrival_hour=14)
    arrivals = [_arrival_hour(f["arrival"]) for f in data["flights"]]
    assert any(h < 14 for h in arrivals), "Expected at least one on-time option in constrained mock"


def test_mock_no_constraint_returns_two_options():
    data = _mock_flight_data("JFK", "ATH", "2026-07-01", "2026-07-14", 1)
    assert len(data["flights"]) == 2


def test_arrival_hour_parses_iso():
    assert _arrival_hour("2026-07-01T13:00:00") == 13
    assert _arrival_hour("2026-07-01T22:30:00") == 22


def test_arrival_hour_returns_25_on_bad_input():
    assert _arrival_hour("") == 25
    assert _arrival_hour("not-a-date") == 25
