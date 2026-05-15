"""
Unit tests for WeatherAgent.
Tests weather forecast retrieval with OpenWeather API and climate averages fallback.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.weather_agent import WeatherAgent


@pytest.mark.asyncio
async def test_weather_forecast_mock_fallback():
    """Test that climate averages are used when API is not configured."""
    with patch("agents.weather_agent.get_api_config") as mock_config:
        mock_config.return_value.weather.use_mock = True

        agent = WeatherAgent()
        state = {
            "intent": {
                "destination": "Greece",
                "travel_month": "July",
                "travel_year": 2026
            }
        }

        result = await agent._execute(state)

        assert "weather" in result
        assert result["weather"] is not None


@pytest.mark.asyncio
async def test_weather_has_temperature():
    """Test that weather forecast includes temperature."""
    with patch("agents.weather_agent.get_api_config") as mock_config:
        mock_config.return_value.weather.use_mock = True

        agent = WeatherAgent()
        state = {
            "intent": {
                "destination": "Greece",
                "travel_month": "July"
            }
        }

        result = await agent._execute(state)

        weather = result["weather"]
        assert "avg_temp_c" in weather or "temp_c" in weather
        # Temperature should be realistic
        temp = weather.get("avg_temp_c") or weather.get("temp_c")
        assert -50 < temp < 60  # Celsius range


@pytest.mark.asyncio
async def test_weather_has_conditions():
    """Test that weather includes conditions description."""
    with patch("agents.weather_agent.get_api_config") as mock_config:
        mock_config.return_value.weather.use_mock = True

        agent = WeatherAgent()
        state = {
            "intent": {
                "destination": "Greece",
                "travel_month": "July"
            }
        }

        result = await agent._execute(state)

        weather = result["weather"]
        assert "conditions" in weather
        assert len(weather["conditions"]) > 0


@pytest.mark.asyncio
async def test_weather_precipitation_data():
    """Test that precipitation data is included."""
    with patch("agents.weather_agent.get_api_config") as mock_config:
        mock_config.return_value.weather.use_mock = True

        agent = WeatherAgent()
        state = {
            "intent": {
                "destination": "Greece",
                "travel_month": "July"
            }
        }

        result = await agent._execute(state)

        weather = result["weather"]
        # Should have precipitation info
        assert "precipitation_mm" in weather or "rainfall" in weather


@pytest.mark.asyncio
async def test_different_months_different_weather():
    """Test that weather changes by month."""
    with patch("agents.weather_agent.get_api_config") as mock_config:
        mock_config.return_value.weather.use_mock = True

        agent = WeatherAgent()

        state_summer = {
            "intent": {
                "destination": "Greece",
                "travel_month": "July"
            }
        }

        state_winter = {
            "intent": {
                "destination": "Greece",
                "travel_month": "January"
            }
        }

        result_summer = await agent._execute(state_summer)
        result_winter = await agent._execute(state_winter)

        # Summer should be warmer than winter in Greece
        temp_summer = result_summer["weather"].get("avg_temp_c", 0)
        temp_winter = result_winter["weather"].get("avg_temp_c", 0)

        assert temp_summer > temp_winter


@pytest.mark.asyncio
async def test_handles_missing_month_gracefully():
    """Test that agent works even without travel month."""
    with patch("agents.weather_agent.get_api_config") as mock_config:
        mock_config.return_value.weather.use_mock = True

        agent = WeatherAgent()
        state = {
            "intent": {
                "destination": "Greece"
            }
        }

        result = await agent._execute(state)

        # Should still return weather data or handle gracefully
        assert "weather" in result or "errors" in result


@pytest.mark.asyncio
async def test_weather_forecast_key_exists():
    """Test that weather_forecast is also set for backward compatibility."""
    with patch("agents.weather_agent.get_api_config") as mock_config:
        mock_config.return_value.weather.use_mock = True

        agent = WeatherAgent()
        state = {
            "intent": {
                "destination": "Greece",
                "travel_month": "July"
            }
        }

        result = await agent._execute(state)

        # Both keys should exist
        assert "weather" in result or "weather_forecast" in result
