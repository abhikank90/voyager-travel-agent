# v1.3 replay measurement artifacts

Benchmark: `--mode compare --inventory replay --query-count 12` (12 queries ×
2 modes), run three times after the Round-3 resolver-targeting fix.

Context: Round 3 previously re-ran all conflict participants, re-invoking the
never-messaged experience agent on location conflicts and producing
post-refinement introductions (0.25–0.42/query in the v1.2 pinned runs; see
results/v1.2/). The fix routes Round 3 through the shared CONFLICT_RESOLVER
map so only the designated resolver re-runs.

Result — three identical post-fix runs:
- post-refinement introductions: 0.0/query (all 3 runs)
- agent-call savings: 45.2% (pre-fix 36.9%)
- mean re-executed agents: 2.42 (pre-fix 3.46)
- resolution rate: 10% (unchanged)
- reopened conflicts: 0

run1/ ran on the fix branch pre-merge (identical code); run2/ and run3/ on
main. v1.1 published artifacts are unchanged; see tag v1.1-infoq.