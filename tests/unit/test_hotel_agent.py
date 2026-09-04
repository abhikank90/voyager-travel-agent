"""Unit tests for HotelAgent — tested against actual mock data (no NUITEE_API_KEY)."""

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
async def test_location_hint_skips_empty_constraint_messages():
    """A constraint message with no hint/centroid data must not short-circuit
    parsing: later messages that do carry a usable hint are still honored."""
    agent = HotelAgent()
    state = {
        "intent": INTENT_BASE,
        "collaboration_round": 2,
        "agent_messages": [
            {
                "to_agent": "hotel",
                "message_type": "constraint",
                "data": {"suggested_budget": 800},
                "round": 1,
            },
            {
                "to_agent": "hotel",
                "message_type": "constraint",
                "data": {"activity_locations": ["Oia, Santorini"]},
                "round": 1,
            },
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


# ── Nuitee (LiteAPI) three-call flow ──────────────────────────────────────────

NUITEE_PLACES = {"data": [{"placeId": "place-123", "displayName": "Orlando"}]}

NUITEE_RATES = {
    "data": [
        {
            "hotelId": "hotel-1",
            "roomTypes": [
                {"offerRetailRate": {"amount": 306.68}},
                {"offerRetailRate": {"amount": 326.05}},
            ],
        },
        {
            "hotelId": "hotel-2",
            "roomTypes": [
                {"offerRetailRate": {"amount": 412.00}},
            ],
        },
    ]
}

NUITEE_DETAILS = {
    "hotel-1": [
        {
            "name": "Lakeside Resort",
            "address": "2000 Hotel Plaza Boulevard",
            "city": "Orlando",
            "country": "us",
            "latitude": 28.378342,
            "longitude": -81.508629,
            "rating": 4.5,
        }
    ],
    "hotel-2": [
        {
            "name": "Airport Inn",
            "address": "1 Terminal Drive",
            "city": "Dallas",
            "country": "us",
            "latitude": 32.8998,
            "longitude": -97.0403,
            "rating": 3.9,
        }
    ],
}

NUITEE_DETAILS_NESTED = {
    "hotel-3": {
        "name": "Harbor View",
        "address": "5 Marina Way",
        "city": "Miami",
        "country": "us",
        "rating": 4.2,
        "location": {"latitude": 25.7617, "longitude": -80.1918},
    }
}


def _fake_nuitee_client(
    monkeypatch,
    places=None,
    rates=None,
    details=None,
    raise_details=False,
):
    places = places if places is not None else NUITEE_PLACES
    rates = rates if rates is not None else NUITEE_RATES
    details = details if details is not None else NUITEE_DETAILS

    class FakeResponse:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, *a, **k):
            params = k.get("params", {}) or {}
            if "/data/places" in url:
                return FakeResponse(places)
            if "/data/hotel" in url:
                if raise_details:
                    raise Exception("rate limited")
                hotel_id = params.get("hotelId", "")
                return FakeResponse({"data": details.get(hotel_id, [])})
            return FakeResponse({})

        async def post(self, url, *a, **k):
            if "/hotels/rates" in url:
                return FakeResponse(rates)
            return FakeResponse({})

    monkeypatch.setattr("agents.hotel_agent.httpx.AsyncClient", FakeClient)


@pytest.mark.asyncio
async def test_nuitee_selects_cheapest_room_type(monkeypatch):
    monkeypatch.setenv("NUITEE_API_KEY", "test-key")
    _fake_nuitee_client(monkeypatch)

    agent = HotelAgent()
    result = await agent._fetch_real("Orlando", "2026-10-01", "2026-10-04", 2, 1000)

    hotels = result["hotels"]
    assert len(hotels) == 2
    first = hotels[0]
    assert first["hotel_id"] == "hotel-1"
    assert first["total_usd"] == 306.68
    assert first["price_per_night_usd"] == pytest.approx(306.68 / 3, abs=0.01)
    assert hotels[1]["hotel_id"] == "hotel-2"
    assert hotels[1]["total_usd"] == 412.00


@pytest.mark.asyncio
async def test_nuitee_merges_static_details(monkeypatch):
    monkeypatch.setenv("NUITEE_API_KEY", "test-key")
    _fake_nuitee_client(monkeypatch)

    agent = HotelAgent()
    result = await agent._fetch_real("Orlando", "2026-10-01", "2026-10-04", 2, 1000)

    hotel = result["hotels"][0]
    assert hotel["name"] == "Lakeside Resort"
    assert hotel["rating"] == 4.5
    assert hotel["latitude"] == 28.378342
    assert hotel["longitude"] == -81.508629
    assert "Orlando" in hotel["location"]
    assert "US" in hotel["location"]


@pytest.mark.asyncio
async def test_nuitee_details_nested_location_shape(monkeypatch):
    """/data/hotel may return data as an object with nested location: {lat, lon}
    rather than a list with flat coordinates. Coordinates must still surface."""
    monkeypatch.setenv("NUITEE_API_KEY", "test-key")
    rates = {
        "data": [
            {
                "hotelId": "hotel-3",
                "roomTypes": [{"offerRetailRate": {"amount": 240.00}}],
            }
        ]
    }
    _fake_nuitee_client(monkeypatch, rates=rates, details=NUITEE_DETAILS_NESTED)

    agent = HotelAgent()
    result = await agent._fetch_real("Miami", "2026-10-01", "2026-10-04", 2, 1000)

    hotel = result["hotels"][0]
    assert hotel["hotel_id"] == "hotel-3"
    assert hotel["name"] == "Harbor View"
    assert hotel["rating"] == 4.2
    assert hotel["latitude"] == 25.7617
    assert hotel["longitude"] == -80.1918
    assert "Miami" in hotel["location"]
    assert "US" in hotel["location"]


@pytest.mark.asyncio
async def test_nuitee_details_failure_degrades_gracefully(monkeypatch):
    monkeypatch.setenv("NUITEE_API_KEY", "test-key")
    _fake_nuitee_client(monkeypatch, raise_details=True)

    agent = HotelAgent()
    result = await agent._fetch_real("Orlando", "2026-10-01", "2026-10-04", 2, 1000)

    hotels = result["hotels"]
    assert len(hotels) == 2
    first = hotels[0]
    assert first["name"] == "hotel-1"
    assert first["latitude"] is None
    assert first["longitude"] is None
    assert first["total_usd"] == 306.68


@pytest.mark.asyncio
async def test_nuitee_no_place_returns_empty(monkeypatch):
    monkeypatch.setenv("NUITEE_API_KEY", "test-key")
    _fake_nuitee_client(monkeypatch, places={"data": []})

    agent = HotelAgent()
    result = await agent._fetch_real("Nowhere", "2026-10-01", "2026-10-04", 2, 1000)
    assert result["hotels"] == []


@pytest.mark.asyncio
async def test_nuitee_prefers_locality_over_earlier_match(monkeypatch):
    """Places can return a broad match (country) before the locality. The agent
    must pick the locality entry even when it isn't first in the payload."""
    monkeypatch.setenv("NUITEE_API_KEY", "test-key")
    places = {"data": [
        {"placeId": "country-1", "displayName": "Greece", "types": ["country"]},
        {"placeId": "locality-1", "displayName": "Santorini", "types": ["locality"]},
    ]}
    _fake_nuitee_client(monkeypatch, places=places)

    agent = HotelAgent()
    result = await agent._fetch_real("Santorini", "2026-10-01", "2026-10-04", 2, 1000)

    assert len(result["hotels"]) == 2
    assert result["hotels"][0]["hotel_id"] == "hotel-1"


@pytest.mark.asyncio
async def test_nuitee_retries_on_429(monkeypatch):
    """/v3.0/data/places can 429 under burst load (LiteAPI sandbox ~5 req/s).
    The throttled request helper must retry and still resolve the destination."""
    monkeypatch.setenv("NUITEE_API_KEY", "test-key")

    class _RateLimitedClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, *a, **k):
            if "/data/places" in url:
                if self._places_calls == 0:
                    self._places_calls += 1
                    return FakeResponseRateLimited({}, status_code=429)
                return FakeResponseRateLimited(NUITEE_PLACES)
            if "/data/hotel" in url:
                return FakeResponseRateLimited({"data": []})
            return FakeResponseRateLimited({})

        async def post(self, url, *a, **k):
            if "/hotels/rates" in url:
                return FakeResponseRateLimited(NUITEE_RATES)
            return FakeResponseRateLimited({})

    class FakeResponseRateLimited:
        def __init__(self, payload, status_code=200):
            self._payload = payload
            self.status_code = status_code

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    _RateLimitedClient._places_calls = 0
    monkeypatch.setattr("agents.hotel_agent.httpx.AsyncClient", _RateLimitedClient)

    agent = HotelAgent()
    result = await agent._fetch_real("Orlando", "2026-10-01", "2026-10-04", 2, 1000)
    assert len(result["hotels"]) == 2


@pytest.mark.asyncio
async def test_capture_replay_round_trip(monkeypatch, tmp_path):
    from config.settings import reload_settings

    monkeypatch.setenv("VOYAGER_INVENTORY_DIR", str(tmp_path))
    monkeypatch.setenv("NUITEE_API_KEY", "test-key")
    _fake_nuitee_client(monkeypatch)

    state = {"intent": {**INTENT_BASE, "destination": "Orlando", "group_size": 2}}

    try:
        monkeypatch.setenv("VOYAGER_INVENTORY_MODE", "capture")
        reload_settings()
        captured = await HotelAgent()._execute(state)

        monkeypatch.setenv("VOYAGER_INVENTORY_MODE", "replay")
        reload_settings()
        replayed = await HotelAgent()._execute(state)
    finally:
        monkeypatch.setenv("VOYAGER_INVENTORY_MODE", "mock")
        reload_settings()

    assert captured["selected_hotel"]["hotel_id"] == replayed["selected_hotel"]["hotel_id"]
    assert captured["selected_hotel"]["total_usd"] == replayed["selected_hotel"]["total_usd"]


@pytest.mark.asyncio
async def test_centroid_selects_nearest_hotel(monkeypatch, tmp_path):
    from config.settings import reload_settings

    monkeypatch.setenv("NUITEE_API_KEY", "test-key")
    monkeypatch.setenv("VOYAGER_INVENTORY_DIR", str(tmp_path))
    monkeypatch.setenv("VOYAGER_INVENTORY_MODE", "capture")
    reload_settings()
    _fake_nuitee_client(monkeypatch)

    agent = HotelAgent()
    state = {
        "intent": {**INTENT_BASE, "destination": "Orlando", "group_size": 2},
        "collaboration_round": 2,
        "agent_messages": [
            {
                "to_agent": "hotel",
                "message_type": "constraint",
                "data": {
                    "activity_locations": ["Orlando"],
                    "activity_centroid": {"lat": 28.39, "lon": -81.51},
                },
                "round": 1,
            }
        ],
    }
    result = await agent._execute(state)
    assert result["selected_hotel"]["hotel_id"] == "hotel-1"
    assert result["feedback_metrics"]["feedback_satisfiable"] is True
    assert result["feedback_metrics"]["reason"] == "qualifying_option_found"


def test_effective_dates_capture_is_future(monkeypatch):
    from datetime import date

    agent = HotelAgent()
    monkeypatch.setattr(agent, "_inventory_mode", lambda: "capture")
    check_in, check_out = agent._effective_dates(2026, 7)
    assert date.fromisoformat(check_in) > date.today()
    assert date.fromisoformat(check_out) > date.fromisoformat(check_in)


def test_location_hint_feedback_satisfiable():
    candidates = [{"location": "Oia, Santorini", "total_usd": 100}]
    feedback = HotelAgent._location_hint_feedback(candidates, "Oia")
    assert feedback["feedback_applied"] is True
    assert feedback["feedback_satisfiable"] is True
    assert feedback["fallback_to_original_selection"] is False


def test_location_hint_feedback_unsatisfiable():
    candidates = [{"location": "Beachfront", "total_usd": 100}]
    feedback = HotelAgent._location_hint_feedback(candidates, "Oia")
    assert feedback["feedback_applied"] is True
    assert feedback["feedback_satisfiable"] is False
    assert feedback["fallback_to_original_selection"] is True
    assert feedback["reason"] == "no_qualifying_option"


def test_location_hint_feedback_not_applied():
    feedback = HotelAgent._location_hint_feedback([{"location": "Beachfront"}], None)
    assert feedback["feedback_applied"] is False


def test_location_hint_feedback_centroid_satisfiable():
    candidates = [
        {"location": "Orlando, US", "latitude": 28.378342, "longitude": -81.508629},
        {"location": "Dallas, US", "latitude": 32.8998, "longitude": -97.0403},
    ]
    feedback = HotelAgent._location_hint_feedback(
        candidates, "Orlando", centroid=(28.39, -81.51)
    )
    assert feedback["feedback_applied"] is True
    assert feedback["feedback_satisfiable"] is True
    assert feedback["fallback_to_original_selection"] is False


def test_location_hint_feedback_centroid_unsatisfiable():
    candidates = [
        {"location": "Orlando, US", "latitude": 28.378342, "longitude": -81.508629},
        {"location": "Dallas, US", "latitude": 32.8998, "longitude": -97.0403},
    ]
    feedback = HotelAgent._location_hint_feedback(
        candidates, "Orlando", centroid=(51.5, -0.12)
    )
    assert feedback["feedback_applied"] is True
    assert feedback["feedback_satisfiable"] is False
    assert feedback["fallback_to_original_selection"] is True
    assert feedback["reason"] == "no_qualifying_option"
