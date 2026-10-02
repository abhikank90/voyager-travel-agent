# Design Decisions

This document records the reasoning behind Voyager's core design choices: the
problem each decision solves, the alternatives considered, and why they were
rejected. It complements ARCHITECTURE.md, which describes *what* the system is;
this describes *why* it is that way.

## 1. Deterministic conflict detection, with the LLM in an advisory role

**Decision.** Conflicts are detected by a registry of typed, deterministic rules
(`location_mismatch`, `timing_inefficiency`, `weather_activity_mismatch`)
evaluated over structured agent outputs. The hub does call an LLM once per round
— to generate a narrative analysis surfaced in the UI — and that narrative is
deliberately ignored for routing.

**Why.** A detection event spends money: it triggers selective re-execution of
agents. Routing authority therefore requires verifiable evidence, not plausible
prose. A controlled evaluation (`scripts/eval_hybrid_detection.py`) measured an
LLM detector against the rules on identical states: at temperature 0 it was
fully self-consistent and caught conflict classes the rules don't enumerate
(visa lead-time, dietary preference, budget component sums) — but it also
asserted an unverifiable budget violation on a clean control case. One
hallucinated trigger buys an unnecessary re-run.

**Alternatives rejected.**

- *Pure LLM judging* — unverifiable assertions, non-reproducible benchmarks,
  false positives with a direct dollar cost.
- *Hybrid where the LLM's proposals route directly* — implemented instead as a
  flag-gated configuration where the LLM proposes and deterministic validators
  gate. Current eval: the LLM catches 3/3 rule-invisible conflict classes, but
  0/10 of its candidates pass validation, because validators for those classes
  don't exist yet. Writing them is roadmap work.

The operating principle: the LLM is allowed to be curious, the rules are allowed
to be certain, and only certainty is allowed to spend money.

## 2. Targeted routing instead of full-panel review

**Decision.** Each detected conflict generates one message addressed to the
single agent best positioned to resolve it; only that agent re-runs.

**Alternatives rejected.**

- *Debate / generator-critic loops with broadcast critique* — cost scales with
  rounds × agents, and unstructured natural-language critique gives no guarantee
  the right agent receives the right constraint. You can only route a constraint
  to the hotel agent specifically if you know structurally that the conflict is
  a hotel-location/activity-location mismatch — which is what typed detection
  provides.
- *Full re-run of all agents per round* — the measured cost of that approach is
  what targeted routing saves: 30% fewer agent calls on synthetic inventory, 41%
  on real API inventory.
- *Sequential pipeline* — eliminates conflicts by serializing everything and
  gives up the latency win of parallel research rounds.

## 3. One resolution direction per conflict type

**Decision.** Each conflict type names a single responsible agent (e.g., for
`location_mismatch`, the hotel moves toward the activities — the activities do
not move toward the hotel). That mapping lives in one place
(`CONFLICT_RESOLVER` in `agents/conflicts.py`): the hub routes each type's
feedback message to it, and Round 3 re-runs exactly that same resolver.

**Why.** Bidirectional messages ("hotel, move near the activities" +
"experiences, find some near the hotel") cause oscillation: both agents adjust
in the same round, each invalidating the other's new constraint, and the
conflict reopens. A fixed direction makes convergence analyzable and the round
cap meaningful.

## 4. Typed constraint payloads, not prose

**Decision.** Feedback messages carry structured data: a geocoded activity
centroid (`{lat, lon}`), arrival-time windows, weather advisory labels — never
natural-language suggestions.

**Why.** Substring matching does not survive contact with real inventory
payloads: an activity in "Oia, Santorini" cannot be matched against a hotel
address string like "600 Center Place Drive". The experience agent resolves each
activity's location string to coordinates via a free geocoding endpoint, and the
hotel agent distance-matches candidates against the centroid. The typed
payload's producer must emit the type the consumer needs — that contract is the
real coordination mechanism.

## 5. Content-addressed conflict fingerprints

**Decision.** Every conflict gets a SHA-256 identity computed from its type, the
agents involved, and normalized evidence data — never from prose.

**Why.** This makes the introduced/resolved/reopened lifecycle classification
honest: the tracker can distinguish "same conflict persisting" from "new
conflict introduced" across rounds. The 0.42/query introduction rate on live
inventory came from Round 3 re-running every participant in each surviving
conflict — including the experience agent, which was never messaged for a
location conflict — so its LLM re-execution produced a genuinely different
activity set and, with it, different location constraints. Content-addressed
fingerprints make that churn visible rather than masked, and prose
fingerprints would be unstable under LLM paraphrase; the fix here (§3) re-runs
only the designated resolver per conflict type, so the experience agent is no
longer re-executed for conflicts it does not resolve.

## 6. Constraints filter selection; sources only need to contain a qualifying option

**Decision.** Agents apply constraints when choosing among candidates rather
than depending on data-source-specific query parameters, and fall back honestly
(`fallback_to_original_selection: true, reason: no_qualifying_option`) when no
candidate qualifies.

**Why.** Identical behavior across real APIs and mocks, robustness to result
ordering, and no forced bad picks: when real inventory contains no hotel within
25km of the activity centroid, the system says so instead of silently shipping a
bad one.

## 7. Bounded rounds via graph topology, not a counter

**Decision.** `research_round_1`, `research_round_2`, and `research_round_3` are
distinct hard-wired nodes; the loop is bounded by the shape of the graph.

**Why.** A configurable max-rounds counter is a bug surface — misconfiguration,
off-by-one, or a runaway loop. Topology makes the bound structural, visible in
the graph definition, and impossible to mismanage.

## 8. Honest auditing over success theater

**Decision.** A final audit runs the same deterministic detectors used in Round
1 and reports persisting conflicts in the output rather than suppressing them.

**Why.** On real API inventory, 67% of queries end with at least one
unsatisfiable constraint — reality often doesn't contain a qualifying option.
Hiding that would inflate the apparent resolution rate and hollow out the
benchmark. The mock/live contrast (100% vs 10% resolution) is the system's core
finding, and it is only visible because the audit is honest.

## 9. Reproducibility architecture: mock / capture / replay

**Decision.** Three inventory modes with escalating fidelity:

- **mock** — deterministic fixtures, fully offline; CI, unit tests, and
  zero-friction reproduction of the published synthetic benchmarks.
- **capture** — live APIs (SerpApi, Nuitee, OpenWeather) with hash-verified
  fixture recording.
- **replay** — inventory served from captured fixtures; query dates anchored to
  the fixtures' capture date recorded in the manifest (not the calendar), and
  decoding pinned to temperature 0 via a central `effective_temperature()`
  resolver.

**Why the anchoring and pinning exist.** Replay originally derived query dates
from the wall clock, so fixtures became unfindable across a date boundary — the
defect that excluded a query from the v1.1 replay dataset. Date anchoring fixed
the fixture layer; temperature pinning addressed the second nondeterminism
source. Verification (see `results/v1.2/`): pinning raised exact rule-level
matches from 17/20 paired runs (default temperatures) to 21/24 (pinned). The
residual variance is Anthropic API nondeterminism at temperature 0; fully
byte-identical replay requires recording and replaying LLM responses, which is
on the roadmap.

## 10. Budget guardrail as a hard correctness gate

**Decision.** The budget check is a hard gate (≤2 retries) before option
generation, not a soft warning.

**Why.** Cost correctness is the invariant every other metric assumes; a system
that detects and resolves conflicts but misprices the result has failed the
user regardless.

## Rejected alternatives, summarized

| Alternative | Decision area | Why rejected |
|---|---|---|
| Pure LLM conflict judging | Detection | Unverifiable assertions; false positives spend money; non-reproducible |
| Debate / broadcast critique | Routing | Cost scales rounds × agents; no guarantee the right agent gets the right constraint |
| Sequential pipeline | Architecture | Loses the parallelism latency win |
| Bidirectional resolution | Routing | Oscillation; reopened conflicts |
| Prose feedback messages | Payloads | Unmatchable against real inventory payloads |
| Constant or prose fingerprints | Tracking | Masks churn, or unstable under paraphrase |
| Configurable round counter | Graph | Bug surface; topology is structural |
| Same-day capture/replay | Reproducibility | Replaced by date-stable anchoring |

## Non-goals

- **Booking execution** — Voyager recommends and links; it does not purchase.
- **General-purpose agent framework** — the hub, message protocol, and
  selective re-execution are designed so they *can* be extracted as a reusable
  LangGraph library, but that extraction is roadmap work, not current scope.

---

*For component-level details (agents, state schema, API, benchmark
methodology), see ARCHITECTURE.md.*