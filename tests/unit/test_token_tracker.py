"""
Regression tests for per-model token pricing and session cost computation.

These tests guard against two past bugs:
  1. Flat-rate bug: all session tokens priced at Sonnet rates even if they were
     produced by Haiku — compute_session_cost now sums per-model costs.
  2. Attribution leak: tokens tracked without a model string (track_usage called
     with no model=) fell only into session totals, not per_model, so they were
     silently excluded from per-model cost summation. compute_session_cost now
     detects and prices the remainder at Sonnet fallback.
"""

import logging

from metrics.token_tracker import (
    compute_cost,
    compute_session_cost,
    start_session,
    track_usage,
)

HAIKU = "claude-haiku-4-5-20251001"
SONNET = "claude-sonnet-4-6"
M = 1_000_000  # shorthand for 1 million tokens


# ── Unit tests for compute_cost ──────────────────────────────────────────────

def test_compute_cost_haiku():
    assert compute_cost(M, M, HAIKU) == 6.0


def test_compute_cost_sonnet():
    assert compute_cost(M, M, SONNET) == 18.0


def test_compute_cost_no_model_falls_back_to_sonnet():
    assert compute_cost(M, M) == 18.0


def test_compute_cost_unknown_model_warns_and_falls_back(caplog):
    with caplog.at_level(logging.WARNING, logger="metrics.token_tracker"):
        cost = compute_cost(M, M, "claude-unknown-999")
    assert cost == 18.0
    assert "Unknown model" in caplog.text
    assert "claude-unknown-999" in caplog.text


# ── Regression: per-model session cost ───────────────────────────────────────

def test_haiku_only_session_prices_at_haiku_rates():
    """Pure Haiku session: 1M+1M = $6.00 (not $18 at Sonnet rates)."""
    u = start_session()
    track_usage(M, M, model=HAIKU)
    assert compute_session_cost(u) == 6.0


def test_mixed_session_sums_per_model_costs():
    """1M+1M Haiku ($6) + 1M+1M Sonnet ($18) = $24.00 exactly."""
    u = start_session()
    track_usage(M, M, model=HAIKU)
    track_usage(M, M, model=SONNET)
    assert compute_session_cost(u) == 24.0


def test_unattributed_tokens_priced_at_fallback_and_logged(caplog):
    """1M+1M Haiku + 1M+1M Sonnet + 1M+1M no-model = $6 + $18 + $18 = $42.00."""
    u = start_session()
    track_usage(M, M, model=HAIKU)    # $6
    track_usage(M, M, model=SONNET)   # $18
    track_usage(M, M)                 # $18 fallback (no model)

    with caplog.at_level(logging.WARNING, logger="metrics.token_tracker"):
        cost = compute_session_cost(u)

    assert cost == 42.0
    assert "no model attribution" in caplog.text


# ── per_model accumulation ────────────────────────────────────────────────────

def test_per_model_tokens_accumulated():
    u = start_session()
    track_usage(500_000, 200_000, model=HAIKU)
    track_usage(300_000, 100_000, model=HAIKU)  # second Haiku call accumulates
    track_usage(M, M, model=SONNET)

    assert u.per_model[HAIKU] == {"input": 800_000, "output": 300_000}
    assert u.per_model[SONNET] == {"input": M, "output": M}
    assert u.models_used[HAIKU] == 2   # call count preserved
    assert u.models_used[SONNET] == 1


def test_session_totals_always_match_sum_of_calls():
    u = start_session()
    track_usage(400_000, 100_000, model=HAIKU)
    track_usage(600_000, 900_000, model=SONNET)
    track_usage(200_000, 50_000)  # unattributed

    assert u.input_tokens == 1_200_000
    assert u.output_tokens == 1_050_000


def test_no_model_calls_do_not_appear_in_per_model():
    u = start_session()
    track_usage(M, M)  # no model
    assert u.per_model == {}
    assert u.input_tokens == M


# ── compute_session_cost with empty per_model ─────────────────────────────────

def test_empty_per_model_falls_back_to_sonnet_totals():
    u = start_session()
    track_usage(M, M)  # no model — per_model stays empty
    # Falls back to total tokens at Sonnet rates
    assert compute_session_cost(u) == 18.0


# ── to_dict includes per_model ────────────────────────────────────────────────

def test_token_usage_to_dict_includes_per_model():
    u = start_session()
    track_usage(M, M, model=HAIKU)
    d = u.to_dict()
    assert "per_model" in d
    assert d["per_model"][HAIKU] == {"input": M, "output": M}
    assert d["models_used"][HAIKU] == 1
