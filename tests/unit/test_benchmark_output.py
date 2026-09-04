"""Benchmark output regression tests (Priority 4.2 + acceptance criteria).

Runs the standardized artifact writer against tiny synthetic session records
and asserts the output files carry the churn/convergence fields, round columns,
lifecycle transitions, and a results_schema_version. No live graph or API runs.
"""

import json

from metrics.collector import (
    compute_aggregate_summary,
    write_results_artifacts,
)


def _session(session_id, mode, round_1=1, final=0, converged=None, lifecycle=None):
    return {
        "session_id": session_id,
        "mode": mode,
        "round_1_conflict_count": round_1,
        "final_conflict_count": final,
        "convergence_summary": {
            "round_1_conflicts": round_1,
            "round_2_conflicts_remaining": 0,
            "round_3_conflicts_remaining": final,
            "resolved_by_round_2": round_1 - final,
            "resolved_by_round_3": 0,
            "introduced_post_refinement": 0,
            "reopened": 0,
            "persisting_at_final_audit": final,
            "converged_round": converged,
        },
        "conflicts_introduced_count": 0,
        "conflicts_reopened_count": 0,
        "conflict_lifecycle": lifecycle or [],
        "round_2_agents_rerun_count": 1,
        "round_3_agents_rerun_count": 0,
        "round_2_triggered": True,
        "round_3_triggered": False,
        "selective_rerun_savings_pct": 30.0,
        "conflict_resolution_rate_pct": 100.0,
        "llm_candidate_count": 0,
        "validated_llm_count": 0,
        "unverified_llm_count": 0,
        "feedback_metrics": {},
    }


def _lifecycle(fingerprint="abc123", status="resolved", resolved_in_round=2):
    return [{
        "fingerprint": fingerprint,
        "type": "location_mismatch",
        "agents": ["hotel", "experience"],
        "status": status,
        "first_seen_round": 1,
        "last_seen_round": 1 if status == "resolved" else 3,
        "resolved_in_round": resolved_in_round,
        "persistence_count": 0,
    }]


def test_run_summary_includes_churn_and_convergence_fields(tmp_path):
    sessions = [
        _session("s1", "baseline", round_1=2, final=2, converged=None),
        _session("s2", "full", round_1=2, final=0, converged=2,
                 lifecycle=_lifecycle()),
    ]
    out = write_results_artifacts(sessions, inventory_manifest={"fixtures": {}}, out_dir=str(tmp_path))

    summary = json.loads((out / "run_summary.json").read_text())
    assert summary["results_schema_version"] == "2"
    assert "mean_round_1_conflicts" in summary["full"]
    assert "resolution_rate_pct" in summary
    assert "post_refinement_introduction_rate_pct" in summary
    assert "reopened_conflict_rate_pct" in summary


def test_conflicts_by_round_csv_contains_round_columns(tmp_path):
    sessions = [_session("s2", "full", round_1=2, final=0, converged=2,
                         lifecycle=_lifecycle())]
    out = write_results_artifacts(sessions, out_dir=str(tmp_path))

    header = (out / "conflicts_by_round.csv").read_text().splitlines()[0]
    for col in ("round_1_conflicts", "round_2_conflicts_remaining",
                "round_3_conflicts_remaining", "converged_round"):
        assert col in header


def test_conflict_lifecycle_csv_contains_status_transitions(tmp_path):
    sessions = [_session("s2", "full", round_1=2, final=0, converged=2,
                         lifecycle=_lifecycle(status="resolved"))]
    out = write_results_artifacts(sessions, out_dir=str(tmp_path))

    lines = (out / "conflict_lifecycle.csv").read_text().strip().splitlines()
    assert len(lines) == 2  # header + one lifecycle record
    assert "resolved" in lines[1]


def test_baseline_and_full_use_identical_manifest_hash(tmp_path):
    manifest = {"fixtures": {"q1_amadeus": {"fixture_hash": "abc", "sanitized": True}}}
    sessions = [
        _session("s1", "baseline", round_1=2, final=2),
        _session("s2", "full", round_1=2, final=0, converged=2),
    ]
    out = write_results_artifacts(sessions, inventory_manifest=manifest, out_dir=str(tmp_path))

    written = json.loads((out / "inventory_manifest.json").read_text())
    assert written["fixtures"]["q1_amadeus"]["fixture_hash"] == "abc"
    # The same manifest is referenced by both modes — paired comparability.
    summary = json.loads((out / "run_summary.json").read_text())
    assert summary["mode"] == "compare"
    assert summary["baseline"]["query_count"] == 1
    assert summary["full"]["query_count"] == 1


def test_aggregate_summary_versions_schema(tmp_path):
    summary = compute_aggregate_summary([_session("s2", "full", final=0, converged=2)])
    assert summary["results_schema_version"] == "2"


def test_collector_accepts_older_summary_without_convergence(tmp_path):
    """Older session records (no convergence_summary) still aggregate safely."""
    old = _session("s_old", "full", round_1=1, final=0, converged=None)
    old.pop("convergence_summary")
    summary = compute_aggregate_summary([old])
    assert summary["results_schema_version"] == "2"
