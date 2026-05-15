import pytest
from agents.budget_guardrail import BudgetGuardrailAgent


@pytest.fixture
def agent():
    return BudgetGuardrailAgent()


@pytest.mark.asyncio
async def test_within_budget(agent):
    state = {
        "intent": {"budget_usd": 2000},
        "flight_cost_usd": 700,
        "hotel_cost_usd": 800,
        "budget_retry_count": 0,
    }
    result = await agent._execute(state)
    assert result["budget_ok"] is True
    assert result["budget_loop_back"] is False
    assert result["budget_breakdown"]["total_usd"] <= 2000


@pytest.mark.asyncio
async def test_over_budget_triggers_retry(agent):
    state = {
        "intent": {"budget_usd": 1000},
        "flight_cost_usd": 900,
        "hotel_cost_usd": 800,
        "budget_retry_count": 0,
    }
    result = await agent._execute(state)
    assert result["budget_ok"] is False
    assert result["budget_loop_back"] is True
    assert result["budget_retry_count"] == 1


@pytest.mark.asyncio
async def test_max_retries_stops_loop(agent):
    state = {
        "intent": {"budget_usd": 1000},
        "flight_cost_usd": 900,
        "hotel_cost_usd": 800,
        "budget_retry_count": 2,
    }
    result = await agent._execute(state)
    assert result["budget_loop_back"] is False
