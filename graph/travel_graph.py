"""
Main LangGraph state machine for Voyager Travel Agent - Collaborative Multi-Agent Design.

Flow:
  personalisation → intent_parser
      → ROUND 1: [parallel fan-out: flight, hotel, experience, weather, visa_safety]
      → collaboration_hub_1 (analyze, send messages)
      → ROUND 2: [parallel refinement based on peer feedback]
      → collaboration_hub_2 (check conflicts resolved)
      → ROUND 3: [final optimization if needed]
      → budget_guardrail
      → option_generator (creates 3 variants: budget, balanced, premium)
      → END
"""

import asyncio
from typing import Literal

from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from langsmith import traceable

from agents import (
    IntentParserAgent,
    FlightAgent,
    HotelAgent,
    ExperienceAgent,
    WeatherAgent,
    VisaSafetyAgent,
    BudgetGuardrailAgent,
    ItineraryBuilderAgent,
    PersonalisationAgent,
    CollaborationHubAgent,
    OptionGeneratorAgent,
)
from graph.state import TravelState


# ── Agent singletons ────────────────────────────────────────────────────────
_personalisation = PersonalisationAgent()
_intent_parser = IntentParserAgent()
_flight = FlightAgent()
_hotel = HotelAgent()
_experience = ExperienceAgent()
_weather = WeatherAgent()
_visa_safety = VisaSafetyAgent()
_budget_guardrail = BudgetGuardrailAgent()
_itinerary_builder = ItineraryBuilderAgent()
_collaboration_hub = CollaborationHubAgent()
_option_generator = OptionGeneratorAgent()


# ── Node functions ───────────────────────────────────────────────────────────
async def personalisation_node(state: TravelState) -> TravelState:
    return await _personalisation.run(state)


async def intent_parser_node(state: TravelState) -> TravelState:
    return await _intent_parser.run(state)


async def research_round_1(state: TravelState) -> TravelState:
    """Round 1: Initial research - all 5 agents run in parallel."""
    # Set round number
    state["collaboration_round"] = 1

    results = await asyncio.gather(
        _flight.run(state),
        _hotel.run(state),
        _experience.run(state),
        _weather.run(state),
        _visa_safety.run(state),
        return_exceptions=True,
    )

    merged: TravelState = {"collaboration_round": 1}
    for r in results:
        if isinstance(r, dict):
            merged.update(r)
        # exceptions are logged by base_agent; we silently skip them here
    return merged


async def collaboration_hub_node(state: TravelState) -> TravelState:
    """Run collaboration hub to analyze findings and generate messages."""
    return await _collaboration_hub.run(state)


async def research_round_2(state: TravelState) -> TravelState:
    """Round 2: Refinement based on collaboration messages."""
    # Update round number
    state["collaboration_round"] = 2

    # Re-run agents that received messages
    messages = state.get("agent_messages", [])
    agents_to_rerun = set()

    for msg in messages:
        target = msg.get("to_agent", "")
        if target != "all":
            agents_to_rerun.add(target)

    # Run targeted agents or all if "all" was targeted
    has_all_message = any(msg.get("to_agent") == "all" for msg in messages)

    if has_all_message or len(agents_to_rerun) >= 3:
        # Re-run all research agents
        results = await asyncio.gather(
            _flight.run(state),
            _hotel.run(state),
            _experience.run(state),
            _weather.run(state),
            _visa_safety.run(state),
            return_exceptions=True,
        )
    else:
        # Selectively re-run only agents that need refinement
        tasks = []
        if "flight" in agents_to_rerun:
            tasks.append(_flight.run(state))
        if "hotel" in agents_to_rerun:
            tasks.append(_hotel.run(state))
        if "experience" in agents_to_rerun:
            tasks.append(_experience.run(state))
        if "weather" in agents_to_rerun:
            tasks.append(_weather.run(state))
        if "visa_safety" in agents_to_rerun:
            tasks.append(_visa_safety.run(state))

        results = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []

    merged: TravelState = {"collaboration_round": 2}
    for r in results:
        if isinstance(r, dict):
            merged.update(r)

    return merged


async def research_round_3(state: TravelState) -> TravelState:
    """Round 3: Final optimization (if needed)."""
    state["collaboration_round"] = 3

    # Run targeted refinements based on remaining conflicts
    conflicts = state.get("conflicts", [])

    if not conflicts:
        # No conflicts, just pass through
        return {"collaboration_round": 3}

    # Re-run only agents involved in conflicts
    tasks = []
    agents_in_conflict = set()
    for conflict in conflicts:
        agents_in_conflict.update(conflict.get("agents", []))

    if "flight" in agents_in_conflict:
        tasks.append(_flight.run(state))
    if "hotel" in agents_in_conflict:
        tasks.append(_hotel.run(state))
    if "experience" in agents_in_conflict:
        tasks.append(_experience.run(state))

    results = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []

    merged: TravelState = {"collaboration_round": 3}
    for r in results:
        if isinstance(r, dict):
            merged.update(r)

    return merged


async def budget_guardrail_node(state: TravelState) -> TravelState:
    return await _budget_guardrail.run(state)


async def option_generator_node(state: TravelState) -> TravelState:
    """Generate 3 trip options: budget, balanced, premium."""
    return await _option_generator.run(state)


# Legacy nodes for backward compatibility
async def retry_research_node(state: TravelState) -> TravelState:
    """Re-run flight + hotel with tighter budget constraint (legacy)."""
    tighter = state.get("tighter_budget", state["intent"]["budget_usd"] * 0.80)
    state["intent"]["budget_usd"] = tighter
    results = await asyncio.gather(
        _flight.run(state),
        _hotel.run(state),
        return_exceptions=True,
    )
    merged: TravelState = {}
    for r in results:
        if isinstance(r, dict):
            merged.update(r)
    return merged


async def itinerary_builder_node(state: TravelState) -> TravelState:
    """Build single itinerary (legacy - used for backward compatibility)."""
    return await _itinerary_builder.run(state)


# ── Routing ──────────────────────────────────────────────────────────────────
def route_after_hub_1(state: TravelState) -> Literal["research_round_2", "budget_guardrail"]:
    """After first collaboration, decide if we need round 2."""
    messages = state.get("agent_messages", [])
    conflicts = state.get("conflicts", [])

    # If there are messages or conflicts, do round 2
    if messages or conflicts:
        return "research_round_2"
    else:
        # Skip to budget check
        return "budget_guardrail"


def route_after_hub_2(state: TravelState) -> Literal["research_round_3", "budget_guardrail"]:
    """After second collaboration, decide if we need round 3."""
    conflicts = state.get("conflicts", [])
    round_num = state.get("collaboration_round", 1)

    # If still have conflicts and we haven't done round 3 yet
    if conflicts and round_num < 3:
        return "research_round_3"
    else:
        return "budget_guardrail"


# ── Graph assembly ───────────────────────────────────────────────────────────
def build_collaborative_graph() -> CompiledStateGraph:
    """Build the new collaborative multi-agent graph."""
    g = StateGraph(TravelState)

    # Add all nodes
    g.add_node("personalisation", personalisation_node)
    g.add_node("intent_parser", intent_parser_node)

    # Research rounds
    g.add_node("research_round_1", research_round_1)
    g.add_node("collaboration_hub_1", collaboration_hub_node)
    g.add_node("research_round_2", research_round_2)
    g.add_node("collaboration_hub_2", collaboration_hub_node)
    g.add_node("research_round_3", research_round_3)

    # Final stages
    g.add_node("budget_guardrail", budget_guardrail_node)
    g.add_node("option_generator", option_generator_node)

    # Wire the graph
    g.set_entry_point("personalisation")
    g.add_edge("personalisation", "intent_parser")
    g.add_edge("intent_parser", "research_round_1")
    g.add_edge("research_round_1", "collaboration_hub_1")

    # Conditional: Need round 2?
    g.add_conditional_edges("collaboration_hub_1", route_after_hub_1)

    # After round 2
    g.add_edge("research_round_2", "collaboration_hub_2")

    # Conditional: Need round 3?
    g.add_conditional_edges("collaboration_hub_2", route_after_hub_2)

    # Final path
    g.add_edge("research_round_3", "budget_guardrail")
    g.add_edge("budget_guardrail", "option_generator")
    g.add_edge("option_generator", END)

    return g.compile()


# Legacy graph for backward compatibility
def build_graph() -> CompiledStateGraph:
    """Build the legacy single-option graph (for backward compatibility)."""
    g = StateGraph(TravelState)

    g.add_node("personalisation", personalisation_node)
    g.add_node("intent_parser", intent_parser_node)
    g.add_node("research_fan_out", research_round_1)  # Use round_1 as fan_out
    g.add_node("budget_guardrail", budget_guardrail_node)
    g.add_node("retry_research", retry_research_node)
    g.add_node("itinerary_builder", itinerary_builder_node)

    g.set_entry_point("personalisation")
    g.add_edge("personalisation", "intent_parser")
    g.add_edge("intent_parser", "research_fan_out")
    g.add_edge("research_fan_out", "budget_guardrail")

    def route_budget(state: TravelState) -> Literal["retry_research", "itinerary_builder"]:
        if state.get("budget_loop_back") and state.get("budget_retry_count", 0) <= 2:
            return "retry_research"
        return "itinerary_builder"

    g.add_conditional_edges("budget_guardrail", route_budget)
    g.add_edge("retry_research", "budget_guardrail")
    g.add_edge("itinerary_builder", END)

    return g.compile()


# Compiled graphs
travel_graph: CompiledStateGraph = build_graph()  # Legacy
collaborative_travel_graph: CompiledStateGraph = build_collaborative_graph()  # New default


@traceable(name="voyager_travel_query")
async def run_travel_query(user_query: str, user_id: str = "anonymous") -> dict:
    """Entry point: run the full graph for a user query (legacy single-option)."""
    initial_state: TravelState = {
        "user_query": user_query,
        "user_id": user_id,
        "budget_retry_count": 0,
        "errors": {},
    }
    final_state = await travel_graph.ainvoke(initial_state)
    return final_state


@traceable(name="voyager_collaborative_query")
async def run_collaborative_travel_query(
    user_query: str,
    user_id: str = "anonymous",
    session_id: str = None
) -> dict:
    """Entry point: run collaborative multi-agent graph (generates 3 options)."""
    import uuid
    if session_id is None:
        session_id = str(uuid.uuid4())

    initial_state: TravelState = {
        "user_query": user_query,
        "user_id": user_id,
        "session_id": session_id,
        "collaboration_round": 0,
        "budget_retry_count": 0,
        "agent_messages": [],
        "conflicts": [],
        "synergies": [],
        "errors": {},
        "refinement_history": [],
    }
    final_state = await collaborative_travel_graph.ainvoke(initial_state)
    return final_state
