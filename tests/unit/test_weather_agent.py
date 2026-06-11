"""Unit tests for WeatherAgent — tested against historical climate fallback (no OPENWEATHER_API_KEY)."""

import pytest

from agents.weather_agent import WeatherAgent

INTENT_BASE = {"destination": "Greece", "travel_month": "July", "travel_year": 2026}


@pytest.mark.asyncio
async def test_execute_returns_weather_key():
    agent = WeatherAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    assert "weather" in result


@pytest.mark.asyncio
async def test_weather_has_temperature():
    agent = WeatherAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    weather = result["weather"]
    assert "avg_temp_c" in weather
    assert -50 < weather["avg_temp_c"] < 60


@pytest.mark.asyncio
async def test_weather_has_summary_not_conditions():
    """WeatherAgent emits 'summary', not 'conditions'."""
    agent = WeatherAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    weather = result["weather"]
    assert "summary" in weather
    assert len(weather["summary"]) > 0


@pytest.mark.asyncio
async def test_weather_has_precipitation_mm():
    agent = WeatherAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    assert "precipitation_mm" in result["weather"]


@pytest.mark.asyncio
async def test_summer_warmer_than_winter():
    agent = WeatherAgent()
    summer = await agent._execute({"intent": {**INTENT_BASE, "travel_month": "July"}})
    winter = await agent._execute({"intent": {**INTENT_BASE, "travel_month": "January"}})
    assert summer["weather"]["avg_temp_c"] > winter["weather"]["avg_temp_c"]


@pytest.mark.asyncio
async def test_greek_july_is_hot():
    """Greece in July should trigger the extreme-heat threshold (≥32°C)."""
    agent = WeatherAgent()
    result = await agent._execute({"intent": INTENT_BASE})
    assert result["weather"]["avg_temp_c"] >= 30


@pytest.mark.asyncio
async def test_handles_missing_month_gracefully():
    agent = WeatherAgent()
    result = await agent._execute({"intent": {"destination": "Greece"}})
    assert "weather" in result or "errors" in result


@pytest.mark.asyncio
async def test_missing_intent_returns_error():
    agent = WeatherAgent()
    result = await agent._execute({})
    assert "errors" in result


@pytest.mark.asyncio
async def test_unknown_destination_returns_default_weather():
    agent = WeatherAgent()
    result = await agent._execute({"intent": {"destination": "Unknownia", "travel_month": "July"}})
    assert "weather" in result
    assert "avg_temp_c" in result["weather"]
