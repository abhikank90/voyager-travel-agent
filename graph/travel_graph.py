"""
Main LangGraph state machine for Voyager Travel Agent - Collaborative Multi-Agent Design.

Flow (full mode):
  personalisation → intent_parser
      → ROUND 1: [parallel fan-out: flight, hotel, experience, weather, visa_safety]
      → collaboration_hub_1  (analyze, send messages, snapshot round-1 conflicts)
      → ROUND 2: [selective re-run of agents that received messages]
      → collaboration_hub_2  (check if conflicts resolved)
      → ROUND 3: [final optimization if still conflicting]
      → final_conflict_audit (rule-based only — no LLM, records final conflict state)
      → budget_guardrail
      → option_generator (3 variants: budget, balanced, premium)
      → END

Flow (baseline mode, enable_refinement=False):
  ... → collaboration_hub_1 → final_conflict_audit → budget_guardrail → option_generator → END
  Rounds 2 and 3 are skipped entirely; used for before/after comparison.
"""

import asyncio
import time
from typing import Literal

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langsmith import traceable

from agents import (
    BudgetGuardrailAgent,
    CollaborationHubAgent,
    ExperienceAgent,
    FlightAgent,
    HotelAgent,
    IntentParserAgent,
    ItineraryBuilderAgent,
    OptionGeneratorAgent,
    PersonalisationAgent,
    VisaSafetyAgent,
    WeatherAgent,
)
from agents.conflicts import ConflictLifecycleTracker
from graph.state import TravelState

_AGENTS_ALL = {"flight", "hotel", "experience", "weather", "visa_safety"}

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
    """Round 1: Initial research — all 5 agents run in parallel."""
    state["collaboration_round"] = 1
    t0 = time.perf_counter()

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

    existing = state.get("run_metrics") or {}
    merged["run_metrics"] = {**existing, "round_1_duration_s": round(time.perf_counter() - t0, 2)}
    return merged


async def collaboration_hub_1_node(state: TravelState) -> TravelState:
    """Round 1 hub: analyze findings, generate peer messages, snapshot conflicts."""
    result = await _collaboration_hub.run(state)

    # Preserve the Round-1 conflicts before hub_2 may overwrite state["conflicts"]
    conflicts = result.get("conflicts") if result.get("conflicts") is not None else state.get("conflicts", [])
    existing = {**(state.get("run_metrics") or {}), **(result.get("run_metrics") or {})}
    result["run_metrics"] = {**existing, "round_1_conflicts": list(conflicts)}

    # ── Lifecycle audit (Round 1) ──────────────────────────────────────────
    tracker = ConflictLifecycleTracker.from_state(state.get("conflict_lifecycle_state"))
    audit = tracker.audit(conflicts, round_num=1)
    result.update(audit)
    return result


async def research_round_2(state: TravelState) -> TravelState:
    """Round 2: Selective re-run of agents that received collaboration messages."""
    state["collaboration_round"] = 2
    t0 = time.perf_counter()

    messages = state.get("agent_messages", [])
    agents_to_rerun: set[str] = set()
    for msg in messages:
        target = msg.get("to_agent", "")
        if target != "all":
            agents_to_rerun.add(target)

    has_all_message = any(msg.get("to_agent") == "all" for msg in messages)
    full_rerun = has_all_message or len(agents_to_rerun) >= 3
    rerun_names = sorted(_AGENTS_ALL) if full_rerun else sorted(agents_to_rerun)

    if full_rerun:
        results = await asyncio.gather(
            _flight.run(state),
            _hotel.run(state),
            _experience.run(state),
            _weather.run(state),
            _visa_safety.run(state),
            return_exceptions=True,
        )
    else:
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

    existing = state.get("run_metrics") or {}
    merged["run_metrics"] = {
        **existing,
        "round_2_agents_rerun": rerun_names,
        "round_2_agents_rerun_count": len(rerun_names),
        "round_2_full_rerun": full_rerun,
        "round_2_duration_s": round(time.perf_counter() - t0, 2),
    }
    return merged


async def collaboration_hub_2_node(state: TravelState) -> TravelState:
    """Round 2 hub: check if conflicts are resolved, audit lifecycle."""
    result = await _collaboration_hub.run(state)
    conflicts = result.get("conflicts") if result.get("conflicts") is not None else state.get("conflicts", [])

    existing = {**(state.get("run_metrics") or {}), **(result.get("run_metrics") or {})}
    result["run_metrics"] = {**existing, "round_2_conflicts": list(conflicts)}

    tracker = ConflictLifecycleTracker.from_state(state.get("conflict_lifecycle_state"))
    introduced_after = state.get("run_metrics", {}).get("round_2_agents_rerun")
    audit = tracker.audit(
        conflicts,
        round_num=2,
        introduced_after_agents=list(introduced_after) if introduced_after else None,
    )
    result.update(audit)
    return result


async def research_round_3(state: TravelState) -> TravelState:
    """Round 3: Final selective optimization based on remaining conflicts."""
    state["collaboration_round"] = 3
    t0 = time.perf_counter()

    conflicts = state.get("conflicts", [])
    agents_in_conflict: set[str] = set()
    for conflict in conflicts:
        agents_in_conflict.update(conflict.get("agents", []))

    # Only flight/hotel/experience can be re-run; weather and visa_safety are
    # read-only data sources that don't benefit from a second pass here.
    # Counting agents_in_conflict directly (which can include "weather") would
    # inflate the rerun metric and corrupt the savings calculation.
    rerunnable = agents_in_conflict & {"flight", "hotel", "experience"}

    tasks = []
    if "flight" in rerunnable:
        tasks.append(_flight.run(state))
    if "hotel" in rerunnable:
        tasks.append(_hotel.run(state))
    if "experience" in rerunnable:
        tasks.append(_experience.run(state))

    results = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []

    merged: TravelState = {"collaboration_round": 3}
    for r in results:
        if isinstance(r, dict):
            merged.update(r)

    existing = state.get("run_metrics") or {}
    merged["run_metrics"] = {
        **existing,
        "round_3_agents_rerun": sorted(rerunnable),
        "round_3_agents_rerun_count": len(rerunnable),
        "round_3_duration_s": round(time.perf_counter() - t0, 2),
    }
    return merged


async def final_conflict_audit_node(state: TravelState) -> TravelState:
    """Rule-based conflict detection only — no LLM, no side effects.
    Records the true final conflict state for resolution-rate calculation and
    computes the convergence/churn summary."""
    final_conflicts = _collaboration_hub.detect_conflicts_only(state)
    existing = state.get("run_metrics") or {}

    tracker = ConflictLifecycleTracker.from_state(state.get("conflict_lifecycle_state"))
    # The final audit is a distinct snapshot. In full mode it lands on round 3
    # (after any Round-3 re-run); in baseline mode there is only Round 1.
    final_round = 3 if state.get("enable_refinement", True) else 1
    round_3_agents = state.get("run_metrics", {}).get("round_3_agents_rerun")
    audit = tracker.audit(
        final_conflicts,
        round_num=final_round,
        introduced_after_agents=list(round_3_agents) if round_3_agents else None,
    )

    result = {
        "run_metrics": {**existing, "final_conflicts": final_conflicts},
        "conflicts_current": audit["conflicts_current"],
        "conflict_lifecycle": audit["conflict_lifecycle"],
        "conflicts_introduced": audit["conflicts_introduced"],
        "conflicts_resolved": audit["conflicts_resolved"],
        "conflicts_persisting": audit["conflicts_persisting"],
        "conflicts_reopened": audit["conflicts_reopened"],
        "conflict_lifecycle_state": audit["conflict_lifecycle_state"],
    }
    result["run_metrics"]["convergence_summary"] = tracker.convergence_summary()
    return result


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
    """Build single itinerary (legacy — used for backward compatibility)."""
    return await _itinerary_builder.run(state)


# ── Routing ──────────────────────────────────────────────────────────────────
def route_after_hub_1(
    state: TravelState,
) -> Literal["research_round_2", "final_conflict_audit"]:
    """After Round-1 hub: skip refinement in baseline mode or when no conflicts."""
    if not state.get("enable_refinement", True):
        return "final_conflict_audit"
    messages = state.get("agent_messages", [])
    conflicts = state.get("conflicts", [])
    if messages or conflicts:
        return "research_round_2"
    return "final_conflict_audit"


def route_after_hub_2(
    state: TravelState,
) -> Literal["research_round_3", "final_conflict_audit"]:
    """After Round-2 hub: do Round 3 only if conflicts remain."""
    conflicts = state.get("conflicts", [])
    round_num = state.get("collaboration_round", 1)
    if conflicts and round_num < 3:
        return "research_round_3"
    return "final_conflict_audit"


# ── Graph assembly ───────────────────────────────────────────────────────────
def build_collaborative_graph() -> CompiledStateGraph:
    """Build the collaborative multi-agent graph."""
    g = StateGraph(TravelState)

    g.add_node("personalisation", personalisation_node)
    g.add_node("intent_parser", intent_parser_node)
    g.add_node("research_round_1", research_round_1)
    g.add_node("collaboration_hub_1", collaboration_hub_1_node)
    g.add_node("research_round_2", research_round_2)
    g.add_node("collaboration_hub_2", collaboration_hub_2_node)
    g.add_node("research_round_3", research_round_3)
    g.add_node("final_conflict_audit", final_conflict_audit_node)
    g.add_node("budget_guardrail", budget_guardrail_node)
    g.add_node("option_generator", option_generator_node)

    g.set_entry_point("personalisation")
    g.add_edge("personalisation", "intent_parser")
    g.add_edge("intent_parser", "research_round_1")
    g.add_edge("research_round_1", "collaboration_hub_1")

    # After Round-1 hub: full mode → Round 2; baseline mode or no conflicts → audit
    g.add_conditional_edges("collaboration_hub_1", route_after_hub_1)

    g.add_edge("research_round_2", "collaboration_hub_2")

    # After Round-2 hub: still conflicting → Round 3; otherwise → audit
    g.add_conditional_edges("collaboration_hub_2", route_after_hub_2)

    # All paths converge at final_conflict_audit before budget validation
    g.add_edge("research_round_3", "final_conflict_audit")
    g.add_edge("final_conflict_audit", "budget_guardrail")
    g.add_edge("budget_guardrail", "option_generator")
    g.add_edge("option_generator", END)

    return g.compile()


# Legacy graph for backward compatibility
def build_graph() -> CompiledStateGraph:
    """Build the legacy single-option graph (for backward compatibility)."""
    g = StateGraph(TravelState)

    g.add_node("personalisation", personalisation_node)
    g.add_node("intent_parser", intent_parser_node)
    g.add_node("research_fan_out", research_round_1)
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
travel_graph: CompiledStateGraph = build_graph()
collaborative_travel_graph: CompiledStateGraph = build_collaborative_graph()


@traceable(name="voyager_travel_query")
async def run_travel_query(user_query: str, user_id: str = "anonymous") -> dict:
    """Entry point: run the full graph for a user query (legacy single-option)."""
    initial_state: TravelState = {
        "user_query": user_query,
        "user_id": user_id,
        "budget_retry_count": 0,
        "errors": {},
    }
    return await travel_graph.ainvoke(initial_state)


@traceable(name="voyager_collaborative_query")
async def run_collaborative_travel_query(
    user_query: str,
    user_id: str = "anonymous",
    session_id: str = None,
    enable_refinement: bool = True,
    record_metrics: bool = True,
) -> dict:
    """Entry point: run collaborative multi-agent graph (generates 3 options).

    Args:
        enable_refinement: When False, skips Rounds 2/3 entirely (baseline mode).
            Used by the benchmark script to produce before/after comparisons.
        record_metrics: When False, suppresses writing to metrics/sessions.jsonl.
            Set False on the API path so live user requests don't pollute the
            benchmark dataset.
    """
    import uuid

    from metrics.collector import record_session
    from metrics.token_tracker import compute_session_cost, get_current, start_session

    if session_id is None:
        session_id = str(uuid.uuid4())

    start_session()

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
        "run_metrics": {},
        "enable_refinement": enable_refinement,
    }

    t0 = time.perf_counter()
    final_state = await collaborative_travel_graph.ainvoke(initial_state)
    duration = round(time.perf_counter() - t0, 2)

    usage = get_current()
    estimated_cost = compute_session_cost(usage) if usage else 0.0

    if record_metrics:
        record_session(
            final_state,
            query=user_query,
            duration_s=duration,
            mode="full" if enable_refinement else "baseline",
            token_usage=usage,
            estimated_cost_usd=estimated_cost,
        )
    return final_state
