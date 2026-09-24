# v1.2 replay verification artifacts

Benchmark: `--mode compare --inventory replay --query-count 12` (12 queries × 2 modes).

- `*_unpinned_day1.*`, `*_unpinned_day2.*` — runs on different calendar days at
  default app temperatures. 17/20 paired runs bit-identical on rule-level
  metrics; Greece (baseline), Portugal Algarve (full), and Tokyo (full)
  differed in Round-1 conflict counts. Tokyo resolving fixtures cross-day
  confirms date-stable replay anchoring.
- `*_pinned_run1.*`, `*_pinned_run2.*` — same benchmark with replay decoding
  pinned to temperature 0: 21/24 paired runs identical on rule-level metrics.
  The 3 remaining diffs (Portugal baseline/full, Thailand full) are residual
  LLM API variance at temperature 0. Raw CSVs also differ by random per-run
  session UUIDs — compare normalized per query.

v1.1 published artifacts are unchanged; see tag v1.1-infoq.