"""Unit tests for VisaSafetyAgent.

The actual agent uses DuckDuckGoSearchRun (via self.search) and builds
the LLM chain inline in _execute as `self.prompt | self.llm`. These tests
mock both so no real API calls are made.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.visa_safety_agent import VisaSafetyAgent

VALID_VISA_JSON = json.dumps({
    "visa_required": False,
    "visa_type": "Schengen — 90 days visa-free",
    "visa_on_arrival": False,
    "safety_level": 1,
    "safety_summary": "Greece is very safe for tourists.",
    "tips": ["Keep passport copies"],
    "emergency_contacts": {"police": "100", "ambulance": "166"},
    "health_requirements": ["Travel insurance recommended"],
})


def _make_agent(llm_response: str = VALID_VISA_JSON, search_raises: bool = False):
    """Build a VisaSafetyAgent with all external deps mocked out."""
    with patch("agents.visa_safety_agent.ChatAnthropic"), \
         patch("agents.visa_safety_agent.DuckDuckGoSearchRun") as mock_search_cls:
        if search_raises:
            mock_search_cls.side_effect = Exception("Search unavailable")
        else:
            mock_search = MagicMock()
            mock_search.run.return_value = "Greece is Schengen. No visa for US citizens."
            mock_search_cls.return_value = mock_search
        agent = VisaSafetyAgent()

    # Replace prompt so `self.prompt | self.llm` → mock_chain
    mock_response = MagicMock()
    mock_response.content = llm_response
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_response)
    mock_prompt = MagicMock()
    mock_prompt.__or__ = MagicMock(return_value=mock_chain)
    agent.prompt = mock_prompt
    agent._test_chain = mock_chain
    return agent


INTENT_GREECE = {"destination": "Greece", "origin_country": "USA"}


# ── Output contract ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_returns_visa_safety_key():
    agent = _make_agent()
    result = await agent._execute({"intent": INTENT_GREECE})
    assert "visa_safety" in result


@pytest.mark.asyncio
async def test_visa_required_field_is_bool():
    agent = _make_agent()
    result = await agent._execute({"intent": INTENT_GREECE})
    info = result["visa_safety"]
    assert "visa_required" in info
    assert isinstance(info["visa_required"], bool)


@pytest.mark.asyncio
async def test_safety_level_present():
    agent = _make_agent()
    result = await agent._execute({"intent": INTENT_GREECE})
    info = result["visa_safety"]
    assert "safety_level" in info


@pytest.mark.asyncio
async def test_llm_chain_is_called():
    agent = _make_agent()
    await agent._execute({"intent": INTENT_GREECE})
    agent._test_chain.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_destination_passed_to_chain():
    agent = _make_agent()
    await agent._execute({"intent": INTENT_GREECE})
    call_kwargs = agent._test_chain.ainvoke.call_args[0][0]
    assert call_kwargs["destination"] == "Greece"


# ── Edge cases ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_missing_origin_country_still_works():
    """Agent should not crash when origin_country is absent."""
    agent = _make_agent()
    result = await agent._execute({"intent": {"destination": "Greece"}})
    assert "visa_safety" in result


@pytest.mark.asyncio
async def test_invalid_llm_json_falls_back():
    """When Claude returns unparseable JSON, _fallback is used."""
    agent = _make_agent(llm_response="not valid json at all")
    result = await agent._execute({"intent": INTENT_GREECE})
    assert "visa_safety" in result
    # Fallback for Greece always returns visa_required=False
    assert result["visa_safety"].get("visa_required") is False


@pytest.mark.asyncio
async def test_search_failure_uses_fallback():
    """DuckDuckGoSearchRun failure (at construction) is caught — agent uses self.search=None."""
    agent = _make_agent(search_raises=True)
    result = await agent._execute({"intent": INTENT_GREECE})
    assert "visa_safety" in result


@pytest.mark.asyncio
async def test_missing_destination_returns_gracefully():
    """Empty destination should not raise; may return errors or empty visa_safety."""
    agent = _make_agent()
    result = await agent._execute({"intent": {}})
    assert "visa_safety" in result or "errors" in result
