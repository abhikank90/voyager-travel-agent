"""Unit tests for CollaborationHubAgent.

Focuses on the deterministic rule-based conflict detection and message-routing
logic. The LLM call (narrative summary generation) is mocked out so these tests
don't require a real API key and run identically on every invocation.
"""

from unittest.mock import MagicMock, patch

import pytest

from agents.collaboration_hub import CollaborationHubAgent

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def hub():
    """CollaborationHubAgent with Anthropic client mocked out."""
    with patch("agents.collaboration_hub.Anthropic") as mock_anthropic, \
         patch("agents.collaboration_hub.get_api_config") as mock_cfg:
        mock_cfg.return_value.llm.api_key = "ci-test-key"
        mock_cfg.return_value.llm.collaboration_hub_model = "claude-haiku-4-5-20251001"

        mock_client = MagicMock()
        mock_anthropic.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Hub analysis narrative.")]
        mock_response.usage = MagicMock(input_tokens=100, output_tokens=50)
        mock_client.messages.create.return_value = mock_response

        agent = CollaborationHubAgent()
        agent.client = mock_client
        return agent


# States with known conflict patterns

def _state_location_mismatch() -> dict:
    """Hotel in Beachfront, all top experiences in Oia — mismatch fires."""
    return {
        "intent": {"destination": "Greece", "budget_usd": 2000, "interests": ["beaches"]},
        "collaboration_round": 1,
        "selected_hotel": {"name": "Aegean Bliss", "location": "Beachfront", "total_usd": 595},
        "experiences": [
            {"name": "Sunset", "category": "culture", "location": "Oia, Santorini"},
            {"name": "Boat Tour", "category": "outdoor", "location": "Fira center"},
            {"name": "Dinner", "category": "food", "location": "Oia village"},
        ],
        "selected_flight": {"airline": "UA", "arrival": "2026-07-01T14:00:00", "price_usd": 680},
        "weather": {"avg_temp_c": 25, "summary": "warm and sunny", "precipitation_mm": 5},
        "visa_safety": {"visa_required": False, "safety_level": "safe"},
        "flights": [],
        "hotels": [],
        "agent_messages": [],
        "conflicts": [],
    }


def _state_no_conflicts() -> dict:
    """Hotel and experiences both in Santorini, flight on time, pleasant weather."""
    return {
        "intent": {"destination": "Greece", "budget_usd": 2000, "interests": ["beaches"]},
        "collaboration_round": 1,
        "selected_hotel": {"name": "Santorini Resort", "location": "Santorini", "total_usd": 700},
        "experiences": [
            {"name": "Red Beach", "category": "beach", "location": "Santorini"},
            {"name": "Oia Walk", "category": "culture", "location": "Santorini"},
            {"name": "Taverna", "category": "food", "location": "Santorini"},
        ],
        "selected_flight": {"airline": "LH", "arrival": "2026-07-01T13:00:00", "price_usd": 890},
        "weather": {"avg_temp_c": 28, "summary": "warm", "precipitation_mm": 2},
        "visa_safety": {},
        "flights": [],
        "hotels": [],
        "agent_messages": [],
        "conflicts": [],
    }


# ── Conflict detection rules ───────────────────────────────────────────────────

def test_location_mismatch_fires_when_hotel_far_from_experiences(hub):
    assert hub._check_hotel_experience_mismatch(_state_location_mismatch()) is True


def test_location_mismatch_clear_when_hotel_matches_experiences(hub):
    assert hub._check_hotel_experience_mismatch(_state_no_conflicts()) is False


def test_location_mismatch_false_when_no_hotel(hub):
    state = _state_location_mismatch()
    state["selected_hotel"] = {}
    assert hub._check_hotel_experience_mismatch(state) is False


def test_location_mismatch_false_when_hotel_is_none(hub):
    """Real inventory may leave selected_hotel None (no qualifying hotel).
    The hub must not crash and must treat it as 'no hotel'."""
    state = _state_location_mismatch()
    state["selected_hotel"] = None
    assert hub._check_hotel_experience_mismatch(state) is False


def test_synergies_do_not_crash_when_hotel_is_none(hub):
    state = _state_no_conflicts()
    state["selected_hotel"] = None
    assert hub._identify_synergies(state) == []


def test_location_mismatch_false_when_no_experiences(hub):
    state = _state_location_mismatch()
    state["experiences"] = []
    assert hub._check_hotel_experience_mismatch(state) is False


def test_location_mismatch_false_when_experiences_have_no_location(hub):
    state = _state_location_mismatch()
    state["experiences"] = [{"name": "Beach", "location": ""}] * 3
    assert hub._check_hotel_experience_mismatch(state) is False


def test_timing_fires_on_late_arrival(hub):
    state = _state_no_conflicts()
    state["selected_flight"] = {"arrival": "2026-07-01T22:30:00", "price_usd": 680}
    assert hub._check_flight_timing_issue(state) is True


def test_timing_clear_on_afternoon_arrival(hub):
    state = _state_no_conflicts()
    state["selected_flight"] = {"arrival": "2026-07-01T13:00:00", "price_usd": 890}
    assert hub._check_flight_timing_issue(state) is False


def test_timing_clear_on_early_morning_arrival(hub):
    """19:00 arrival is under the 20:00 threshold — should not fire."""
    state = _state_no_conflicts()
    state["selected_flight"] = {"arrival": "2026-07-01T19:59:00", "price_usd": 750}
    assert hub._check_flight_timing_issue(state) is False


def test_timing_departure_does_not_trigger_conflict(hub):
    """Outbound departure time (origin → destination) must NOT affect the rule.
    An early JFK departure maximises Day 1; it is not a 'waste'."""
    state = _state_no_conflicts()
    # Flight departs JFK at 06:00, arrives Santorini at 13:00 — should be fine
    state["selected_flight"] = {
        "departure": "2026-07-01T06:00:00",
        "arrival": "2026-07-01T13:00:00",
        "price_usd": 890,
    }
    assert hub._check_flight_timing_issue(state) is False


def test_weather_mismatch_fires_on_heat_with_outdoor_activities(hub):
    state = _state_no_conflicts()
    state["weather"] = {"avg_temp_c": 33, "summary": "hot and dry", "precipitation_mm": 5}
    state["experiences"] = [
        {"name": "Beach Day", "category": "beach", "location": "Red Beach"},
        {"name": "Hike", "category": "outdoor", "location": "Trail"},
        {"name": "Dinner", "category": "food", "location": "Oia"},
    ]
    assert hub._check_weather_activity_mismatch(state) is True


def test_weather_mismatch_clear_on_mild_temperature(hub):
    state = _state_no_conflicts()
    state["weather"] = {"avg_temp_c": 26, "summary": "pleasant", "precipitation_mm": 5}
    assert hub._check_weather_activity_mismatch(state) is False


def test_weather_mismatch_clear_when_fewer_than_two_outdoor_activities(hub):
    state = _state_no_conflicts()
    state["weather"] = {"avg_temp_c": 34, "summary": "very hot", "precipitation_mm": 0}
    state["experiences"] = [
        {"name": "Museum", "category": "culture", "location": "Athens"},
        {"name": "Dinner", "category": "food", "location": "Athens"},
    ]
    assert hub._check_weather_activity_mismatch(state) is False


# ── Message generation ────────────────────────────────────────────────────────

def test_location_mismatch_sends_message_to_hotel_only(hub):
    """Hub should only move the hotel to experience locations, not also
    move experiences to hotel location (that would bounce forever)."""
    msgs = hub._generate_collaboration_messages(_state_location_mismatch(), round=1)
    recipients = [m["to_agent"] for m in msgs]
    assert "hotel" in recipients
    assert "experience" not in recipients, (
        "Hub must not send contradicting relocation message to experience agent"
    )


def test_timing_message_has_preferred_arrival_no_departure(hub):
    state = _state_location_mismatch()
    state["selected_flight"] = {"arrival": "2026-07-01T22:30:00", "price_usd": 680}
    msgs = hub._generate_collaboration_messages(state, round=1)
    flight_msgs = [m for m in msgs if m["to_agent"] == "flight"]
    assert len(flight_msgs) >= 1
    assert "preferred_arrival" in flight_msgs[0]["data"]
    assert "preferred_departure" not in flight_msgs[0]["data"]


def test_message_structure_has_required_fields(hub):
    msgs = hub._generate_collaboration_messages(_state_location_mismatch(), round=1)
    valid_types = {"insight", "constraint", "question", "proposal", "conflict"}
    for msg in msgs:
        assert msg["from_agent"] == "collaboration_hub"
        assert "to_agent" in msg
        assert "message_type" in msg
        assert msg["message_type"] in valid_types
        assert "content" in msg
        assert "round" in msg


# ── Round dispatch ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_round_1_returns_conflicts_and_messages(hub):
    result = await hub._execute(_state_location_mismatch())
    assert result["collaboration_round"] == 1
    assert "conflicts" in result
    assert "agent_messages" in result
    assert "shared_discoveries" in result


@pytest.mark.asyncio
async def test_round_1_detects_location_mismatch(hub):
    result = await hub._execute(_state_location_mismatch())
    conflict_types = [c["type"] for c in result["conflicts"]]
    assert "location_mismatch" in conflict_types


@pytest.mark.asyncio
async def test_round_1_no_conflicts_when_state_clean(hub):
    result = await hub._execute(_state_no_conflicts())
    assert result["conflicts"] == []
    assert result["agent_messages"] == []


@pytest.mark.asyncio
async def test_round_2_returns_reduced_conflicts_after_resolution(hub):
    """After the hotel moves to the activity location, Round 2 should
    detect zero location_mismatch conflicts."""
    state = _state_no_conflicts()
    state["collaboration_round"] = 2
    state["conflicts"] = [{"type": "location_mismatch", "agents": ["hotel", "experience"], "severity": "medium"}]
    result = await hub._execute(state)
    assert result["collaboration_round"] == 2
    assert "conflicts" in result
    location_conflicts = [c for c in result["conflicts"] if c["type"] == "location_mismatch"]
    assert len(location_conflicts) == 0


@pytest.mark.asyncio
async def test_anthropic_called_in_round_1(hub):
    await hub._execute(_state_location_mismatch())
    hub.client.messages.create.assert_called_once()


@pytest.mark.asyncio
async def test_anthropic_not_called_in_round_2(hub):
    state = _state_no_conflicts()
    state["collaboration_round"] = 2
    state["conflicts"] = []
    await hub._execute(state)
    hub.client.messages.create.assert_not_called()


# ── Final conflict audit ───────────────────────────────────────────────────────

def test_detect_conflicts_only_is_deterministic(hub):
    """Same state → same conflicts on every call."""
    state = _state_location_mismatch()
    result_a = hub.detect_conflicts_only(state)
    result_b = hub.detect_conflicts_only(state)
    assert result_a == result_b


def test_detect_conflicts_only_returns_no_conflicts_for_clean_state(hub):
    assert hub.detect_conflicts_only(_state_no_conflicts()) == []


# ── Experience location window ─────────────────────────────────────────────────

def test_get_experience_locations_uses_top_3_only(hub):
    """Must use experiences[:3] — same window as the mismatch check — so the
    hint passed to HotelAgent is guaranteed to satisfy the audit."""
    state = {
        "experiences": [
            {"location": "Oia"},
            {"location": "Fira"},
            {"location": "Imerovigli"},
            {"location": "Perissa"},  # position 4 — must be excluded
            {"location": "Akrotiri"},  # position 5 — must be excluded
        ]
    }
    locs = hub._get_experience_locations(state)
    assert "Perissa" not in locs
    assert "Akrotiri" not in locs
    assert locs[0] == "Oia"  # ordering is deterministic


def test_get_experience_locations_ordered_dedup(hub):
    state = {
        "experiences": [
            {"location": "Oia"},
            {"location": "Oia"},  # duplicate
            {"location": "Fira"},
        ]
    }
    locs = hub._get_experience_locations(state)
    assert locs == ["Oia", "Fira"]
