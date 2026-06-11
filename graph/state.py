from typing import Any, Optional, Literal
from typing_extensions import TypedDict


class CollaborationMessage(TypedDict, total=False):
    """Message passed between agents during collaboration rounds."""
    from_agent: str
    to_agent: str  # Specific agent name or "all"
    message_type: Literal["insight", "constraint", "question", "proposal", "conflict"]
    content: str
    data: dict[str, Any]
    round: int


class TripOption(TypedDict, total=False):
    """One of three generated trip options."""
    option_id: int  # 0, 1, or 2
    style: Literal["budget", "balanced", "premium"]
    title: str
    description: str
    total_cost_usd: float

    # Selected options for this variant
    flight: dict[str, Any]
    hotel: dict[str, Any]
    experiences: list[dict]

    # Full itinerary
    itinerary: dict[str, Any]
    day_by_day: list[dict]

    # Booking links
    flight_booking_url: Optional[str]
    hotel_booking_url: Optional[str]
    experience_booking_urls: list[str]

    # Highlights
    highlights: list[str]
    trade_offs: list[str]


class TravelState(TypedDict, total=False):
    # Input
    user_query: str
    user_id: str
    session_id: str

    # Parsed intent
    intent: dict[str, Any]

    # User profile
    user_profile: dict[str, Any]

    # Collaboration tracking
    collaboration_round: int  # 1, 2, or 3
    agent_messages: list[CollaborationMessage]
    shared_discoveries: dict[str, Any]  # Cross-agent insights
    agent_proposals: dict[str, dict]  # Each agent's current best proposal
    conflicts: list[dict]  # Identified conflicts between agents
    synergies: list[dict]  # Identified opportunities

    # Research results (populated in parallel, refined over rounds)
    flights: list[dict]
    selected_flight: Optional[dict]
    flight_cost_usd: float

    hotels: list[dict]
    selected_hotel: Optional[dict]
    hotel_cost_usd: float

    experiences: list[dict]
    top_beaches: list[str]
    top_restaurants: list[str]
    destination_context: Optional[dict]

    weather: dict[str, Any]
    travel_month: str

    visa_safety: dict[str, Any]

    # Budget validation
    budget_breakdown: dict[str, Any]
    budget_ok: bool
    budget_retry_count: int
    budget_loop_back: bool
    tighter_budget: Optional[float]

    # Multi-option output
    trip_options: list[TripOption]  # 3 variants: budget, balanced, premium
    selected_option_id: Optional[int]  # User's choice (0, 1, or 2)

    # Refinement tracking
    refinement_request: Optional[str]  # User's follow-up request
    refinement_history: list[dict]  # Track all refinements

    # Legacy single itinerary (for backwards compatibility)
    itinerary: dict[str, Any]

    # Control
    status: str
    errors: dict[str, str]

    # When False: skip Rounds 2/3 (baseline comparison mode for benchmarking)
    enable_refinement: bool

    # Instrumentation — populated during the run, written to metrics JSONL at end
    run_metrics: dict[str, Any]
