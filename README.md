# Voyager: Targeted Peer Feedback for Multi-Agent Conflict Resolution

[![DOI](https://zenodo.org/badge/1240210492.svg)](https://doi.org/10.5281/zenodo.21269752)

[![CI](https://github.com/abhikank90/voyager-travel-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/abhikank90/voyager-travel-agent/actions/workflows/ci.yml)

**A coordination pattern for multi-agent LLM systems: typed conflict detection, targeted peer feedback, and selective re-execution.** Voyager demonstrates the pattern on a real problem — multi-agent travel planning — where parallel specialist agents produce locally optimal but globally incoherent results, and resolves them for a cost overhead that sits within ordinary per-query output variance.

| Metric (25-query benchmark, 2 modes) | Without hub (baseline) | With hub (full) |
|---|---|---|
| Cross-agent conflicts surviving into final output | 2.04 / query | **0.08 / query** (97% resolved) |
| Cost per query | $0.1740 | $0.1772 (**+1.8%**) |
| End-to-end latency | 219.5s | 225.5s (**+2.7%**) |
| Agent calls vs. naive "re-run everything" | — | **−30%** |

*Estimated costs were validated against billed API usage for the benchmark window (agreement within 1%). The cost overhead is statistically indistinguishable from per-query output variance — see [Benchmarks](#benchmarks) for methodology, paired statistics, and caveats.*

---

## Demo

![Voyager Travel Agent Demo](docs/demo/voyager-demo.gif)

*Watch Voyager generate personalized trip options in real-time as agents collaborate to find flights, hotels, and experiences.*

---

## The Problem

The dominant pattern for multi-agent systems is **parallel fan-out/gather**: decompose a task, run specialist agents concurrently, merge results. It's fast and modular — and it has a structural flaw: **each agent optimizes locally with no knowledge of its peers' outputs.**

In travel planning, that looks like:

- The hotel agent books the best-value hotel — on the opposite side of the destination from every activity the experience agent selected.
- The flight agent picks the cheapest fare — landing at 22:30, wasting the first day of a 7-day trip.
- The experience agent plans beach days — during the week the weather agent flagged a heat wave.

Each output is individually defensible. The combination is incoherent. In our benchmark, every query produced at least one cross-agent conflict after the parallel round (2.0 on average) — and in a single-pass architecture, all of them ship to the user.

The well-documented fixes are expensive or imprecise:

- **Sequential pipelines** eliminate conflicts by serializing everything — and give up the latency win of parallelism.
- **Debate / generator-critic loops** re-run *all* agents with broadcast critique until convergence — effective, but cost scales with rounds × agents, and unstructured natural-language critique gives no guarantee the right agent gets the right constraint.

## The Pattern

Voyager inserts a **Collaboration Hub** between research rounds. It does three things, all deliberately narrow:

```
            ┌──────────────────────── Round 1 (parallel) ───────────────────────┐
            │  Flight    Hotel    Experience    Weather    Visa/Safety          │
            └──────────────────────────────┬─────────────────────────────────────┘
                                           ▼
                                 ┌──────────────────┐
                                 │ Collaboration Hub │
                                 │  1. detect typed  │
                                 │     conflicts     │
                                 │  2. route targeted│
                                 │     constraints   │
                                 └────────┬──────────┘
                          conflicts? ──── no ──→ final audit → budget guardrail → options
                                           │ yes
                                           ▼
            ┌────────── Round 2 (selective — only agents that received messages) ─┐
            │            Hotel ✓          Flight ✓        (others skipped)        │
            └──────────────────────────────┬───────────────────────────────────────┘
                                           ▼
                                 (hub re-checks; ≤1 more round)
```

**1. Typed conflict detection (deterministic by design).** The hub checks the merged state against a registry of *typed* conflict rules — `location_mismatch`, `timing_inefficiency`, `weather_activity_mismatch` — each a cheap, deterministic predicate over structured agent outputs. Detection is intentionally rule-based rather than LLM-based: typed conflicts are what make the next two steps possible. You can only route a constraint *to the hotel agent specifically* if you know *structurally* that the conflict is a hotel-location/activity-location mismatch. (The hub does call Claude once per round — to generate a narrative analysis surfaced in the UI; that narrative is deliberately ignored for routing.)

**2. Targeted constraint routing.** Each detected conflict generates a message addressed to the *one agent best positioned to resolve it*, carrying structured data, not prose: the hotel agent receives `{activity_locations: ["Oia, Santorini", ...]}`; the flight agent receives `{preferred_arrival: "before 14:00"}`. This is the inversion of the usual coordinator pattern — instead of routing a *user request* to specialists at the start, the hub routes *inter-agent critique* to specialists mid-execution. Detection, routing, and the feedback messages themselves are all deterministic; the only LLM work in a refinement round happens *inside* the agents that re-run.

**3. Selective re-execution.** Only agents that received messages re-run. Each rerunnable agent reads its inbox via `BaseAgent._messages_for_me()` and applies constraints at *selection time* — the hotel agent prefers affordable candidates matching the suggested area; the flight agent prefers fares satisfying the arrival window — falling back gracefully when no candidate qualifies. Agents that received nothing are skipped, and their Round-1 outputs stand. Across the benchmark, Round 2 re-ran the flight and hotel agents (the two implicated in every query's conflicts) while the experience, weather, and visa agents stayed dormant.

A **final conflict audit** (same deterministic detectors, no routing) runs after the last round, so the system reports honestly which conflicts were resolved and which persist — persisting conflicts are surfaced, not hidden.

The round cap is the **shape of the graph**, not a configurable constant: `research_round_1`, `research_round_2`, and `research_round_3` are distinct hard-wired nodes, so the loop is bounded by topology rather than by a counter that a bug could mismanage.

### Why not just one big agent?

A single agent with all five specialties in one prompt avoids coordination entirely — and gives up parallelism, per-domain model/tool selection, independent testing, and bounded context per concern. The interesting regime is where you've *already* decided multiple agents are right (latency, modularity, separate data sources) and need coherence without paying the full debate-loop tax. That's what this pattern is for.

## Benchmarks

**Setup:** 25 diverse trip queries (beach, city, adventure, budget, family) × 2 modes. *Full* runs the complete graph; *baseline* skips the hub's routing and refinement rounds (Round 1 → audit → options). Both modes run identical detectors at audit time, so final-conflict counts are directly comparable. Both modes also see identical simulated inventory per query, which isolates the coordination pattern from inventory drift. Reproduce against tag `v1.0-infoq` with:

```bash
python3 scripts/benchmark_queries.py --mode compare
python3 scripts/benchmark_queries.py --summary
```

**Results (50 sessions, June 2026; `claude-sonnet-4-6` + `claude-haiku-4-5`):**

| | Baseline | Full |
|---|---|---|
| Queries with ≥1 Round-1 conflict | 25/25 | 25/25 |
| Avg Round-1 conflicts / query | 2.0 | 2.0 |
| Avg conflicts in final output | 2.04 | **0.08** (97% resolved) |
| Queries needing Round 2 | — | 25/25 |
| Queries needing Round 3 | — | 1/25 |
| Avg agents re-run per refinement | — | 2.1 (of 5) |
| Agent-call savings vs. full re-run | — | 30% |
| Avg cost / query | $0.1740 | $0.1772 (**+1.8%**) |
| Avg latency / query | 219.5s | 225.5s (**+2.7%**) |

Reported as paired per-query deltas: cost +$0.0032/query mean (median +$0.0026, σ $0.0086); latency +6.0s mean (median +4.3s, σ 11.9s). The cost overhead's standard deviation is roughly three times its mean — the coordination cost is statistically indistinguishable from ordinary generation-length noise at the per-query level, visible only in aggregate. Estimated costs (summed from per-model token usage at published rates) matched billed API usage for the benchmark window within 1%.

The one unresolved conflict was a `weather_activity_mismatch` on a query whose stated interests *were* the flagged outdoor activities — the advisory competes with user preferences rather than overriding them, and the system reports the tension instead of silently dropping it.

**Three caveats:**

1. **Conflict incidence is a property of the workload, not the world.** Benchmarks run against simulated flight/hotel/weather inventory (deterministic fixtures; all agent reasoning, conflict detection, routing, and re-execution are real Claude calls). The fixtures are constructed so that locally-optimal agent choices start every query in conflict — that's what makes resolution measurable and reproducible, and what lets baseline and full modes see an identical world per query. The 100% incidence describes this controlled setup, not real-world travel workloads. Agent *selections* remain stochastic (temperature 0.3), so Round-1 conflict counts vary slightly run to run.
2. **Resolution rate measures coordination mechanics given satisfiable data.** The fixture inventory always contains a qualifying option. With real inventory, satisfiability isn't guaranteed — the pattern routes feedback to the right agent; it cannot conjure a hotel that doesn't exist. Claim: *given a satisfiable option space, the coordination layer resolves 97% of conflicts within ≤3 rounds.*
3. **Selective re-execution saves cost, not latency.** Rounds run under `asyncio.gather`, so duration is bounded by the slowest member, not the count. The end-to-end latency delta (+6.0s, paired) and the standalone Round-2 wall time (16.2s) are separate measurements and should not be read as summing — per-query duration variance (σ 11.9s) is roughly twice the size of the overhead being measured. The durable win is in agent *invocations*: Round 2 re-runs ~2 of 5 agents instead of all of them, a 30% call reduction that grows in importance as agents get heavier and more expensive.

Full details on workload design, inventory construction, cost estimation methodology, and planned live-inventory follow-up: **[ARCHITECTURE.md & Benchmark Methodology](ARCHITECTURE.md#benchmark-methodology)**.

## Example: Location Conflict, End to End

A real trace from the benchmark (Greece, $2,000, beaches and local food):

**Round 1 (parallel):** HotelAgent selects a Beachfront hotel; ExperienceAgent's top activities cluster in *Oia, Santorini*.

**Hub:** `location_mismatch` detected → one constraint message, to the hotel agent only:

```json
{
  "to_agent": "hotel",
  "message_type": "constraint",
  "content": "Top experiences cluster in a different area than the selected hotel.",
  "data": { "activity_locations": ["Oia, Santorini", "Perissa Beach"] },
  "round": 1
}
```

**Round 2 (selective):** Only the hotel agent re-runs. It reads the constraint and prefers an affordable candidate in Oia at selection time. Flight, weather, and visa agents are skipped — their outputs stand.

**Audit:** `location_mismatch` no longer fires. The conflict is resolved with one extra agent invocation instead of five.

(Earlier versions sent messages in both directions — also asking the experience agent to consider activities near the original hotel. That created circular chasing; the current design picks one resolution direction per conflict type: the hotel follows the experiences.)

## System Architecture

<img src="docs/diagrams/Voyager-travel-agent.drawio.png" alt="Voyager Travel Agent - System Architecture" width="100%">

**The application around the pattern:** Voyager is a full-stack travel planner producing three trip variants (budget / balanced / premium) with day-by-day itineraries and booking links.

- **Backend:** Python 3.11+, FastAPI, LangGraph state machine (`graph/travel_graph.py`) — nodes: `personalisation → intent_parser → research_round_1 → collaboration_hub_1 → [research_round_2 → collaboration_hub_2 → research_round_3] → final_conflict_audit → budget_guardrail → option_generator`, with conditional edges short-circuiting refinement when no conflicts fire.
- **Agents (11):** five parallel research agents (flight, hotel, experience, weather, visa/safety), the Collaboration Hub, a budget guardrail (hard correctness gate, ≤2 retries), option generator, personalisation, intent parser, itinerary builder. All share a typed `TravelState` (`graph/state.py`).
- **AI:** Anthropic Claude — `claude-sonnet-4-6` for synthesis and hub/option generation, `claude-haiku-4-5` for the flight, hotel, and visa/safety research agents. Per-agent model selection lives in `config/api_config.py`.
- **Frontend:** React 18 + TypeScript + Vite + Tailwind; live collaboration feed renders hub messages and per-round agent activity over WebSocket.
- **Infrastructure:** AWS (ECS Fargate, DynamoDB, SQS, ALB); LangSmith for observability.
- **External data:** real APIs when keys are present, deterministic mock fallbacks otherwise — see [API_REQUIREMENTS.md](API_REQUIREMENTS.md).

## Quick Start

```bash
git clone https://github.com/abhikank90/voyager-travel-agent.git
cd voyager-travel-agent
pip install -e ".[dev]"
cp .env.example .env        # add ANTHROPIC_API_KEY (only required key)
uvicorn api.main:app --reload          # backend
cd frontend && npm ci && npm run dev   # frontend
```

Full setup (Docker, AWS deployment, LangSmith): **[GETTING_STARTED.md](GETTING_STARTED.md)**.

```bash
# Run the test suite (116 unit tests)
python3 -m pytest tests/unit -q

# Run the benchmark yourself
python3 scripts/benchmark_queries.py --limit 3      # smoke test (~$0.50)
python3 scripts/benchmark_queries.py --mode compare # full 50-session benchmark (~$9)
```

## Design Decisions

**Deterministic detection, LLM reasoning.** Claude does what it's good at — parsing intent, generating experiences, synthesizing options, narrating analysis. Conflict detection stays rule-based because typed conflicts are the contract that targeted routing and selective re-execution depend on, and because deterministic detection makes benchmarks reproducible. A controlled evaluation (`scripts/eval_hybrid_detection.py`) measured an LLM detector against the rules on the same states: at temperature 0 it was fully self-consistent and caught conflict types the rules don't enumerate, but it also asserted an unverifiable budget violation on a clean control case. The takeaway shapes the roadmap — let the LLM *propose* candidate conflicts and let deterministic rules *validate* before anything triggers a re-run, since in this pattern a detection event spends money. Put another way: the LLM is allowed to be curious, the rules are allowed to be certain, and only certainty is allowed to spend money.

**One resolution direction per conflict type.** Bidirectional messages ("hotel, move near the activities" + "experiences, find some near the hotel") cause oscillation. Each conflict type names a single agent responsible for resolving it.

**Constraints filter selection; sources only need to contain a qualifying option.** Agents apply constraints when *choosing* among candidates rather than depending on data-source-specific query parameters — identical behavior across real APIs and mocks, robust to result ordering.

**Honest auditing.** The final audit uses the same detectors as Round 1 and reports unresolved conflicts in the output rather than suppressing them.

**Mock fallbacks for every external API.** The system is fully runnable with one API key, demos are deterministic, and CI needs no secrets.

## Limitations & Roadmap

Known limitations: resolution depends on a satisfiable option space (the pattern routes feedback; it can't create inventory); conflict coverage is currently three typed rules; benchmark inventory is fixture-based; per-type resolution varies by design (preference-competing conflicts persist and are reported).

Roadmap:

- **LLM-augmented conflict detection** — Claude proposes candidate conflicts beyond the typed registry; deterministic rules validate before routing (keeps the audit stable and re-runs grounded).
- **Live-inventory validation via record/replay** — capture real Amadeus/OpenWeather responses into fixtures and replay them deterministically, measuring resolution under real-world (non-guaranteed) satisfiability without sacrificing reproducibility.
- **Return-leg flight modeling** — enables the timing rule for departure legs that genuinely waste trip days.
- **Conflict-churn metrics** — track when one agent's re-run introduces *new* conflicts, quantifying convergence behavior across rounds.
- **Pattern extraction** — the hub, message protocol, and selective re-execution as a reusable LangGraph library independent of the travel domain.

## Documentation

📚 **Complete documentation for this project:**

- **[GETTING_STARTED.md](GETTING_STARTED.md)** - Installation, setup, and quick start guide
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Detailed component reference: all 11 agents, state schema, API endpoints, frontend, benchmark methodology
- **[API_REQUIREMENTS.md](API_REQUIREMENTS.md)** - External API requirements, keys, and mock fallbacks
- **[TESTING.md](TESTING.md)** - Comprehensive testing guide with coverage targets
- **[CLAUDE.md](CLAUDE.md)** - Development guidance for Claude Code and contributors

## License

MIT — see [LICENSE](LICENSE).
