from unittest.mock import AsyncMock, patch

import pytest

from agents.intent_parser import IntentParserAgent


@pytest.fixture
def agent():
    with patch("agents.intent_parser.ChatAnthropic"):
        return IntentParserAgent()


@pytest.mark.asyncio
async def test_intent_parser_extracts_destination(agent):
    mock_intent = {
        "destination": "Greece",
        "budget_usd": 2000,
        "interests": ["beaches", "local food"],
        "group_size": 1,
        "flexibility": "moderate",
        "raw_query": "vacation in Greece under $2000",
        "travel_month": "July",
        "travel_year": 2026,
    }

    with patch.object(agent, "chain") as mock_chain:
        mock_chain.ainvoke = AsyncMock(return_value=type("R", (), {"model_dump": lambda self: mock_intent})())
        result = await agent._execute({"user_query": "vacation in Greece under $2000"})

    assert result["intent"]["destination"] == "Greece"
    assert result["intent"]["budget_usd"] == 2000
    assert "beaches" in result["intent"]["interests"]


@pytest.mark.asyncio
async def test_intent_parser_missing_query(agent):
    result = await agent._execute({})
    assert "errors" in result
