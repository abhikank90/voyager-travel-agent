"""Unit tests for live-inventory capture and deterministic replay (Priority 3).

Verifies: replay never opens the network, missing fixtures fail clearly, hash
mismatches are detected, and captured-vs-replayed selections are identical
under the same constraints. No test calls a live API.
"""

import json

import pytest

from agents import inventory
from config.settings import reload_settings


@pytest.fixture()
def tmp_inventory_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VOYAGER_INVENTORY_DIR", str(tmp_path))
    monkeypatch.setenv("VOYAGER_INVENTORY_MODE", "mock")
    reload_settings()
    return tmp_path


def _sample_flights():
    return {"flights": [
        {"price_usd": 680, "airline": "UA", "arrival": "2026-07-01T22:30:00"},
        {"price_usd": 890, "airline": "LH", "arrival": "2026-07-01T13:00:00"},
    ], "mock": False}


def test_replay_never_opens_network(tmp_inventory_dir, monkeypatch):
    query_id = inventory.inventory_query_id("serpapi", origin="JFK", destination="ATH")
    inventory.capture("serpapi", _sample_flights(), query_id, run_label="test")

    import httpx
    # If replay touched the network it would construct an AsyncClient; guard it.
    opened = []

    class GuardedClient(httpx.AsyncClient):
        def __init__(self, *a, **k):
            opened.append(True)
            super().__init__(*a, **k)

    monkeypatch.setattr("agents.flight_agent.httpx.AsyncClient", GuardedClient)

    monkeypatch.setenv("VOYAGER_INVENTORY_MODE", "replay")
    reload_settings()

    result = inventory.replay("serpapi", query_id)
    assert result["flights"] == _sample_flights()["flights"]
    assert opened == []


def test_missing_fixture_fails_clearly(tmp_inventory_dir):
    with pytest.raises(FileNotFoundError, match="capture"):
        inventory.replay("serpapi", "nonexistent_query_id")


def test_fixture_hash_mismatch_detected(tmp_inventory_dir):
    query_id = inventory.inventory_query_id("openweather", destination="Greece")
    inventory.capture("openweather", {"avg_temp_c": 28}, query_id, run_label="test")

    # Tamper with the fixture file after capture.
    path = tmp_inventory_dir / f"{query_id}_openweather.json"
    path.write_text(json.dumps({"avg_temp_c": 999}))

    with pytest.raises(ValueError, match="hash mismatch"):
        inventory.replay("openweather", query_id)


def test_capture_and_replay_produce_identical_selections(tmp_inventory_dir):
    """Under the same selection constraint, replay selects the same flight."""
    from unittest.mock import patch

    from agents.flight_agent import FlightAgent, _arrival_hour

    # Capture and replay both derive future-dated queries via _effective_dates;
    # the fixture must be stored under the exact query_id the agent computes
    # at run time, otherwise replay can't find it.
    probe = FlightAgent()
    with patch.object(probe, "_inventory_mode", return_value="replay"):
        dep, ret = probe._effective_dates(2026)
    query_id = inventory.inventory_query_id(
        "serpapi", origin="New York", destination="Greece",
        departure_date=dep, return_date=ret, adults=1,
    )
    inventory.capture("serpapi", _sample_flights(), query_id, run_label="test")

    state = {
        "intent": {
            "destination": "Greece", "origin": "New York", "budget_usd": 2000,
            "travel_year": 2026, "travel_month": "July", "group_size": 1,
        },
        "collaboration_round": 2,
        "agent_messages": [
            {"to_agent": "flight", "message_type": "insight",
             "data": {"preferred_arrival": "before 14:00"}, "round": 1},
        ],
    }

    import asyncio
    from unittest.mock import patch

    async def run():
        agent = FlightAgent()
        with patch.object(agent, "_inventory_mode", return_value="replay"):
            return await agent._execute(state)

    result = asyncio.run(run())
    # Replay selects the on-time LH flight (before 14:00), not the cheaper UA late flight.
    assert _arrival_hour(result["selected_flight"]["arrival"]) < 14
    assert result["selected_flight"]["airline"] == "LH"


def test_manifest_records_hash_and_sanitized_flag(tmp_inventory_dir):
    query_id = inventory.inventory_query_id("serpapi", origin="JFK")
    inventory.capture("serpapi", _sample_flights(), query_id, run_label="test")
    manifest = inventory.load_manifest()
    entry = manifest["fixtures"][f"{query_id}_serpapi"]
    assert entry["sanitized"] is True
    assert entry["fixture_hash"]
    assert entry["source"] == "serpapi"
    assert entry["query_id"] == query_id


# ── Weather agent inventory branches ─────────────────────────────────────────

def _weather_payload():
    return {"avg_temp_c": 33, "avg_temp_f": 91, "precipitation_mm": 5,
            "summary": "hot and dry", "source": "openweather"}


def test_weather_replay_returns_captured_fixture(tmp_inventory_dir, monkeypatch):
    """WeatherAgent in replay mode reads the captured fixture (never forecasts)."""
    import asyncio

    from agents.weather_agent import WeatherAgent

    query_id = inventory.inventory_query_id("openweather", destination="Greece", month="july")
    inventory.capture("openweather", _weather_payload(), query_id, run_label="test")

    monkeypatch.setenv("VOYAGER_INVENTORY_MODE", "replay")
    reload_settings()

    agent = WeatherAgent()
    result = asyncio.run(agent._execute({"intent": {"destination": "Greece", "travel_month": "July"}}))

    assert result["weather"] == _weather_payload()
    assert result["travel_month"] == "july"


def test_weather_replay_never_opens_network(tmp_inventory_dir, monkeypatch):
    import asyncio

    import httpx

    from agents.weather_agent import WeatherAgent

    query_id = inventory.inventory_query_id("openweather", destination="Greece", month="july")
    inventory.capture("openweather", _weather_payload(), query_id, run_label="test")

    opened = []

    class GuardedClient(httpx.AsyncClient):
        def __init__(self, *a, **k):
            opened.append(True)
            super().__init__(*a, **k)

    monkeypatch.setattr("agents.weather_agent.httpx.AsyncClient", GuardedClient)
    monkeypatch.setenv("VOYAGER_INVENTORY_MODE", "replay")
    reload_settings()

    agent = WeatherAgent()
    asyncio.run(agent._execute({"intent": {"destination": "Greece", "travel_month": "July"}}))

    assert opened == []


def test_weather_capture_writes_fixture(tmp_inventory_dir, monkeypatch):
    """WeatherAgent capture mode (no API key → historical fallback) writes a fixture."""
    import asyncio

    from agents.weather_agent import WeatherAgent

    monkeypatch.delenv("OPENWEATHER_API_KEY", raising=False)
    monkeypatch.setenv("VOYAGER_INVENTORY_MODE", "capture")
    reload_settings()

    agent = WeatherAgent()
    asyncio.run(agent._execute({"intent": {"destination": "Greece", "travel_month": "July"}}))

    query_id = inventory.inventory_query_id("openweather", destination="Greece", month="july")
    manifest = inventory.load_manifest()
    entry = manifest["fixtures"].get(f"{query_id}_openweather")
    assert entry is not None
    assert entry["source"] == "openweather"
