"""
Integration test for the full travel graph.
Requires ANTHROPIC_API_KEY in environment (or .env).
"""
import pytest
import os
from dotenv import load_dotenv

load_dotenv()

pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping integration test",
)


@pytest.mark.asyncio
async def test_full_graph_greece():
    from graph.travel_graph import run_travel_query

    result = await run_travel_query(
        "I want a vacation in Greece under $2000 with good beaches around summer 2026"
    )

    assert result.get("intent", {}).get("destination", "").lower() == "greece"
    assert result.get("budget_breakdown") is not None
    assert result.get("itinerary") is not None


@pytest.mark.asyncio
async def test_budget_guardrail_retries():
    from graph.travel_graph import run_travel_query

    result = await run_travel_query(
        "Luxury trip to Maldives under $500 for 2 weeks"
    )

    # Should still complete (after retries), not crash
    assert result.get("status") == "complete" or result.get("itinerary") is not None
