#!/usr/bin/env python3
"""Compare a replay benchmark run against the committed expected values.

Loads the run's results artifacts (run_summary.json, conflicts_by_round.csv,
conflict_lifecycle.csv) and checks each metric in an expected-values file
(benchmarks/expected_replay.json) against its expected value within the
documented per-metric tolerance. Prints a per-metric PASS/FAIL table and exits
0 when every check passes, 1 otherwise, 2 on usage/IO errors.

Usage:
    python scripts/compare_results.py [expected.json] [results_dir]
    python scripts/compare_results.py --quick [expected.json] [results_dir]

--quick compares only round-1 and final conflict counts for the queries the
run actually executed (first N of the expected per_query sequence) and is used
by scripts/reproduce.sh --quick as a smoke check. scripts/reproduce.sh clears
metrics/sessions.jsonl before running so the artifacts cover exactly one run.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

CONFLICT_TYPES = ("location_mismatch", "timing_inefficiency", "weather_activity_mismatch")
MODES = ("full", "baseline")
STATUSES = ("resolved", "persisting", "new")


def load_expected(path: Path) -> dict[str, Any]:
    with open(path) as fh:
        return json.load(fh)


def load_actual(results_dir: Path) -> tuple[dict[str, Any], list[dict[str, str]], list[dict[str, str]]]:
    def _read_csv(name: str) -> list[dict[str, str]]:
        with open(results_dir / name, newline="") as fh:
            return list(csv.DictReader(fh))

    with open(results_dir / "run_summary.json") as fh:
        run_summary = json.load(fh)
    return run_summary, _read_csv("conflicts_by_round.csv"), _read_csv("conflict_lifecycle.csv")


def byround_metrics(by_round: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    """Aggregate rule-level counts per mode from conflicts_by_round.csv."""
    out: dict[str, dict[str, int]] = {}
    for mode in MODES:
        rows = [r for r in by_round if r["mode"] == mode]
        finals = [int(r["final_conflicts"]) for r in rows]
        round_1 = [int(r["round_1_conflicts"]) for r in rows]
        converged = [r["converged_round"] for r in rows if r["converged_round"]]
        out[mode] = {
            "fully_resolved_queries": sum(1 for f in finals if f == 0),
            "unresolved_queries": sum(1 for f in finals if f > 0),
            "total_round_1_conflicts": sum(round_1),
            "total_final_conflicts": sum(finals),
            "converged_round_1": converged.count("1"),
            "converged_round_2": converged.count("2"),
            "converged_round_3": converged.count("3"),
        }
    return out


def _type_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    return {t: sum(1 for r in rows if r["type"] == t) for t in CONFLICT_TYPES}


def _status_counts(
    lifecycle: list[dict[str, str]], mode_of: dict[str, str], mode: str
) -> dict[str, int]:
    rows = [r for r in lifecycle if mode_of.get(r["session_id"]) == mode]
    return {s: sum(1 for r in rows if r["status"] == s) for s in STATUSES}


def lifecycle_metrics(
    lifecycle: list[dict[str, str]], by_round: list[dict[str, str]]
) -> dict[str, Any]:
    """Per-rule detection/resolution counts from conflict_lifecycle.csv."""
    mode_of = {r["session_id"]: r["mode"] for r in by_round}
    round_1 = [r for r in lifecycle if r["first_seen_round"] == "1"]
    return {
        "detection_round_1": {
            "all_modes": _type_counts(round_1),
            "full": _type_counts([r for r in round_1 if mode_of.get(r["session_id"]) == "full"]),
            "baseline": _type_counts([r for r in round_1 if mode_of.get(r["session_id"]) == "baseline"]),
        },
        "lifecycle_total": _type_counts(lifecycle),
        "status_full": _status_counts(lifecycle, mode_of, "full"),
        "status_baseline": _status_counts(lifecycle, mode_of, "baseline"),
    }


def resolve_actual(
    key: str, run_summary: dict[str, Any], byround: dict[str, dict[str, int]], lifecycle: dict[str, Any]
) -> float:
    if key.startswith("run_summary."):
        node: Any = run_summary
        for part in key.split(".")[1:]:
            node = node[part]
        return node
    if key.startswith("conflicts_by_round."):
        _, mode, metric = key.split(".")
        return byround[mode][metric]
    if key.startswith("rule_level."):
        node = lifecycle
        for part in key.split(".")[1:]:
            node = node[part]
        return node
    raise KeyError(f"unknown metric path: {key}")


def expected_items(node: Any, prefix: str = "") -> list[tuple[str, float, float]]:
    """Flatten the expected file's nested metric leaves to (path, expected, tolerance)."""
    items: list[tuple[str, float, float]] = []
    for key, value in node.items():
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict) and "expected" in value:
            items.append((path, float(value["expected"]), float(value.get("tolerance", 0))))
        elif isinstance(value, dict):
            items.extend(expected_items(value, path))
    return items


def _print_header(expected: dict[str, Any], results_dir: Path) -> None:
    provenance = expected.get("provenance", {})
    print("Benchmark output comparison")
    print(f"  expected: {provenance.get('benchmark_command', '?')}")
    print(f"  actual:   {results_dir}")
    print()


def compare_full(expected: dict[str, Any], results_dir: Path) -> int:
    run_summary, by_round, lifecycle = load_actual(results_dir)
    actuals = {
        "run_summary": run_summary,
        "conflicts_by_round": byround_metrics(by_round),
        "rule_level": lifecycle_metrics(lifecycle, by_round),
    }
    items = expected_items(expected)
    query_count = expected.get("provenance", {}).get("query_count")
    if query_count is not None and len(by_round) != query_count:
        print(f"FAIL  session count: expected {query_count}, found {len(by_round)}")
        print("  (rerun with a clean metrics/sessions.jsonl — scripts/reproduce.sh does this)")
        return 1

    _print_header(expected, results_dir)
    width = max(len(path) for path, _, _ in items) + 2
    print(f"{'metric':<{width}} {'expected':>9} {'actual':>7} {'tol':>4}  result")
    failures = 0
    for path, expected_value, tolerance in items:
        actual = resolve_actual(path, actuals["run_summary"], actuals["conflicts_by_round"], actuals["rule_level"])
        ok = abs(actual - expected_value) <= tolerance + 1e-9
        failures += 0 if ok else 1
        status = "PASS" if ok else "FAIL"
        print(f"{path:<{width}} {expected_value:>9} {actual:>7} {tolerance:>4}  {status}")

    total = len(items)
    passed = total - failures
    print()
    print(f"{passed}/{total} metrics passed")
    return 1 if failures else 0


def compare_quick(expected: dict[str, Any], results_dir: Path) -> int:
    _, by_round, _ = load_actual(results_dir)
    full_rows = [r for r in by_round if r["mode"] == "full"]
    base_rows = [r for r in by_round if r["mode"] == "baseline"]
    if len(full_rows) != len(base_rows):
        print(f"FAIL  unbalanced sessions: {len(full_rows)} full vs {len(base_rows)} baseline")
        return 1

    n = len(full_rows)
    per_query = expected.get("per_query", {})
    if n < 1 or n > len(per_query.get("full", [])):
        print(f"FAIL  quick check expects 1..{len(per_query.get('full', []))} queries, found {n}")
        return 1

    _print_header(expected, results_dir)
    print(f"Quick smoke check — first {n} query(ies), round-1 and final conflict counts\n")
    print(f"{'session':<28} {'expected':>8} {'actual':>6} {'tol':>4}  result")
    failures = 0
    total = 0
    known_variance = 0
    for i in range(n):
        mode_rows = (("full", full_rows, per_query["full"]), ("baseline", base_rows, per_query["baseline"]))
        for mode, rows, exp_rows in mode_rows:
            # Optional per-query "tolerance" marks sessions with documented
            # residual variance at temperature 0 (see provenance notes in
            # expected_replay.json). Default 0 keeps every other check exact.
            tolerance = int(exp_rows[i].get("tolerance", 0))
            for field, exp_field in (("round_1", "round_1"), ("final", "final")):
                expected_value = exp_rows[i][exp_field]
                actual = int(rows[i][f"{field}_conflicts"]) if field == "round_1" else int(rows[i]["final_conflicts"])
                diff = abs(actual - expected_value)
                ok = diff <= tolerance
                if not ok:
                    status = "FAIL"
                elif diff:
                    status = "PASS (known variance)"
                    known_variance += 1
                else:
                    status = "PASS"
                failures += 0 if ok else 1
                total += 1
                label = f"q{i}.{mode}.{field}"
                print(f"{label:<28} {expected_value:>8} {actual:>6} {tolerance:>4}  {status}")

    print()
    passed = total - failures
    summary = f"{passed}/{total} checks passed"
    if known_variance:
        summary += f" ({known_variance} within documented tolerance)"
    print(summary)
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quick", action="store_true", help="smoke check: compare first N queries only")
    parser.add_argument("expected", nargs="?", default="benchmarks/expected_replay.json")
    parser.add_argument("results_dir", nargs="?", default="results")
    args = parser.parse_args()

    expected_path = Path(args.expected)
    results_dir = Path(args.results_dir)
    try:
        expected = load_expected(expected_path)
        _ = load_actual(results_dir)
    except (FileNotFoundError, json.JSONDecodeError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.quick:
        return compare_quick(expected, results_dir)
    return compare_full(expected, results_dir)


if __name__ == "__main__":
    sys.exit(main())