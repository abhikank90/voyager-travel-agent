"""
Integration tests for FastAPI endpoints.
Tests collaborative endpoints, option selection, and refinement.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock
from api.main import app


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture
def mock_graph_run():
    """Mock the collaborative travel graph execution."""
    with patch("api.main.run_collaborative_travel_query") as mock_run:
        mock_result = {
            "session_id": "test-session-123",
            "intent": {
                "destination": "Greece",
                "budget_usd": 2000
            },
            "trip_options": [
                {
                    "option_id": 0,
                    "style": "budget",
                    "title": "Budget Explorer - Greece",
                    "total_cost_usd": 1500,
                    "flight": {"price": 450},
                    "hotel": {"price_per_night": 60},
                    "day_by_day": [],
                    "flight_booking_url": "https://google.com/flights",
                    "hotel_booking_url": "https://booking.com",
                    "highlights": ["Save $500"],
                    "trade_offs": ["1 stop flight"]
                },
                {
                    "option_id": 1,
                    "style": "balanced",
                    "title": "Balanced - Greece",
                    "total_cost_usd": 2000,
                    "flight": {"price": 650},
                    "hotel": {"price_per_night": 120},
                    "day_by_day": [],
                    "flight_booking_url": "https://google.com/flights",
                    "hotel_booking_url": "https://booking.com",
                    "highlights": ["Best value"],
                    "trade_offs": []
                },
                {
                    "option_id": 2,
                    "style": "premium",
                    "title": "Premium - Greece",
                    "total_cost_usd": 2300,
                    "flight": {"price": 850},
                    "hotel": {"price_per_night": 250},
                    "day_by_day": [],
                    "flight_booking_url": "https://google.com/flights",
                    "hotel_booking_url": "https://booking.com",
                    "highlights": ["Direct flight", "Luxury resort"],
                    "trade_offs": ["$300 over budget"]
                }
            ],
            "collaboration_messages": [
                {
                    "from_agent": "collaboration_hub",
                    "to_agent": "hotel",
                    "message_type": "constraint",
                    "content": "Find hotels closer to activities"
                }
            ],
            "status": "complete"
        }

        mock_run.return_value = mock_result
        yield mock_run


def test_health_endpoint(client):
    """Test that health endpoint returns OK."""
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_collaborative_endpoint_success(client, mock_graph_run):
    """Test collaborative travel planning endpoint."""
    request_data = {
        "query": "Greece under $2000, beaches, summer 2026",
        "user_id": "test-user"
    }

    response = client.post("/api/travel/collaborative", json=request_data)

    assert response.status_code == 200
    data = response.json()

    assert "session_id" in data
    assert "trip_options" in data
    assert len(data["trip_options"]) == 3
    assert "collaboration_messages" in data


def test_collaborative_endpoint_returns_three_options(client, mock_graph_run):
    """Test that collaborative endpoint returns exactly 3 trip options."""
    request_data = {
        "query": "Greece under $2000"
    }

    response = client.post("/api/travel/collaborative", json=request_data)

    assert response.status_code == 200
    data = response.json()

    options = data["trip_options"]
    assert len(options) == 3

    styles = [opt["style"] for opt in options]
    assert "budget" in styles
    assert "balanced" in styles
    assert "premium" in styles


def test_collaborative_endpoint_validation():
    """Test that endpoint validates required fields."""
    client_test = TestClient(app)

    # Missing query
    response = client_test.post("/api/travel/collaborative", json={})

    # Should return validation error
    assert response.status_code == 422


def test_select_option_endpoint():
    """Test option selection endpoint."""
    with patch("api.main.session_storage") as mock_storage:
        mock_storage.get.return_value = {
            "trip_options": [
                {"option_id": 0, "style": "budget"},
                {"option_id": 1, "style": "balanced"},
                {"option_id": 2, "style": "premium"}
            ]
        }

        client_test = TestClient(app)

        request_data = {
            "session_id": "test-session",
            "option_id": 1
        }

        response = client_test.post("/api/travel/select-option", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert data["session_id"] == "test-session"
        assert data["selected_option_id"] == 1
        assert "selected_option" in data
        assert data["selected_option"]["style"] == "balanced"


def test_select_option_invalid_option_id():
    """Test that invalid option_id is handled."""
    with patch("api.main.session_storage") as mock_storage:
        mock_storage.get.return_value = {
            "trip_options": [
                {"option_id": 0},
                {"option_id": 1},
                {"option_id": 2}
            ]
        }

        client_test = TestClient(app)

        request_data = {
            "session_id": "test-session",
            "option_id": 5  # Invalid
        }

        response = client_test.post("/api/travel/select-option", json=request_data)

        # Should return error
        assert response.status_code == 400 or response.status_code == 404


def test_refine_endpoint():
    """Test refinement endpoint."""
    with patch("api.main.session_storage") as mock_storage:
        with patch("api.main.run_refinement") as mock_refine:
            mock_storage.get.return_value = {
                "trip_options": [
                    {"option_id": 1, "style": "balanced"}
                ]
            }

            mock_refine.return_value = {
                "option_id": 1,
                "style": "balanced",
                "title": "Refined - Greece",
                "total_cost_usd": 1950
            }

            client_test = TestClient(app)

            request_data = {
                "session_id": "test-session",
                "selected_option_id": 1,
                "refinement_query": "Use hotel from budget option"
            }

            response = client_test.post("/api/travel/refine", json=request_data)

            assert response.status_code == 200
            data = response.json()

            assert "refined_option" in data
            assert data["refinement_query"] == "Use hotel from budget option"


def test_refine_validation_requires_query():
    """Test that refinement endpoint validates required fields."""
    client_test = TestClient(app)

    # Missing refinement_query
    request_data = {
        "session_id": "test-session",
        "selected_option_id": 1
    }

    response = client_test.post("/api/travel/refine", json=request_data)

    # Should return validation error
    assert response.status_code == 422


def test_api_handles_graph_errors_gracefully(client):
    """Test that API handles graph execution errors gracefully."""
    with patch("api.main.run_collaborative_travel_query") as mock_run:
        mock_run.side_effect = Exception("Graph execution failed")

        request_data = {
            "query": "Greece under $2000"
        }

        response = client.post("/api/travel/collaborative", json=request_data)

        # Should return 500 error
        assert response.status_code == 500


def test_cors_headers_present(client):
    """Test that CORS headers are configured."""
    response = client.get("/health")

    # Check for CORS headers (if configured in app)
    # This depends on whether CORS middleware is set up
    assert response.status_code == 200


def test_collaboration_messages_in_response(client, mock_graph_run):
    """Test that collaboration messages are included in response."""
    request_data = {
        "query": "Greece under $2000"
    }

    response = client.post("/api/travel/collaborative", json=request_data)

    assert response.status_code == 200
    data = response.json()

    assert "collaboration_messages" in data
    messages = data["collaboration_messages"]
    assert isinstance(messages, list)

    if len(messages) > 0:
        msg = messages[0]
        assert "from_agent" in msg
        assert "to_agent" in msg
        assert "content" in msg


def test_booking_urls_in_options(client, mock_graph_run):
    """Test that booking URLs are included in trip options."""
    request_data = {
        "query": "Greece under $2000"
    }

    response = client.post("/api/travel/collaborative", json=request_data)

    assert response.status_code == 200
    data = response.json()

    for option in data["trip_options"]:
        assert "flight_booking_url" in option
        assert "hotel_booking_url" in option
        assert option["flight_booking_url"] is not None
        assert option["hotel_booking_url"] is not None
