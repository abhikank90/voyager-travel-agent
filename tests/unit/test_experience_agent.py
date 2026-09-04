"""Unit tests for ExperienceAgent.

Two test modes:
  - Mock-LLM tests: patch ChatAnthropic so Claude returns controlled JSON.
  - Fallback tests: let the chain fail (ci-test-key is invalid) and verify
    _fallback_experiences satisfies the contract. Used for lightweight checks
    that don't need full control over the response content.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.experience_agent import ExperienceAgent

VALID_EXPERIENCES_JSON = json.dumps([
    {"name": "Sunset in Oia", "cost_usd": 0, "category": "culture",
     "location": "Oia, Santorini", "best_time_of_day": "evening",
     "description": "Iconic Santorini sunset viewpoint"},
    {"name": "Caldera Boat Tour", "cost_usd": 80, "category": "outdoor",
     "location": "Fira center", "best_time_of_day": "morning",
     "description": "Sail around the volcanic caldera"},
    {"name": "Greek Taverna Dinner", "cost_usd": 40, "category": "food",
     "location": "Oia village", "best_time_of_day": "evening",
     "description": "Traditional mezze at a cliffside restaurant"},
])

INTENT_BASE = {"destination": "Greece", "interests": ["beaches", "food"], "budget_usd": 2000, "duration_days": 7}


def _make_agent_with_mock_llm(response_content: str = VALID_EXPERIENCES_JSON):
    """Create an ExperienceAgent whose LLM chain returns controlled JSON.

    The chain is built as `self.prompt | self.llm` inside _execute, so `a | b`
    calls `a.__or__(b)` — i.e. prompt's __or__, not llm's.  We replace
    agent.prompt with a mock whose __or__ returns mock_chain so that
    `chain = self.prompt | self.llm` gives us the controllable mock_chain.
    """
    with patch("agents.experience_agent.ChatAnthropic"):
        agent = ExperienceAgent()

    mock_response = MagicMock()
    mock_response.content = response_content
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_response)

    mock_prompt = MagicMock()
    mock_prompt.__or__ = MagicMock(return_value=mock_chain)
    agent.prompt = mock_prompt
    agent._test_chain = mock_chain
    return agent


@pytest.mark.asyncio
async def test_returns_experiences_key():
    agent = _make_agent_with_mock_llm()
    result = await agent._execute({"intent": INTENT_BASE})
    assert "experiences" in result
    assert len(result["experiences"]) > 0


@pytest.mark.asyncio
async def test_experiences_have_correct_fields():
    """Actual field names: cost_usd and category (not price and type)."""
    agent = _make_agent_with_mock_llm()
    result = await agent._execute({"intent": INTENT_BASE})
    for exp in result["experiences"]:
        assert "name" in exp
        assert "cost_usd" in exp
        assert "category" in exp
        assert "location" in exp


@pytest.mark.asyncio
async def test_claude_chain_is_called():
    agent = _make_agent_with_mock_llm()
    await agent._execute({"intent": INTENT_BASE})
    agent._test_chain.ainvoke.assert_called_once()


@pytest.mark.asyncio
async def test_destination_passed_to_chain():
    agent = _make_agent_with_mock_llm()
    await agent._execute({"intent": INTENT_BASE})
    call_kwargs = agent._test_chain.ainvoke.call_args[0][0]
    assert call_kwargs["destination"] == "Greece"


@pytest.mark.asyncio
async def test_weather_constraint_added_to_prompt():
    """When hub sends a weather constraint, location_focus must be non-empty."""
    agent = _make_agent_with_mock_llm()
    state = {
        "intent": INTENT_BASE,
        "collaboration_round": 2,
        "agent_messages": [
            {
                "to_agent": "experience",
                "message_type": "constraint",
                "data": {"suggested_activity_times": ["morning", "evening"]},
                "round": 1,
            }
        ],
    }
    await agent._execute(state)
    call_kwargs = agent._test_chain.ainvoke.call_args[0][0]
    assert call_kwargs["location_focus"] != "", "Expected non-empty location_focus for weather constraint"


@pytest.mark.asyncio
async def test_no_constraint_has_empty_location_focus():
    agent = _make_agent_with_mock_llm()
    await agent._execute({"intent": INTENT_BASE})
    call_kwargs = agent._test_chain.ainvoke.call_args[0][0]
    assert call_kwargs["location_focus"] == ""


@pytest.mark.asyncio
async def test_fallback_used_when_claude_returns_invalid_json():
    agent = _make_agent_with_mock_llm(response_content="not json at all")
    result = await agent._execute({"intent": INTENT_BASE})
    assert "experiences" in result
    assert len(result["experiences"]) > 0


@pytest.mark.asyncio
async def test_fallback_experiences_have_required_fields():
    agent = _make_agent_with_mock_llm(response_content="bad json")
    result = await agent._execute({"intent": INTENT_BASE})
    for exp in result["experiences"]:
        assert "name" in exp
        assert "cost_usd" in exp
        assert "category" in exp
        assert "location" in exp


@pytest.mark.asyncio
async def test_missing_intent_returns_error():
    with patch("agents.experience_agent.ChatAnthropic"):
        agent = ExperienceAgent()
    result = await agent._execute({})
    assert "errors" in result


# ── Geocoding (centroid producer) ────────────────────────────────────────────

class _FakeGeoResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class _FakeGeoClient:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def get(self, url, *a, **k):
        q = (k.get("params") or {}).get("q", "")
        if "Oia" in q:
            return _FakeGeoResponse([{"lat": 36.46, "lon": 25.37, "name": "Oia"}])
        return _FakeGeoResponse([])


@pytest.mark.asyncio
async def test_geocode_attaches_coordinates(monkeypatch):
    agent = ExperienceAgent()
    monkeypatch.setenv("OPENWEATHER_API_KEY", "test-key")
    monkeypatch.setattr("agents.experience_agent.httpx.AsyncClient", _FakeGeoClient)

    exps = [
        {"name": "Oia Walk", "location": "Oia, Santorini"},
        {"name": "Unknown", "location": "nowhere"},
        {"name": "No Loc", "location": ""},
    ]
    await agent._geocode_experiences(exps)

    assert exps[0]["latitude"] == 36.46
    assert exps[0]["longitude"] == 25.37
    assert "latitude" not in exps[1]
    assert "latitude" not in exps[2]


@pytest.mark.asyncio
async def test_geocode_skips_without_api_key(monkeypatch):
    """Without OPENWEATHER_API_KEY the geocoder must no-op (no network, no crash)
    so mock/CI paths stay fully offline."""
    agent = ExperienceAgent()
    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)

    class _Boom:
        def __init__(self, *a, **k):
            raise AssertionError("should not construct client without key")

    monkeypatch.setattr("agents.experience_agent.httpx.AsyncClient", _Boom)
    exps = [{"name": "Oia", "location": "Oia, Santorini"}]
    await agent._geocode_experiences(exps)
    assert "latitude" not in exps[0]
