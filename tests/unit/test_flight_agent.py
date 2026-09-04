"""Unit tests for FlightAgent — tested against actual mock data (no SERPAPI key)."""

import pytest

from agents.flight_agent import FlightAgent, _arrival_hour, _mock_flight_data, _resolve_iata, search_flights

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


def test_effective_dates_capture_is_future(monkeypatch):
    from datetime import date

    agent = FlightAgent()
    monkeypatch.setattr(agent, "_inventory_mode", lambda: "capture")
    departure, return_date = agent._effective_dates(2026, 13)
    assert date.fromisoformat(departure) > date.today()
    assert date.fromisoformat(return_date) > date.fromisoformat(departure)


# ── SerpApi (Google Flights) normalization ───────────────────────────────────

SERPAPI_RESPONSE = {
    "best_flights": [
        {
            "price": 680,
            "total_duration": 870,
            "flights": [
                {
                    "airline": "United",
                    "departure_airport": {"time": "2026-07-01 08:00"},
                    "arrival_airport": {"time": "2026-07-01 20:00"},
                },
                {
                    "airline": "United",
                    "departure_airport": {"time": "2026-07-01 21:00"},
                    "arrival_airport": {"time": "2026-07-01 22:30"},
                },
            ],
        },
        {
            "price": 1400,
            "total_duration": 780,
            "flights": [
                {
                    "airline": "Delta",
                    "departure_airport": {"time": "2026-07-01 07:30"},
                    "arrival_airport": {"time": "2026-07-01 14:00"},
                },
            ],
        },
    ],
    "other_flights": [
        {
            "price": 950,
            "total_duration": 900,
            "flights": [
                {
                    "airline": "Lufthansa",
                    "departure_airport": {"time": "2026-07-01 10:00"},
                    "arrival_airport": {"time": "2026-07-01 23:00"},
                },
                {
                    "airline": "Lufthansa",
                    "departure_airport": {"time": "2026-07-01 23:30"},
                    "arrival_airport": {"time": "2026-07-02 00:30"},
                },
            ],
        },
    ],
}


def _fake_serpapi_client(monkeypatch, payload):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            return FakeResponse()

    monkeypatch.setattr("agents.flight_agent.httpx.AsyncClient", FakeClient)


@pytest.mark.asyncio
async def test_serpapi_normalizes_three_offers(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    _fake_serpapi_client(monkeypatch, SERPAPI_RESPONSE)

    result = await search_flights.coroutine(
        "JFK", "ATH", "2026-07-01", "2026-07-14", 1, None
    )
    flights = result["flights"]
    assert len(flights) == 3

    first = flights[0]
    assert first["price_usd"] == 680
    assert first["airline"] == "United"
    assert first["departure"] == "2026-07-01 08:00"
    assert first["arrival"] == "2026-07-01 22:30"  # last segment's arrival
    assert first["stops"] == 1  # two segments → one stop
    assert first["duration"] == 870
    assert first["duration_minutes"] == 870

    second = flights[1]
    assert second["stops"] == 0  # single segment → direct


@pytest.mark.asyncio
async def test_serpapi_max_price_filter(monkeypatch):
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    _fake_serpapi_client(monkeypatch, SERPAPI_RESPONSE)

    result = await search_flights.coroutine(
        "JFK", "ATH", "2026-07-01", "2026-07-14", 1, 900
    )
    prices = [f["price_usd"] for f in result["flights"]]
    assert all(p <= 900 for p in prices)


@pytest.mark.asyncio
async def test_serpapi_missing_key_falls_back_to_mock(monkeypatch):
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    result = await search_flights.coroutine(
        "JFK", "ATH", "2026-07-01", "2026-07-14", 1, None
    )
    assert result.get("mock") is True
    assert len(result["flights"]) == 2


# ── IATA resolution ──────────────────────────────────────────────────────────

def test_resolve_iata_known_cities():
    assert _resolve_iata("Greece") == "ATH"
    assert _resolve_iata("new york") == "JFK"
    assert _resolve_iata("Tokyo") == "HND"  # TYO is rejected by SerpAPI; HND/NRT work
    assert _resolve_iata("Bali") == "DPS"
    assert _resolve_iata("New Zealand") == "AKL"
    assert _resolve_iata("Costa Rica") == "SJO"
    assert _resolve_iata("Seoul") == "ICN"
    assert _resolve_iata("LA") == "LAX"


def test_resolve_iata_unknown_returns_empty_not_garbage():
    """Unknown destinations must NOT be truncated to a bogus 3-letter code
    (SerpAPI 400s on invalid IATAs, silently emptying flights and invalidating
    the whole run)."""
    assert _resolve_iata("Atlantis") == ""
    assert _resolve_iata("") == ""
    assert _resolve_iata(None) == ""
    assert _resolve_iata("12345") == ""


@pytest.mark.asyncio
async def test_serpapi_unresolvable_iata_falls_back_to_mock(monkeypatch):
    """An unknown destination must fall back to mock rather than send a bogus
    IATA to SerpAPI and get back an empty (invalidating) result set."""
    monkeypatch.setenv("SERPAPI_API_KEY", "test-key")
    result = await search_flights.coroutine(
        "JFK", "Atlantis", "2026-07-01", "2026-07-14", 1, None
    )
    assert result.get("mock") is True
    assert len(result["flights"]) == 2
