"""Unit tests for conflict identity and lifecycle tracking.

These are the acceptance-criteria tests for Priority 1:
  - the same conflict has ONE identity across rounds (stable fingerprint),
  - agent order / list order / round number do not change identity,
  - identity tracks (type, agents) so live-data evidence churn across
    refinement rounds cannot split a single logical conflict,
  - genuinely different conflict types produce different fingerprints,
  - lifecycle transitions (new/persisting/resolved/reopened) are correct.
"""

from agents.conflicts import (
    Conflict,
    ConflictLifecycleTracker,
    conflict_fingerprint,
    deep_normalize,
)

# ── Fingerprint identity ──────────────────────────────────────────────────────

def _conf(**overrides):
    base = {
        "type": "location_mismatch",
        "agents": ["hotel", "experience"],
        "data": {"activity_locations": ["Oia", "Fira", "Imerovigli"]},
        "severity": "medium",
        "description": "Hotel far from activities",
    }
    base.update(overrides)
    return base


def test_same_conflict_across_rounds_same_fingerprint():
    fp1 = conflict_fingerprint(_conf())
    fp2 = conflict_fingerprint(_conf())
    assert fp1 == fp2


def test_agent_order_does_not_affect_fingerprint():
    fp1 = conflict_fingerprint(_conf(agents=["hotel", "experience"]))
    fp2 = conflict_fingerprint(_conf(agents=["experience", "hotel"]))
    assert fp1 == fp2


def test_equivalent_location_lists_with_different_ordering_match():
    fp1 = conflict_fingerprint(_conf(data={"activity_locations": ["Oia", "Fira", "Imerovigli"]}))
    fp2 = conflict_fingerprint(_conf(data={"activity_locations": ["Fira", "Imerovigli", "Oia"]}))
    assert fp1 == fp2


def test_round_number_does_not_alter_identity():
    fp_no_round = conflict_fingerprint(_conf())
    with_round = _conf()
    with_round["round"] = 3
    fp_with_round = conflict_fingerprint(with_round)
    assert fp_no_round == fp_with_round


def test_data_change_across_rounds_splits_identity():
    """Fingerprints are content-addressed: if refinement genuinely replaces the
    evidence (activity_locations), that is a DIFFERENT conflict with a distinct
    identity — so introduced/resolved/reopened stay meaningful, not vacuous."""
    fp1 = conflict_fingerprint(_conf(data={"activity_locations": ["Oia", "Fira"]}))
    fp2 = conflict_fingerprint(_conf(data={"activity_locations": ["Fira", "Imerovigli", "Oia"]}))
    assert fp1 != fp2


def test_different_evidence_same_type_produces_different_fingerprints():
    """Heat vs. rain ad advisory, or distinct activity sets, must not collapse
    into a single constant fingerprint across queries."""
    fp_heat = conflict_fingerprint(_conf(data={"advisory": "heat"}))
    fp_rain = conflict_fingerprint(_conf(data={"advisory": "rain"}))
    assert fp_heat != fp_rain


def test_empty_vs_populated_evidence_splits_identity():
    fp_empty = conflict_fingerprint(_conf(data={}))
    fp_populated = conflict_fingerprint(
        _conf(data={"activity_locations": ["Oia", "Fira", "Imerovigli"]})
    )
    assert fp_empty != fp_populated


def test_different_conflict_types_produce_different_fingerprints():
    fp1 = conflict_fingerprint(_conf(type="location_mismatch"))
    fp2 = conflict_fingerprint(_conf(type="timing_inefficiency"))
    assert fp1 != fp2


def test_different_agents_produce_different_fingerprints():
    fp1 = conflict_fingerprint(_conf(agents=["hotel", "experience"]))
    fp2 = conflict_fingerprint(_conf(agents=["flight"]))
    assert fp1 != fp2


def test_description_prose_is_excluded_from_fingerprint():
    fp1 = conflict_fingerprint(_conf(description="prose A"))
    fp2 = conflict_fingerprint(_conf(description="totally different prose B"))
    assert fp1 == fp2


def test_float_rounding_does_not_split_identity():
    fp1 = conflict_fingerprint(_conf(data={"budget_usd": 2000.0001}))
    fp2 = conflict_fingerprint(_conf(data={"budget_usd": 2000.0002}))
    assert fp1 == fp2


def test_duration_values_normalized_to_one_unit():
    c = _conf(data={"duration": "PT1H30M"})
    c2 = _conf(data={"duration": "PT1H30M"})
    assert conflict_fingerprint(c) == conflict_fingerprint(c2)
    # deep_normalize converts ISO duration to a canonical minutes string
    assert deep_normalize({"duration": "PT1H30M"}) == {"duration": "duration_minutes:90"}


def test_conflict_dataclass_fingerprint_stable():
    a = Conflict(conflict_type="x", agents=("a", "b"), data={"k": [3, 1, 2]})
    b = Conflict(conflict_type="x", agents=("b", "a"), data={"k": [1, 2, 3]})
    assert a.fingerprint == b.fingerprint


# ── Lifecycle transitions ─────────────────────────────────────────────────────

def _run_sequence():
    tracker = ConflictLifecycleTracker()
    A = _conf(type="conflict_A", data={"v": "a"})
    B = _conf(type="conflict_B", data={"v": "b"})
    C = _conf(type="conflict_C", data={"v": "c"})

    tracker.audit([A, B], round_num=1)
    tracker.audit([B], round_num=2)
    tracker.audit([B, C], round_num=3)
    tracker.audit([A, B, C], round_num=4)
    return tracker


def test_lifecycle_round2_resolved_and_persisting():
    tracker = ConflictLifecycleTracker()
    A = _conf(type="A", data={"v": "a"})
    B = _conf(type="B", data={"v": "b"})

    tracker.audit([A, B], round_num=1)
    audit2 = tracker.audit([B], round_num=2)

    resolved_fps = {c["fingerprint"] for c in audit2["conflicts_resolved"]}
    persisting_fps = {c["fingerprint"] for c in audit2["conflicts_persisting"]}
    assert resolved_fps == {conflict_fingerprint(A)}
    assert persisting_fps == {conflict_fingerprint(B)}
    assert audit2["conflicts_reopened"] == []


def test_lifecycle_round3_introduced_post_refinement():
    tracker = ConflictLifecycleTracker()
    A = _conf(type="A", data={"v": "a"})
    B = _conf(type="B", data={"v": "b"})
    C = _conf(type="C", data={"v": "c"})

    tracker.audit([A, B], round_num=1)
    tracker.audit([B], round_num=2)
    audit3 = tracker.audit([B, C], round_num=3)

    introduced_fps = {c["fingerprint"] for c in audit3["conflicts_introduced"]}
    assert introduced_fps == {conflict_fingerprint(C)}
    # C was introduced after round 1 → post-refinement
    rec = next(r for r in audit3["conflict_lifecycle"] if r["type"] == "C")
    assert rec["first_seen_round"] == 3


def test_lifecycle_round4_reopened():
    tracker = _run_sequence()
    A_fp = conflict_fingerprint(_conf(type="conflict_A", data={"v": "a"}))
    records = {r["fingerprint"]: r for r in tracker.to_state()["records"].values()}
    assert records[A_fp]["status"] == "reopened"


def test_lifecycle_full_sequence_statuses():
    tracker = _run_sequence()
    state = tracker.to_state()
    records = {r["fingerprint"]: r for r in state["records"].values()}

    A_fp = conflict_fingerprint(_conf(type="conflict_A", data={"v": "a"}))
    B_fp = conflict_fingerprint(_conf(type="conflict_B", data={"v": "b"}))
    C_fp = conflict_fingerprint(_conf(type="conflict_C", data={"v": "c"}))

    assert records[A_fp]["status"] == "reopened"
    assert records[B_fp]["status"] == "persisting"
    assert records[C_fp]["status"] == "persisting"
    assert records[A_fp]["first_seen_round"] == 1


def test_introduced_after_agents_attributed():
    tracker = ConflictLifecycleTracker()
    A = _conf(type="A", data={"v": "a"})
    tracker.audit([A], round_num=1)
    C = _conf(type="C", data={"v": "c"})
    audit = tracker.audit([C], round_num=2, introduced_after_agents=["hotel"])

    rec = next(r for r in audit["conflict_lifecycle"] if r["type"] == "C")
    assert rec["introduced_after_agents"] == ["hotel"]


def test_convergence_summary_resolved_by_round2():
    tracker = ConflictLifecycleTracker()
    A = _conf(type="A", data={"v": "a"})
    B = _conf(type="B", data={"v": "b"})
    tracker.audit([A, B], round_num=1)
    tracker.audit([], round_num=2)
    tracker.audit([], round_num=3)

    summary = tracker.convergence_summary()
    assert summary["round_1_conflicts"] == 2
    assert summary["round_2_conflicts_remaining"] == 0
    assert summary["round_3_conflicts_remaining"] == 0
    assert summary["resolved_by_round_2"] == 2
    assert summary["converged_round"] == 2


def test_convergence_summary_never_converges():
    tracker = ConflictLifecycleTracker()
    A = _conf(type="A", data={"v": "a"})
    tracker.audit([A], round_num=1)
    tracker.audit([A], round_num=2)
    tracker.audit([A], round_num=3)

    summary = tracker.convergence_summary()
    assert summary["converged_round"] is None
    assert summary["persisting_at_final_audit"] == 1


def test_tracker_serialization_round_trip():
    tracker = _run_sequence()
    restored = ConflictLifecycleTracker.from_state(tracker.to_state())
    assert restored.convergence_summary() == tracker.convergence_summary()


def test_empty_audit_returns_empty_summary():
    tracker = ConflictLifecycleTracker()
    summary = tracker.convergence_summary()
    assert summary["round_1_conflicts"] == 0
    assert summary["converged_round"] == 1
