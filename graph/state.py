from typing import Any, Literal

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
    flight_booking_url: str | None
    hotel_booking_url: str | None
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

    # ── Conflict lifecycle tracking ───────────────────────────────────────
    # Deterministic conflicts are the authoritative set used for routing.
    # LLM candidates are proposals only and never route unless a deterministic
    # validator accepts them (see agents/hybrid_conflict_detector.py).
    deterministic_conflicts: list[dict]
    llm_candidate_conflicts: list[dict]
    validated_llm_conflicts: list[dict]
    unverified_llm_conflicts: list[dict]

    # Lifecycle fields (populated after each hub audit).
    conflicts_current: list[dict]
    conflict_lifecycle: list[dict]
    conflicts_introduced: list[dict]
    conflicts_resolved: list[dict]
    conflicts_persisting: list[dict]
    conflicts_reopened: list[dict]
    conflict_lifecycle_state: dict[str, Any]  # serialized ConflictLifecycleTracker

    synergies: list[dict]  # Identified opportunities

    # Research results (populated in parallel, refined over rounds)
    flights: list[dict]
    selected_flight: dict | None
    flight_cost_usd: float

    hotels: list[dict]
    selected_hotel: dict | None
    hotel_cost_usd: float

    experiences: list[dict]
    top_beaches: list[str]
    top_restaurants: list[str]
    destination_context: dict | None

    weather: dict[str, Any]
    travel_month: str

    visa_safety: dict[str, Any]

    # Budget validation
    budget_breakdown: dict[str, Any]
    budget_ok: bool
    budget_retry_count: int
    budget_loop_back: bool
    tighter_budget: float | None

    # Multi-option output
    trip_options: list[TripOption]  # 3 variants: budget, balanced, premium
    selected_option_id: int | None  # User's choice (0, 1, or 2)

    # Refinement tracking
    refinement_request: str | None  # User's follow-up request
    refinement_history: list[dict]  # Track all refinements

    # Legacy single itinerary (for backwards compatibility)
    itinerary: dict[str, Any]

    # Control
    status: str
    errors: dict[str, str]

    # When False: skip Rounds 2/3 (baseline comparison mode for benchmarking)
    enable_refinement: bool

    # Feedback from constraint application (flight/hotel agents report whether
    # a collaboration constraint was satisfiable or fell back to the original
    # selection). Must be declared here or LangGraph drops it at node
    # boundaries, silently zeroing the collector's unsatisfiable rate.
    feedback_metrics: dict[str, Any]

    # Instrumentation — populated during the run, written to metrics JSONL at end
    run_metrics: dict[str, Any]
