"""Unit tests for scripts/compare_results.py (expected-vs-actual comparison).

Builds synthetic results artifacts and asserts the PASS/FAIL logic, tolerance
handling, and quick-mode smoke checks. No live graph or API runs.
"""

import json

from scripts.compare_results import (
    byround_metrics,
    compare_full,
    compare_quick,
    lifecycle_metrics,
)


def _expected() -> dict:
    return {
        "provenance": {
            "query_count": 4,
            "queries": 2,
            "benchmark_command": "python scripts/benchmark_queries.py --mode compare --inventory replay",
        },
        "run_summary": {"mean_final_conflicts": {"expected": 1.0, "tolerance": 0.1}},
        "conflicts_by_round": {
            "full": {
                "fully_resolved_queries": {"expected": 1, "tolerance": 0},
                "unresolved_queries": {"expected": 1, "tolerance": 0},
            },
            "baseline": {
                "fully_resolved_queries": {"expected": 0, "tolerance": 0},
                "unresolved_queries": {"expected": 2, "tolerance": 0},
            },
        },
        "rule_level": {
            "detection_round_1": {
                "full": {"location_mismatch": {"expected": 1, "tolerance": 0}},
                "baseline": {"location_mismatch": {"expected": 0, "tolerance": 1}},
            },
            "lifecycle_total": {"timing_inefficiency": {"expected": 1, "tolerance": 0}},
        },
        "per_query": {
            "full": [{"round_1": 2, "final": 1}, {"round_1": 1, "final": 0}],
            "baseline": [{"round_1": 2, "final": 2}, {"round_1": 1, "final": 1}],
        },
    }


def _artifacts(tmp_path):
    d = tmp_path / "results"
    d.mkdir()
    (d / "run_summary.json").write_text(json.dumps({"mean_final_conflicts": 1.0}))
    (d / "conflicts_by_round.csv").write_text(
        "session_id,mode,round_1_conflicts,round_2_conflicts_remaining,"
        "round_3_conflicts_remaining,final_conflicts,converged_round\n"
        "a,full,2,1,1,1,\n"
        "b,baseline,2,2,2,2,\n"
        "c,full,1,1,1,0,2\n"
        "d,baseline,1,1,1,1,\n"
    )
    (d / "conflict_lifecycle.csv").write_text(
        "session_id,fingerprint,type,agents,status,first_seen_round,"
        "last_seen_round,resolved_in_round,persistence_count\n"
        "a,f1,location_mismatch,hotel|experience,persisting,1,3,,2\n"
        "c,f2,timing_inefficiency,flight,resolved,1,2,2,1\n"
    )
    return d


def test_compare_full_passes(tmp_path, capsys):
    d = _artifacts(tmp_path)
    rc = compare_full(_expected(), d)
    out = capsys.readouterr().out
    assert rc == 0
    assert "8/8 metrics passed" in out
    assert "PASS" in out
    assert "FAIL" not in out


def test_compare_full_fails_on_drift(tmp_path, capsys):
    d = _artifacts(tmp_path)
    (d / "run_summary.json").write_text(json.dumps({"mean_final_conflicts": 5.0}))
    rc = compare_full(_expected(), d)
    assert rc == 1


def test_compare_full_rejects_session_count_mismatch(tmp_path, capsys):
    d = _artifacts(tmp_path)
    (d / "conflicts_by_round.csv").write_text(
        "session_id,mode,round_1_conflicts,round_2_conflicts_remaining,"
        "round_3_conflicts_remaining,final_conflicts,converged_round\n"
        "a,full,2,1,1,1,\n"
        "b,baseline,2,2,2,2,\n"
    )
    rc = compare_full(_expected(), d)
    assert rc == 1


def test_compare_quick_passes(tmp_path, capsys):
    d = _artifacts(tmp_path)
    rc = compare_quick(_expected(), d)
    assert rc == 0
    assert "8/8 checks passed" in capsys.readouterr().out


def test_compare_quick_fails_on_drift(tmp_path):
    d = _artifacts(tmp_path)
    (d / "conflicts_by_round.csv").write_text(
        "session_id,mode,round_1_conflicts,round_2_conflicts_remaining,"
        "round_3_conflicts_remaining,final_conflicts,converged_round\n"
        "a,full,2,1,1,1,\n"
        "b,baseline,2,2,2,2,\n"
        "c,full,1,1,1,0,2\n"
        "d,baseline,9,1,1,1,\n"
    )
    assert compare_quick(_expected(), d) == 1


def test_byround_metrics():
    by_round = [
        {"mode": "full", "round_1_conflicts": "2", "final_conflicts": "1", "converged_round": ""},
        {"mode": "full", "round_1_conflicts": "1", "final_conflicts": "0", "converged_round": "2"},
        {"mode": "baseline", "round_1_conflicts": "2", "final_conflicts": "2", "converged_round": ""},
    ]
    m = byround_metrics(by_round)
    assert m["full"]["fully_resolved_queries"] == 1
    assert m["full"]["total_round_1_conflicts"] == 3
    assert m["full"]["converged_round_2"] == 1
    assert m["baseline"]["unresolved_queries"] == 1


def test_lifecycle_metrics():
    by_round = [
        {"session_id": "a", "mode": "full"},
        {"session_id": "b", "mode": "baseline"},
    ]
    lifecycle = [
        {"session_id": "a", "type": "location_mismatch", "status": "persisting", "first_seen_round": "1"},
        {"session_id": "b", "type": "timing_inefficiency", "status": "persisting", "first_seen_round": "1"},
    ]
    m = lifecycle_metrics(lifecycle, by_round)
    assert m["detection_round_1"]["full"]["location_mismatch"] == 1
    assert m["detection_round_1"]["baseline"]["timing_inefficiency"] == 1
    assert m["lifecycle_total"]["location_mismatch"] == 1
    assert m["status_full"]["persisting"] == 1
    assert m["status_baseline"]["persisting"] == 1