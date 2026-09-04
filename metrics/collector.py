"""
Session metrics collector for Voyager's collaborative multi-agent system.

One JSONL record per session written to metrics/sessions.jsonl.
Each record contains everything the article cites:
  - Conflict rate (% of Round-1 queries that had conflicts)
  - Conflict resolution rate (% of Round-1 conflicts resolved by refinement)
  - Selective re-execution savings vs. naive full re-run
  - Token usage and estimated USD cost
  - Per-round latencies (proves selective re-run saves cost, not wall-clock time)
  - Mode: "full" (with refinement) or "baseline" (without)

Run scripts/benchmark_queries.py --mode compare to populate both modes, then
call print_summary() to produce the before/after table for the article.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_METRICS_DIR = Path(__file__).parent
_SESSIONS_FILE = _METRICS_DIR / "sessions.jsonl"
_RESULTS_DIR = Path(__file__).parent.parent / "results"
_RESULTS_SCHEMA_VERSION = "2"
_RESEARCH_AGENTS_COUNT = 5

# Maps each typed conflict to the hub message that carries its evidence payload.
# Each conflict type has exactly one corresponding message: (to_agent, message_type).
_CONFLICT_TO_MSG: dict[str, tuple[str, str]] = {
    "location_mismatch":         ("hotel",      "constraint"),
    "timing_inefficiency":       ("flight",     "insight"),
    "weather_activity_mismatch": ("experience", "constraint"),
}


def _default_convergence(run_metrics: dict[str, Any]) -> dict[str, Any]:
    """Fallback convergence summary for sessions recorded without the tracker.

    Preserves compatibility with older session records that predate the
    conflict-lifecycle instrumentation.
    """
    round_1: list[dict] = run_metrics.get("round_1_conflicts", [])
    final: list[dict] = run_metrics.get("final_conflicts", [])
    r1_count = len(round_1)
    final_count = len(final)
    resolved = max(0, r1_count - final_count)
    return {
        "round_1_conflicts": r1_count,
        "round_2_conflicts_remaining": None,
        "round_3_conflicts_remaining": final_count,
        "resolved_by_round_2": None,
        "resolved_by_round_3": resolved,
        "introduced_post_refinement": 0,
        "reopened": 0,
        "persisting_at_final_audit": final_count,
        "converged_round": None,
    }


def record_session(
    final_state: dict,
    query: str,
    duration_s: float,
    mode: str = "full",
    token_usage=None,
    estimated_cost_usd: float = 0.0,
) -> None:
    """Extract all metrics from a completed run and append to sessions.jsonl."""
    conflicts: list[dict] = final_state.get("conflicts", []) or []
    messages: list[dict] = final_state.get("agent_messages", []) or []
    synergies: list[dict] = final_state.get("synergies", []) or []
    run_metrics: dict[str, Any] = final_state.get("run_metrics", {}) or {}

    # ── Round 1 snapshot (preserved before refinement overwrites) ──────────
    round_1_conflicts: list[dict] = run_metrics.get("round_1_conflicts", conflicts)

    # ── Final conflict state (after all refinement rounds) ─────────────────
    final_conflicts: list[dict] = run_metrics.get("final_conflicts", [])

    # ── Lifecycle / churn (computed by the graph's ConflictLifecycleTracker) ──
    lifecycle: list[dict] = final_state.get("conflict_lifecycle", []) or []
    introduced: list[dict] = final_state.get("conflicts_introduced", []) or []
    resolved: list[dict] = final_state.get("conflicts_resolved", []) or []
    persisting: list[dict] = final_state.get("conflicts_persisting", []) or []
    reopened: list[dict] = final_state.get("conflicts_reopened", []) or []
    convergence = run_metrics.get("convergence_summary", _default_convergence(run_metrics))
    llm_candidates: list[dict] = final_state.get("llm_candidate_conflicts", []) or []
    validated: list[dict] = final_state.get("validated_llm_conflicts", []) or []
    unverified: list[dict] = final_state.get("unverified_llm_conflicts", []) or []

    # ── Conflict resolution rate ───────────────────────────────────────────
    r1_count = len(round_1_conflicts)
    final_count = len(final_conflicts)
    resolved_count = max(0, r1_count - final_count)
    resolution_rate_pct = round(resolved_count / r1_count * 100) if r1_count > 0 else None

    # ── Selective re-execution savings ────────────────────────────────────
    r2_count = run_metrics.get("round_2_agents_rerun_count", 0)
    r3_count = run_metrics.get("round_3_agents_rerun_count", 0)
    round_2_triggered = r2_count > 0
    round_3_triggered = r3_count > 0

    actual_calls = _RESEARCH_AGENTS_COUNT + r2_count + r3_count
    rounds_used = 1 + (1 if round_2_triggered else 0) + (1 if round_3_triggered else 0)
    naive_calls = _RESEARCH_AGENTS_COUNT * rounds_used
    savings_pct = round((1 - actual_calls / naive_calls) * 100) if naive_calls > 0 else 0

    # ── Conflict evidence: join each conflict to its message payload ──────
    # Round-1 hub messages carry the structured data (activity_locations,
    # preferred_arrival, weather_concerns, etc.) that explain WHY each conflict fired.
    # Conflict dicts from _identify_conflicts have no data field; we recover the
    # payload here by matching conflict type → (to_agent, message_type).
    r1_msg_data: dict[tuple[str, str], dict] = {}
    for msg in messages:
        if msg.get("round") == 1 and msg.get("from_agent") == "collaboration_hub":
            key = (msg.get("to_agent", ""), msg.get("message_type", ""))
            if key[0] and msg.get("data"):
                r1_msg_data[key] = msg["data"]

    # ── Token usage ───────────────────────────────────────────────────────
    token_data: dict[str, Any] = {}
    if token_usage is not None:
        token_data = {
            "input_tokens": token_usage.input_tokens,
            "output_tokens": token_usage.output_tokens,
            "total_tokens": token_usage.total_tokens,
            "estimated_cost_usd": estimated_cost_usd,
            "per_model_tokens": {m: dict(v) for m, v in token_usage.per_model.items()},
        }

    # ── Per-round latencies ───────────────────────────────────────────────
    round_durations = {
        k: run_metrics[k]
        for k in ("round_1_duration_s", "round_2_duration_s", "round_3_duration_s")
        if k in run_metrics
    }

    record = {
        "session_id": final_state.get("session_id", ""),
        "query": query,
        "timestamp": datetime.now(UTC).isoformat(),
        "duration_s": duration_s,
        "mode": mode,

        # Conflict data
        "had_conflict": r1_count > 0,
        "round_1_conflict_count": r1_count,
        "round_1_conflict_types": [c.get("type") for c in round_1_conflicts],
        "round_1_conflict_severities": [c.get("severity") for c in round_1_conflicts],
        "round_1_conflicts_evidence": [
            {
                "type": c.get("type"),
                "severity": c.get("severity"),
                "data": r1_msg_data.get(_CONFLICT_TO_MSG.get(c.get("type", ""), ("", "")), {}),
            }
            for c in round_1_conflicts
        ],
        "round_1_messages_sent": len(messages),
        "round_1_agents_targeted": sorted({m.get("to_agent") for m in messages if m.get("to_agent") != "all"}),
        "synergy_count": len(synergies),

        # Final state
        "final_conflict_count": final_count,
        "conflicts_resolved_count": resolved_count,
        "conflict_resolution_rate_pct": resolution_rate_pct,

        # Round 2 selective re-execution
        "round_2_triggered": round_2_triggered,
        "round_2_agents_rerun": run_metrics.get("round_2_agents_rerun", []),
        "round_2_agents_rerun_count": r2_count,
        "round_2_full_rerun": run_metrics.get("round_2_full_rerun", False),

        # Round 3 selective re-execution
        "round_3_triggered": round_3_triggered,
        "round_3_agents_rerun": run_metrics.get("round_3_agents_rerun", []),
        "round_3_agents_rerun_count": r3_count,

        # Efficiency
        "rounds_used": rounds_used,
        "actual_agent_calls": actual_calls,
        "naive_full_rerun_calls": naive_calls,
        "selective_rerun_savings_pct": savings_pct,

        # Token + cost
        **token_data,

        # Per-round latencies
        "round_durations": round_durations,

        # Budget
        "budget_ok": final_state.get("budget_ok", False),
        "budget_retry_count": final_state.get("budget_retry_count", 0),
        "errors": list((final_state.get("errors") or {}).keys()),

        # Schema version — makes later analysis scripts safe against drift
        "results_schema_version": _RESULTS_SCHEMA_VERSION,

        # ── Conflict churn & convergence ──────────────────────────────────
        "convergence_summary": convergence,
        "conflicts_introduced_count": len(introduced),
        "lifecycle_resolved_total": len(resolved),
        "conflicts_persisting_count": len(persisting),
        "conflicts_reopened_count": len(reopened),
        "conflict_lifecycle": lifecycle,
        "conflicts_introduced": introduced,
        "conflicts_resolved": resolved,
        "conflicts_persisting": persisting,
        "conflicts_reopened": reopened,

        # ── Hybrid detector isolation ─────────────────────────────────────
        "llm_candidate_conflicts": llm_candidates,
        "validated_llm_conflicts": validated,
        "unverified_llm_conflicts": unverified,
        "llm_candidate_count": len(llm_candidates),
        "validated_llm_count": len(validated),
        "unverified_llm_count": len(unverified),

        # ── Unsatisfiable feedback conditions ─────────────────────────────
        "feedback_metrics": final_state.get("feedback_metrics", {}),
    }

    _SESSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_SESSIONS_FILE, "a") as f:
        f.write(json.dumps(record) + "\n")


def load_sessions(mode: str | None = None) -> list[dict]:
    """Load recorded sessions, optionally filtered by mode ('full' or 'baseline')."""
    if not _SESSIONS_FILE.exists():
        return []
    sessions = []
    with open(_SESSIONS_FILE) as f:
        for line in f:
            if line.strip():
                s = json.loads(line)
                if mode is None or s.get("mode") == mode:
                    sessions.append(s)
    return sessions


def _avg(values: list[float | int], decimals: int = 1) -> float:
    return round(sum(values) / len(values), decimals) if values else 0.0


def _pct(count: int, total: int) -> int:
    return round(count / total * 100) if total > 0 else 0


def print_summary() -> None:
    """Print article-ready summary statistics, split by mode with before/after table."""
    full = load_sessions(mode="full")
    baseline = load_sessions(mode="baseline")
    all_sessions = full + baseline

    if not all_sessions:
        print("No sessions recorded yet. Run scripts/benchmark_queries.py first.")
        return

    def _section(sessions: list[dict], label: str) -> None:
        n = len(sessions)
        if n == 0:
            print(f"\n  No {label} sessions recorded.")
            return

        with_conflict = [s for s in sessions if s["had_conflict"]]
        r2 = [s for s in sessions if s["round_2_triggered"]]
        r3 = [s for s in sessions if s["round_3_triggered"]]
        savings = [
            s["selective_rerun_savings_pct"]
            for s in sessions
            if s["round_2_triggered"] or s["round_3_triggered"]
        ]
        resolution_rates = [
            s["conflict_resolution_rate_pct"]
            for s in sessions
            if s.get("conflict_resolution_rate_pct") is not None
        ]

        print(f"\n  {'─'*54}")
        print(f"  {label.upper()} MODE  ({n} sessions)")
        print(f"  {'─'*54}")

        print("\n  CONFLICT RATE")
        print(f"  Queries with ≥1 Round-1 conflict  {len(with_conflict):>3}/{n}  ({_pct(len(with_conflict), n)}%)")
        print(f"  Queries triggering Round 2         {len(r2):>3}/{n}  ({_pct(len(r2), n)}%)")
        print(f"  Queries triggering Round 3         {len(r3):>3}/{n}  ({_pct(len(r3), n)}%)")
        avg_r1 = _avg([s["round_1_conflict_count"] for s in with_conflict])
        print(f"  Avg Round-1 conflicts per query    {avg_r1}")

        if resolution_rates:
            print("\n  CONFLICT RESOLUTION  (full mode only)")
            print(f"  Overall resolution rate            {_avg(resolution_rates, 0):.0f}%")
            type_r1: dict[str, int] = {}
            for s in sessions:
                for ct in s.get("round_1_conflict_types", []):
                    type_r1[ct] = type_r1.get(ct, 0) + 1
            if type_r1:
                print("  Conflict types detected:")
                for ctype, count in sorted(type_r1.items(), key=lambda x: -x[1]):
                    print(f"    {ctype:<38} {count:>3}  ({_pct(count, n)}% of queries)")

        if savings:
            print("\n  SELECTIVE RE-EXECUTION EFFICIENCY")
            print(f"  Avg agent-call savings vs full re-run  {_avg(savings, 0):.0f}%")
            print(f"  (sessions with Round 2/3, n={len(savings)})")

        avg_final = _avg([s["final_conflict_count"] for s in sessions])
        avg_r1_count = _avg([s["round_1_conflict_count"] for s in sessions])
        print("\n  CONFLICT COUNTS")
        print(f"  Avg Round-1 conflicts/query   {avg_r1_count}")
        print(f"  Avg final conflicts/query     {avg_final}")

        # ── Churn & convergence (full mode only) ──────────────────────────
        converged = [
            s["convergence_summary"]["converged_round"]
            for s in sessions
            if s.get("convergence_summary", {}).get("converged_round") is not None
        ]
        introduced = [s["conflicts_introduced_count"] for s in sessions]
        reopened = [s["conflicts_reopened_count"] for s in sessions]
        if converged:
            print("\n  CONVERGENCE  (full mode only)")
            print(f"  Mean convergence round           {_avg(converged, 2)}")
            r1_only = sum(
                1 for s in sessions
                if s.get("convergence_summary", {}).get("converged_round") == 1
            )
            r2_conv = sum(
                1 for s in sessions
                if s.get("convergence_summary", {}).get("converged_round") == 2
            )
            r3_conv = sum(
                1 for s in sessions
                if s.get("convergence_summary", {}).get("converged_round") == 3
            )
            print(f"  Converged after Round 1         {r1_only}/{n}")
            print(f"  Converged after Round 2         {r2_conv}/{n}")
            print(f"  Converged after Round 3         {r3_conv}/{n}")
            print(f"  Post-refinement introductions   {sum(introduced)} total ({_avg(introduced, 2)}/query)")
            print(f"  Reopened conflicts              {sum(reopened)} total ({_avg(reopened, 2)}/query)")

        costs = [s["estimated_cost_usd"] for s in sessions if s.get("estimated_cost_usd")]
        if costs:
            print("\n  TOKEN USAGE")
            avg_in = _avg([s.get("input_tokens", 0) for s in sessions], 0)
            avg_out = _avg([s.get("output_tokens", 0) for s in sessions], 0)
            print(f"  Avg input tokens/query    {avg_in:>7,.0f}")
            print(f"  Avg output tokens/query   {avg_out:>7,.0f}")
            print(f"  Avg cost/query            ${_avg(costs, 4):.4f}")

        durations = [s["duration_s"] for s in sessions]
        print("\n  LATENCY")
        print(f"  Avg end-to-end duration   {_avg(durations)}s")

        def _round_dur(key: str) -> list:
            return [
                s["round_durations"].get(key)
                for s in sessions
                if s.get("round_durations", {}).get(key)
            ]

        r1_dur = _round_dur("round_1_duration_s")
        r2_dur = _round_dur("round_2_duration_s")
        r3_dur = _round_dur("round_3_duration_s")
        if r1_dur:
            print(f"  Avg Round-1 duration      {_avg(r1_dur)}s  (bounded by slowest agent)")
        if r2_dur:
            print(f"  Avg Round-2 duration      {_avg(r2_dur)}s  (selective — fewer agents)")
        if r3_dur:
            print(f"  Avg Round-3 duration      {_avg(r3_dur)}s")

    print(f"\n{'='*58}")
    print(f"  VOYAGER METRICS SUMMARY  ({len(all_sessions)} total sessions)")
    print(f"{'='*58}")

    _section(full, "full")
    _section(baseline, "baseline")

    # ── Before/after comparison table ────────────────────────────────────
    if full and baseline:
        print(f"\n  {'─'*54}")
        print("  BEFORE / AFTER  COLLABORATION HUB")
        print(f"  {'─'*54}")
        print(f"  {'Metric':<36} {'Baseline':>10} {'Full':>10}")
        print(f"  {'-'*56}")

        def _fmt(v, suffix=""):
            return f"{v}{suffix}" if v is not None else "n/a"

        bf = _avg([s["final_conflict_count"] for s in baseline], 1)
        ff = _avg([s["final_conflict_count"] for s in full], 1)
        print(f"  {'Final conflicts / query':<36} {_fmt(bf):>10} {_fmt(ff):>10}")

        bc = _avg([s.get("estimated_cost_usd", 0) for s in baseline], 4)
        fc = _avg([s.get("estimated_cost_usd", 0) for s in full], 4)
        print(f"  {'Avg cost / query (USD)':<36} {'$'+str(bc):>10} {'$'+str(fc):>10}")

        bd = _avg([s["duration_s"] for s in baseline], 1)
        fd = _avg([s["duration_s"] for s in full], 1)
        print(f"  {'Avg duration / query (s)':<36} {_fmt(bd, 's'):>10} {_fmt(fd, 's'):>10}")

    print(f"\n{'='*58}\n")


# ── Standardized results output ──────────────────────────────────────────────
def compute_aggregate_summary(sessions: list[dict], inventory_mode: str = "mock") -> dict[str, Any]:
    """Aggregate benchmark metrics across a set of sessions.

    Fields mirror Priority-4 recommendations so `run_summary.json` carries the
    article-ready numbers (mean conflicts per round, resolution rate,
    post-refinement introduction rate, reopened rate, convergence distribution).
    """
    full = [s for s in sessions if s.get("mode") == "full"]
    baseline = [s for s in sessions if s.get("mode") == "baseline"]

    def _round_means(mode_sessions: list[dict]) -> dict[str, Any]:
        n = len(mode_sessions)
        conv = [s.get("convergence_summary", {}) for s in mode_sessions]
        r1 = [c.get("round_1_conflicts", 0) for c in conv if c.get("round_1_conflicts") is not None]
        r2 = [c.get("round_2_conflicts_remaining") for c in conv if c.get("round_2_conflicts_remaining") is not None]
        r3 = [c.get("round_3_conflicts_remaining") for c in conv if c.get("round_3_conflicts_remaining") is not None]
        return {
            "query_count": n,
            "mean_round_1_conflicts": _avg(r1, 2),
            "mean_round_2_conflicts_remaining": _avg([x for x in r2 if x is not None], 2),
            "mean_round_3_conflicts_remaining": _avg(r3, 2),
            "mean_introduced": _avg([s.get("conflicts_introduced_count", 0) for s in mode_sessions], 2),
            "mean_reopened": _avg([s.get("conflicts_reopened_count", 0) for s in mode_sessions], 2),
            "mean_persistence": _avg(
                [r.get("persistence_count", 0) for s in mode_sessions for r in s.get("conflict_lifecycle", [])], 2
            ),
        }

    resolution_rates = [
        s.get("conflict_resolution_rate_pct")
        for s in full
        if s.get("conflict_resolution_rate_pct") is not None
    ]
    conv_rounds = [
        s.get("convergence_summary", {}).get("converged_round")
        for s in full
        if s.get("convergence_summary", {}).get("converged_round") is not None
    ]

    return {
        "results_schema_version": _RESULTS_SCHEMA_VERSION,
        "inventory_mode": inventory_mode,
        "query_count": len(sessions),
        "mode": "compare" if full and baseline else ("full" if full else "baseline"),
        "mean_final_conflicts": _avg([s.get("final_conflict_count", 0) for s in full], 2),
        "resolution_rate_pct": _avg(resolution_rates, 1),
        "post_refinement_introduction_rate_pct": _pct(
            sum(s.get("conflicts_introduced_count", 0) for s in full), max(len(full), 1)
        ),
        "reopened_conflict_rate_pct": _pct(
            sum(s.get("conflicts_reopened_count", 0) for s in full), max(len(full), 1)
        ),
        "mean_reexecuted_agents": _avg(
            [s.get("round_2_agents_rerun_count", 0) + s.get("round_3_agents_rerun_count", 0) for s in full], 2
        ),
        "agent_call_savings_vs_full_rerun_pct": _avg(
            [
                s.get("selective_rerun_savings_pct", 0)
                for s in full
                if s.get("round_2_triggered") or s.get("round_3_triggered")
            ],
            1,
        ),
        "converged_after_round_1_pct": _pct(sum(1 for r in conv_rounds if r == 1), max(len(full), 1)),
        "converged_after_round_2_pct": _pct(sum(1 for r in conv_rounds if r == 2), max(len(full), 1)),
        "converged_after_round_3_pct": _pct(sum(1 for r in conv_rounds if r == 3), max(len(full), 1)),
        # True rate: share of queries with ≥1 persisting conflict at the final
        # audit (per-query counts summed here would exceed 100%).
        "final_unresolved_conflict_rate_pct": _pct(
            sum(
                1
                for s in full
                if s.get("convergence_summary", {}).get("persisting_at_final_audit", 0) > 0
            ),
            max(len(full), 1),
        ),
        "unsatisfiable_constraint_rate_pct": _pct(
            sum(
                1
                for s in full
                if s.get("feedback_metrics", {}).get("fallback_to_original_selection")
            ),
            max(len(full), 1),
        ),
        "full": _round_means(full),
        "baseline": _round_means(baseline),
    }


def write_results_artifacts(
    sessions: list[dict],
    inventory_manifest: dict[str, Any] | None = None,
    out_dir: str | None = None,
    inventory_mode: str = "mock",
) -> Path:
    """Write the standardized results files for a benchmark run.

    Produces, under ``results/``:
      - run_summary.json        — aggregate metrics + schema version
      - conflicts_by_round.csv  — per-session round conflict counts
      - conflict_lifecycle.csv  — per-conflict lifecycle transitions
      - hybrid_candidates.csv   — LLM candidate isolation counts
      - inventory_manifest.json — capture/replay manifest (if provided)
    """
    import csv

    results_dir = Path(out_dir) if out_dir else _RESULTS_DIR
    results_dir.mkdir(parents=True, exist_ok=True)

    (results_dir / "run_summary.json").write_text(
        json.dumps(compute_aggregate_summary(sessions, inventory_mode=inventory_mode), indent=2) + "\n"
    )

    # conflicts_by_round.csv
    with open(results_dir / "conflicts_by_round.csv", "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "session_id", "mode",
                "round_1_conflicts", "round_2_conflicts_remaining", "round_3_conflicts_remaining",
                "final_conflicts", "converged_round",
            ],
        )
        writer.writeheader()
        for s in sessions:
            conv = s.get("convergence_summary", {}) or {}
            writer.writerow({
                "session_id": s.get("session_id", ""),
                "mode": s.get("mode", ""),
                "round_1_conflicts": s.get("round_1_conflict_count", 0),
                "round_2_conflicts_remaining": conv.get("round_2_conflicts_remaining", ""),
                "round_3_conflicts_remaining": conv.get("round_3_conflicts_remaining", ""),
                "final_conflicts": s.get("final_conflict_count", 0),
                "converged_round": conv.get("converged_round", ""),
            })

    # conflict_lifecycle.csv
    with open(results_dir / "conflict_lifecycle.csv", "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "session_id", "fingerprint", "type", "agents", "status",
                "first_seen_round", "last_seen_round", "resolved_in_round", "persistence_count",
            ],
        )
        writer.writeheader()
        for s in sessions:
            for rec in s.get("conflict_lifecycle", []) or []:
                writer.writerow({
                    "session_id": s.get("session_id", ""),
                    "fingerprint": rec.get("fingerprint", ""),
                    "type": rec.get("type", ""),
                    "agents": "|".join(rec.get("agents", [])),
                    "status": rec.get("status", ""),
                    "first_seen_round": rec.get("first_seen_round", ""),
                    "last_seen_round": rec.get("last_seen_round", ""),
                    "resolved_in_round": rec.get("resolved_in_round", ""),
                    "persistence_count": rec.get("persistence_count", ""),
                })

    # hybrid_candidates.csv
    with open(results_dir / "hybrid_candidates.csv", "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["session_id", "mode", "llm_candidates", "validated", "unverified"],
        )
        writer.writeheader()
        for s in sessions:
            writer.writerow({
                "session_id": s.get("session_id", ""),
                "mode": s.get("mode", ""),
                "llm_candidates": s.get("llm_candidate_count", 0),
                "validated": s.get("validated_llm_count", 0),
                "unverified": s.get("unverified_llm_count", 0),
            })

    # inventory_manifest.json
    if inventory_manifest is not None:
        (results_dir / "inventory_manifest.json").write_text(
            json.dumps(inventory_manifest, indent=2) + "\n"
        )

    return results_dir
