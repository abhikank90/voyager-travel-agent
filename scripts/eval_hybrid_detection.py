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


def main():
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("Set ANTHROPIC_API_KEY first.")
    model = os.getenv("HYBRID_EVAL_MODEL", "claude-sonnet-4-5-20250929")
    client = Anthropic()
    hub = build_rules_hub()

    states = make_states()
    print(f"Model under test: {model}\n{'=' * 78}")

    consistent = 0
    agree_on_rule_conflicts = 0
    rule_conflict_states = 0
    novel_real, novel_noise = 0, 0

    for name, state, human_truth in states:
        rules = hub.detect_conflicts_only(state)
        rule_types = set(types_of(rules))

        run1 = llm_detect(client, model, state)
        run2 = llm_detect(client, model, state)
        t1, t2 = types_of(run1), types_of(run2)
        is_consistent = set(t1) == set(t2)
        consistent += is_consistent

        # Agreement: on states where rules fire, does the LLM flag something
        # involving the same agents/issue? (type labels will differ; compare
        # by whether LLM found >=1 conflict touching the same agent set)
        if rules:
            rule_conflict_states += 1
            rule_agents = {a for c in rules for a in c.get("agents", [])}
            llm_agents = {a for c in run1 for a in c.get("agents", [])}
            if rule_agents & llm_agents:
                agree_on_rule_conflicts += 1

        # Recall gain: states where rules find nothing but a human would
        if not rules and human_truth:
            if run1:
                novel_real += 1
            else:
                novel_noise += 0  # miss
        # Noise: clean state but LLM invents conflicts
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
    print(f"\n{'=' * 78}\nSUMMARY")
    print(f"  LLM self-consistency (same conflict set twice): {consistent}/{n}")
    if rule_conflict_states:
        print(f"  LLM agreement on rule-detected conflicts:       "
              f"{agree_on_rule_conflicts}/{rule_conflict_states}")
    print(f"  Rule-invisible conflicts caught by LLM:          {novel_real}/{probes}")
    print(f"  Hallucinated conflicts on clean states:          {novel_noise}")
    print("\nInterpretation guide:")
    print("  consistency < n      → LLM-only routing would be nondeterministic;")
    print("                         rules must stay as the routing layer (hybrid).")
    print("  recall gain > 0      → LLM adds real coverage → hybrid is justified")
    print("                         as 'LLM proposes, rules/schema validate'.")
    print("  hallucinations > 0   → unvalidated LLM detection would trigger")
    print("                         unnecessary re-runs and inflate cost.")


if __name__ == "__main__":
    main()
