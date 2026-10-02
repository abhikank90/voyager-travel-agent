#!/usr/bin/env bash
#
# Reproduce the published Voyager replay benchmark and check the outputs.
#
# One command for a stranger: reruns the committed-fixture replay benchmark,
# preserves the locked results/ and fixtures/ artifacts, and compares the run
# against benchmarks/expected_replay.json with a PASS/FAIL table.
#
# Usage:
#   ./scripts/reproduce.sh           # full replay (12 queries x 2 modes, ~40 min, ~$3)
#   ./scripts/reproduce.sh --quick   # first 3 queries, ~5-minute smoke check
#
# Requires ANTHROPIC_API_KEY (replay serves inventory from committed fixtures,
# but the LLM calls are live). Tracing is disabled for the run.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

QUICK=0
QUERY_COUNT=12

usage() {
  cat <<'EOF'
Usage: ./scripts/reproduce.sh [--quick]

Reruns the published replay benchmark and checks the outputs against the
expected values in benchmarks/expected_replay.json.

  --quick   Smoke check: first 3 queries only (~5 min, ~$0.50 in tokens)

Requires ANTHROPIC_API_KEY. Inventory is served from committed fixtures;
only the LLM calls are live.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --quick) QUICK=1; QUERY_COUNT=3 ;;
    -h | --help) usage; exit 0 ;;
    *)
      echo "error: unknown option: $arg" >&2
      usage
      exit 2
      ;;
  esac
done

# ── Pre-flight: API key (respect .env, like the benchmark itself) ─────────────
if [[ -z "${ANTHROPIC_API_KEY:-}" && -f .env ]]; then
  ANTHROPIC_API_KEY="$(python3 - <<'PY'
from dotenv import dotenv_values
print(dotenv_values(".env").get("ANTHROPIC_API_KEY", ""))
PY
)"
  export ANTHROPIC_API_KEY
fi
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "error: ANTHROPIC_API_KEY is not set." >&2
  echo "  Replay serves inventory from committed fixtures, but the LLM calls" >&2
  echo "  are live. Export the key, e.g.  export ANTHROPIC_API_KEY=sk-ant-..." >&2
  exit 1
fi

# ── Pre-flight: replay fixtures exist ─────────────────────────────────────────
MANIFEST="fixtures/live_inventory/manifest.json"
if [[ ! -f "$MANIFEST" ]]; then
  echo "error: replay manifest not found: $MANIFEST" >&2
  echo "  The committed replay fixtures are required; aborting." >&2
  exit 1
fi
FIXTURE_COUNT="$(python3 - "$MANIFEST" <<'PY'
import json
import sys

with open(sys.argv[1]) as fh:
    print(len(json.load(fh).get("fixtures", {})))
PY
)"
if [[ -z "$FIXTURE_COUNT" || "$FIXTURE_COUNT" -eq 0 ]]; then
  echo "error: replay manifest contains no fixtures." >&2
  exit 1
fi

# ── Work dir and cleanup ──────────────────────────────────────────────────────
SESSIONS="metrics/sessions.jsonl"
STATUS="failed"
WORK="$(mktemp -d "${TMPDIR:-/tmp}/voyager-repro.XXXXXX")"
SESSIONS_BAK="$WORK/sessions.jsonl.bak"

cleanup() {
  # Never leave results/ or fixtures/ modified, even if the run fails midway.
  git restore --quiet results/ fixtures/ 2>/dev/null || true
  if [[ -f "$SESSIONS_BAK" ]]; then
    mv -f "$SESSIONS_BAK" "$SESSIONS"
  fi
  if [[ "$STATUS" == "done" ]]; then
    rm -rf "$WORK"
  else
    echo "outputs preserved in: $WORK"
  fi
}
trap cleanup EXIT

if ! git diff --quiet -- results/ fixtures/; then
  echo "warning: results/ or fixtures/ has uncommitted changes; they will be" >&2
  echo "  restored to HEAD after this run (locked v1.1 artifacts stay pristine)." >&2
fi

# Start this run's session log from a clean slate so the artifacts cover
# exactly this run; the prior log is restored at exit.
if [[ -f "$SESSIONS" ]]; then
  cp "$SESSIONS" "$SESSIONS_BAK"
  rm -f "$SESSIONS"
fi

# ── Run the benchmark ─────────────────────────────────────────────────────────
echo
if [[ "$QUICK" == "1" ]]; then
  echo "SMOKE CHECK — first $QUERY_COUNT queries ($((QUERY_COUNT * 2)) sessions, ~5 min)"
else
  echo "FULL REPLAY — $QUERY_COUNT queries x 2 modes ($((QUERY_COUNT * 2)) sessions, ~40 min, ~\$3)"
fi
echo "work dir: $WORK"
LANGCHAIN_TRACING_V2=false LANGSMITH_TRACING=false \
  python3 scripts/benchmark_queries.py --mode compare --inventory replay --query-count "$QUERY_COUNT"

cp metrics/sessions.jsonl "$WORK/sessions.jsonl.new" 2>/dev/null || true

# ── Preserve outputs, then restore the locked artifacts ───────────────────────
RUN_DIR="$WORK/run_results"
mkdir -p "$RUN_DIR"
for f in run_summary.json conflicts_by_round.csv conflict_lifecycle.csv hybrid_candidates.csv inventory_manifest.json; do
  if [[ -f "results/$f" ]]; then
    cp "results/$f" "$RUN_DIR/"
  fi
done
git restore --quiet results/ fixtures/

# ── Compare ────────────────────────────────────────────────────────────────────
echo
if [[ "$QUICK" == "1" ]]; then
  python3 scripts/compare_results.py --quick benchmarks/expected_replay.json "$RUN_DIR"
else
  python3 scripts/compare_results.py benchmarks/expected_replay.json "$RUN_DIR"
fi
rc=$?

if [[ "$rc" -eq 0 ]]; then
  STATUS="done"
else
  echo "comparison FAILED — outputs preserved in: $WORK"
fi
exit $rc