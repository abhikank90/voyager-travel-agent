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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_METRICS_DIR = Path(__file__).parent
_SESSIONS_FILE = _METRICS_DIR / "sessions.jsonl"
_RESEARCH_AGENTS_COUNT = 5


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

    # ── Token usage ───────────────────────────────────────────────────────
    token_data: dict[str, Any] = {}
    if token_usage is not None:
        token_data = {
            "input_tokens": token_usage.input_tokens,
            "output_tokens": token_usage.output_tokens,
            "total_tokens": token_usage.total_tokens,
            "estimated_cost_usd": estimated_cost_usd,
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "duration_s": duration_s,
        "mode": mode,

        # Conflict data
        "had_conflict": r1_count > 0,
        "round_1_conflict_count": r1_count,
        "round_1_conflict_types": [c.get("type") for c in round_1_conflicts],
        "round_1_conflict_severities": [c.get("severity") for c in round_1_conflicts],
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
        savings = [s["selective_rerun_savings_pct"] for s in sessions if s["round_2_triggered"] or s["round_3_triggered"]]
        resolution_rates = [s["conflict_resolution_rate_pct"] for s in sessions if s.get("conflict_resolution_rate_pct") is not None]

        print(f"\n  {'─'*54}")
        print(f"  {label.upper()} MODE  ({n} sessions)")
        print(f"  {'─'*54}")

        print(f"\n  CONFLICT RATE")
        print(f"  Queries with ≥1 Round-1 conflict  {len(with_conflict):>3}/{n}  ({_pct(len(with_conflict), n)}%)")
        print(f"  Queries triggering Round 2         {len(r2):>3}/{n}  ({_pct(len(r2), n)}%)")
        print(f"  Queries triggering Round 3         {len(r3):>3}/{n}  ({_pct(len(r3), n)}%)")
        avg_r1 = _avg([s["round_1_conflict_count"] for s in with_conflict])
        print(f"  Avg Round-1 conflicts per query    {avg_r1}")

        if resolution_rates:
            print(f"\n  CONFLICT RESOLUTION  (full mode only)")
            print(f"  Overall resolution rate            {_avg(resolution_rates, 0):.0f}%")
            type_r1: dict[str, int] = {}
            for s in sessions:
                for ct in s.get("round_1_conflict_types", []):
                    type_r1[ct] = type_r1.get(ct, 0) + 1
            if type_r1:
                print(f"  Conflict types detected:")
                for ctype, count in sorted(type_r1.items(), key=lambda x: -x[1]):
                    print(f"    {ctype:<38} {count:>3}  ({_pct(count, n)}% of queries)")

        if savings:
            print(f"\n  SELECTIVE RE-EXECUTION EFFICIENCY")
            print(f"  Avg agent-call savings vs full re-run  {_avg(savings, 0):.0f}%")
            print(f"  (sessions with Round 2/3, n={len(savings)})")

        avg_final = _avg([s["final_conflict_count"] for s in sessions])
        avg_r1_count = _avg([s["round_1_conflict_count"] for s in sessions])
        print(f"\n  CONFLICT COUNTS")
        print(f"  Avg Round-1 conflicts/query   {avg_r1_count}")
        print(f"  Avg final conflicts/query     {avg_final}")

        costs = [s["estimated_cost_usd"] for s in sessions if s.get("estimated_cost_usd")]
        if costs:
            print(f"\n  TOKEN USAGE")
            avg_in = _avg([s.get("input_tokens", 0) for s in sessions], 0)
            avg_out = _avg([s.get("output_tokens", 0) for s in sessions], 0)
            print(f"  Avg input tokens/query    {avg_in:>7,.0f}")
            print(f"  Avg output tokens/query   {avg_out:>7,.0f}")
            print(f"  Avg cost/query            ${_avg(costs, 4):.4f}")

        durations = [s["duration_s"] for s in sessions]
        print(f"\n  LATENCY")
        print(f"  Avg end-to-end duration   {_avg(durations)}s")
        r1_dur = [s["round_durations"].get("round_1_duration_s") for s in sessions if s.get("round_durations", {}).get("round_1_duration_s")]
        r2_dur = [s["round_durations"].get("round_2_duration_s") for s in sessions if s.get("round_durations", {}).get("round_2_duration_s")]
        r3_dur = [s["round_durations"].get("round_3_duration_s") for s in sessions if s.get("round_durations", {}).get("round_3_duration_s")]
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
        print(f"  BEFORE / AFTER  COLLABORATION HUB")
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
