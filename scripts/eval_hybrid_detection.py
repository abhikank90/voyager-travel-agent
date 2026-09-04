"""Evaluate whether an LLM-augmented conflict detector adds value over rules.

Answers three questions for the InfoQ article (and the roadmap item in
collaboration_hub._identify_conflicts):

  1. AGREEMENT  — does the LLM find the conflicts the rules find?
  2. RECALL GAIN — does the LLM find real conflicts the rules cannot see?
  3. CONSISTENCY — does the LLM return the same conflicts across repeated runs?
                   (Rules are deterministic by construction; this measures what
                   we'd give up by trusting the LLM for routing.)

Usage:
    ANTHROPIC_API_KEY=sk-... python scripts/eval_hybrid_detection.py
    # optional: HYBRID_EVAL_MODEL=claude-haiku-4-5-20251001 to test a cheaper detector

Cost: ~16 LLM calls (8 states x 2 runs), small prompts. A few cents.
"""

import json
import os
import sys
from collections import Counter
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from anthropic import Anthropic  # noqa: E402


# ── Rule-based detector (LLM narrative call mocked out, rules untouched) ─────

def build_rules_hub():
    from agents.collaboration_hub import CollaborationHubAgent
    with patch("agents.collaboration_hub.Anthropic"), \
         patch("agents.collaboration_hub.get_api_config") as cfg:
        cfg.return_value.llm.api_key = "unused"
        cfg.return_value.llm.collaboration_hub_model = "unused"
        return CollaborationHubAgent()


# ── Evaluation states ─────────────────────────────────────────────────────────
# Each: (name, state, conflicts_a_human_would_flag) — the last field is the
# ground truth used to judge LLM "extras" as real recall vs. noise.

def _base():
    return {
        "intent": {"destination": "Greece", "budget_usd": 2000,
                   "interests": ["beaches"], "travel_month": "July 2026"},
        "collaboration_round": 1,
        "selected_hotel": {"name": "Santorini Resort", "location": "Santorini",
                           "total_usd": 700},
        "experiences": [
            {"name": "Red Beach", "category": "beach", "location": "Santorini"},
            {"name": "Oia Walk", "category": "culture", "location": "Santorini"},
            {"name": "Taverna", "category": "food", "location": "Santorini"},
        ],
        "selected_flight": {"airline": "LH", "arrival": "2026-07-01T13:00:00",
                            "price_usd": 890},
        "weather": {"avg_temp_c": 28, "summary": "warm", "precipitation_mm": 2},
        "visa_safety": {"visa_required": False, "safety_level": "safe"},
        "flights": [], "hotels": [], "agent_messages": [], "conflicts": [],
    }


def make_states():
    states = []

    s = _base()
    states.append(("clean_no_conflicts", s, set()))

    s = _base()
    s["selected_hotel"] = {"name": "Aegean Bliss", "location": "Beachfront",
                           "total_usd": 595}
    s["experiences"] = [
        {"name": "Sunset", "category": "culture", "location": "Oia, Santorini"},
        {"name": "Boat Tour", "category": "outdoor", "location": "Fira center"},
        {"name": "Dinner", "category": "food", "location": "Oia village"},
    ]
    states.append(("location_mismatch", s, {"location_mismatch"}))

    s = _base()
    s["selected_flight"] = {"airline": "UA", "arrival": "2026-07-01T22:30:00",
                            "price_usd": 680}
    states.append(("late_arrival_timing", s, {"timing_inefficiency"}))

    s = _base()
    s["weather"] = {"avg_temp_c": 35, "summary": "extreme heat wave",
                    "precipitation_mm": 0}
    s["experiences"] = [
        {"name": "Red Beach Day", "category": "beach", "location": "Santorini"},
        {"name": "Outdoor Hike", "category": "outdoor",
         "description": "outdoor cliff trail", "location": "Santorini"},
        {"name": "Taverna", "category": "food", "location": "Santorini"},
    ]
    states.append(("weather_vs_outdoor", s, {"weather_activity_mismatch"}))

    # ── Conflicts the rules CANNOT currently see (recall-gain probes) ────────
    s = _base()
    s["selected_flight"] = {"airline": "UA", "arrival": "2026-07-01T23:40:00",
                            "price_usd": 680}
    s["selected_hotel"] = {"name": "Boutique Inn", "location": "Santorini",
                           "total_usd": 700, "front_desk_hours": "07:00-22:00"}
    states.append(("arrival_after_desk_close", s, {"checkin_impossible"}))

    s = _base()
    s["selected_flight"]["price_usd"] = 1200
    s["selected_hotel"]["total_usd"] = 1100
    # 1200 + 1100 = 2300 > 2000 budget; rules don't sum components here
    states.append(("component_sum_over_budget", s, {"budget_violation"}))

    s = _base()
    s["visa_safety"] = {"visa_required": True, "processing_days": 30,
                        "safety_level": "safe"}
    s["intent"]["travel_month"] = "July 2026"
    s["intent"]["booking_date"] = "2026-06-20"  # 11 days before travel
    states.append(("visa_lead_time_too_short", s, {"visa_timing"}))

    s = _base()
    s["intent"]["interests"] = ["vegetarian fine dining"]
    s["experiences"] = [
        {"name": "Seafood Grill Crawl", "category": "food",
         "description": "five-stop seafood tasting", "location": "Santorini"},
        {"name": "Octopus BBQ", "category": "food",
         "description": "traditional seafood barbecue", "location": "Santorini"},
        {"name": "Oia Walk", "category": "culture", "location": "Santorini"},
    ]
    states.append(("preference_contradiction", s, {"preference_mismatch"}))

    return states


# ── LLM detector ──────────────────────────────────────────────────────────────

DETECT_PROMPT = """You are the conflict detector in a multi-agent travel planning system.
Below are the combined findings of independent specialist agents (flight, hotel,
experience, weather, visa/safety) for one user query.

Identify CONFLICTS ONLY: places where the combined plan is internally
inconsistent, violates a stated user constraint, or is physically/logistically
impossible. Do not list improvements, synergies, or style preferences.

Respond with ONLY a JSON array (no prose, no markdown fences). Each element:
{{"type": "<short_snake_case_label>", "agents": ["<agent>", ...], "description": "<one sentence>"}}
Return [] if there are no conflicts.

Combined agent findings:
{state_json}
"""


def llm_detect(client, model, state):
    prompt = DETECT_PROMPT.format(state_json=json.dumps(state, indent=2))
    resp = client.messages.create(
        model=model, max_tokens=1000, temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
    )
    text = resp.content[0].text.strip()
    if text.startswith("```"):
        text = text.strip("`").lstrip("json").strip()
    try:
        out = json.loads(text)
        return out if isinstance(out, list) else []
    except json.JSONDecodeError:
        return [{"type": "UNPARSEABLE", "agents": [], "description": text[:120]}]


def types_of(conflicts):
    return Counter(c.get("type", "?") for c in conflicts)


def _to_candidates(conflicts):
    """Convert the eval LLM dicts into strict ``ConflictCandidate`` objects.

    Returns ``None`` for a schema-invalid conflict (missing type/agents).
    """
    from agents.hybrid_conflict_detector import ConflictCandidate

    candidates = []
    for c in conflicts:
        if not isinstance(c, dict) or "type" not in c or "agents" not in c:
            continue
        try:
            candidates.append(ConflictCandidate(
                conflict_type=c.get("type", ""),
                agents=c.get("agents", []) if isinstance(c.get("agents"), list) else [],
                hypothesis=c.get("description", ""),
                evidence=[c.get("description", "")],
                suggested_rule=None,
                confidence=float(c.get("confidence", 0.5)),
            ))
        except Exception:
            continue
    return candidates


def main():
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY first.")
    model = os.getenv("HYBRID_EVAL_MODEL", "claude-sonnet-4-5-20250929")
    client = Anthropic()
    hub = build_rules_hub()

    from agents.hybrid_conflict_detector import HybridConflictDetector
    detector = HybridConflictDetector(hub)

    states = make_states()
    print(f"Model under test: {model}\n{'=' * 78}")

    # ── Aggregate counters (Priority 2.5 expanded output) ──────────────────
    total_rule_conflicts = 0
    total_llm_candidates = 0
    exact_agreement = 0          # LLM candidate type exactly matches a rule type
    missed_by_llm = 0            # rule conflict with no LLM candidate touching it
    extra_llm_candidates = 0     # LLM candidates whose type the rules did NOT emit
    validated_extra = 0          # extras accepted by a deterministic validator
    unverified_extra = 0         # extras rejected by every validator
    consistent = 0
    agree_on_rule_conflicts = 0
    rule_conflict_states = 0
    novel_real, novel_noise = 0, 0

    for name, state, human_truth in states:
        rules = hub.detect_conflicts_only(state)
        rule_types = set(types_of(rules))
        rule_agents = {a for c in rules for a in c.get("agents", [])}
        total_rule_conflicts += len(rules)

        run1 = llm_detect(client, model, state)
        run2 = llm_detect(client, model, state)
        t1, t2 = types_of(run1), types_of(run2)
        is_consistent = set(t1) == set(t2)
        consistent += is_consistent

        llm_types = set(t1)
        llm_agents = {a for c in run1 for a in c.get("agents", [])}
        total_llm_candidates += len(run1)

        # Agreement + extras vs rules
        if rules:
            rule_conflict_states += 1
            if rule_agents & llm_agents:
                agree_on_rule_conflicts += 1

        exact_agreement += len(rule_types & llm_types)
        missed_by_llm += len(rule_types - llm_types)
        extra_types = llm_types - rule_types
        extra_llm_candidates += len(extra_types)

        # ── Deterministic validation of *extra* candidates ─────────────────
        candidates = _to_candidates(run1)
        extras = [c for c in candidates if c.conflict_type in extra_types]
        validated, unverified = detector.validate(extras, state)
        validated_extra += len(validated)
        unverified_extra += len(unverified)

        # Recall gain / noise (unchanged semantics)
        if not rules and human_truth:
            if run1:
                novel_real += 1
        if not rules and not human_truth and run1:
            novel_noise += 1

        print(f"\n[{name}]")
        print(f"  rules : {sorted(rule_types) or '—'}")
        print(f"  llm r1: {sorted(set(t1)) or '—'}")
        print(f"  llm r2: {sorted(set(t2)) or '—'}   consistent={is_consistent}")
        print(f"  human : {sorted(human_truth) or '—'}")

    n = len(states)
    probes = sum(1 for _, s, t in states
                 if t and not build_rules_hub().detect_conflicts_only(s))

    # ── Precision / recall / FPR over candidate counts ─────────────────────
    precision = round(exact_agreement / total_llm_candidates, 3) if total_llm_candidates else 0.0
    recall = round(exact_agreement / total_rule_conflicts, 3) if total_rule_conflicts else 0.0
    fpr = round(unverified_extra / total_llm_candidates, 3) if total_llm_candidates else 0.0
    self_consistency = round(consistent / n, 3) if n else 0.0

    print(f"\n{'=' * 78}\nSUMMARY")
    print(f"  rule_conflicts:            {total_rule_conflicts}")
    print(f"  llm_candidates:            {total_llm_candidates}")
    print(f"  exact_agreement:           {exact_agreement}")
    print(f"  missed_by_llm:             {missed_by_llm}")
    print(f"  extra_llm_candidates:      {extra_llm_candidates}")
    print(f"  validated_extra_conflicts: {validated_extra}")
    print(f"  unverified_extra_candidates: {unverified_extra}")
    print(f"  precision:                 {precision}")
    print(f"  recall:                    {recall}")
    print(f"  false_positive_rate:       {fpr}")
    print(f"  self_consistency:          {self_consistency}")
    print(f"  (LLM agreement on rule-detected conflicts: "
          f"{agree_on_rule_conflicts}/{rule_conflict_states})")
    print(f"  (Rule-invisible conflicts caught by LLM: {novel_real}/{probes})")
    print(f"  (Hallucinated conflicts on clean states: {novel_noise})")

    print("\nInterpretation guide:")
    print("  consistency < n      → LLM-only routing would be nondeterministic;")
    print("                         rules must stay as the routing layer (hybrid).")
    print("  recall gain > 0      → LLM adds real coverage → hybrid is justified")
    print("                         as 'LLM proposes, rules/schema validate'.")
    print("  validated_extra      → extras that earned routing authority via rules.")
    print("  unverified_extra     → extras that must NOT route (false-positive risk).")
    print("  hallucinations > 0   → unvalidated LLM detection would trigger")
    print("                         unnecessary re-runs and inflate cost.")


if __name__ == "__main__":
    main()
