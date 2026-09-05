```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                          │
│  React + TypeScript Frontend (Vite + Tailwind CSS)             │
│                                                                 │
│  Components:                                                    │
│  • CollaborativeChatInterface  (main orchestrator)             │
│  • OptionSelector              (3-option comparison grid)       │
│  • TripOptionCard              (budget/balanced/premium card)   │
│  • DetailedItineraryView       (full itinerary + booking URLs)  │
│  • CollaborationFeed           (real-time agent messages)       │
│  • AgentStatusPanel            (progress tracking)              │
└─────────────────────────────────────────────────────────────────┘
                              ↕ WebSocket
┌─────────────────────────────────────────────────────────────────┐
│                          API LAYER                              │
│  FastAPI (Python)                                               │
│                                                                 │
│  Endpoints:                                                     │
│  • POST   /api/travel/collaborative  (generate 3 options)       │
│  • POST   /api/travel/select-option  (user selects)            │
│  • POST   /api/travel/refine         (refinement requests)      │
│  • WS     /ws/travel/collaborative/{session_id} (streaming)     │
│  • GET    /health                    (health check)             │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                    LANGGRAPH STATE MACHINE                      │
│  Multi-Round Collaborative Workflow                             │
│                                                                 │
│  1. Personalisation → Load user profile                         │
│  2. Intent Parser   → Parse query into structured intent        │
│  3. Round 1         → All 5 agents research in parallel         │
│  4. Collab Hub 1    → Analyze findings, send messages           │
│  5. Round 2         → Agents refine based on feedback           │
│  6. Collab Hub 2    → Check if conflicts resolved               │
│  7. Round 3         → Final optimization (if needed)            │
│  8. Final Audit     → Conflict lifecycle + convergence summary  │
│  9. Budget Guardian → Validate costs                            │
│ 10. Option Generator→ Create 3 trip variants                    │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                       AGENT LAYER                               │
│                                                                 │
│  Research Agents (Parallel):                                   │
│  • FlightAgent       → SerpApi Google Flights / mock            │
│  • HotelAgent        → Nuitee (LiteAPI) / mock                  │
│  • ExperienceAgent   → Claude + destinations.json RAG           │
│                        + OpenWeather geocoding                  │
│  • WeatherAgent      → OpenWeather One Call API / mock          │
│  • VisaSafetyAgent   → DuckDuckGo search + Claude               │
│                                                                 │
│  Coordination Agents:                                           │
│  • CollaborationHubAgent → Conflict detection, message routing  │
│  • ConflictLifecycleTracker → Fingerprint identity + churn      │
│  • HybridConflictDetector  → LLM proposals (flag-gated, off)    │
│  • OptionGeneratorAgent    → Generate 3 trip variants           │
│  • BudgetGuardrailAgent    → Cost validation                    │
│                                                                 │
│  Support Agents:                                                │
│  • PersonalisationAgent  → User profile loading                 │
│  • IntentParserAgent     → Query → TravelIntent                 │
│  • ItineraryBuilderAgent → Legacy synthesis                     │
│                                                                 │
│  Infrastructure:                                                │
│  • InventoryManager      → Capture/replay/mock fixture control  │
│  • MetricsCollector      → Session recording + aggregation      │
│  • TokenTracker          → Per-model cost tracking              │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                            │
│                                                                 │
│  • Anthropic Claude API   (required)                            │
│  • SerpApi Google Flights (optional - has mock)                 │
│  • Nuitee / LiteAPI       (optional - has mock)                 │
│  • OpenWeather API        (optional - has mock)                 │
│  • DuckDuckGo Search      (free, no key)                        │
│  • DynamoDB               (optional - user profiles)            │
│  • LangSmith              (optional - observability)            │
└─────────────────────────────────────────────────────────────────┘
```

---

**Tech Stack**:
- **Backend**: Python 3.11+, FastAPI, LangGraph, LangChain
- **AI**: Anthropic Claude (Sonnet & Haiku)
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS
- **Infrastructure**: AWS (ECS Fargate, DynamoDB, SQS, ALB)
- **Observability**: LangSmith

---

## LangGraph State Machine

The core workflow is a LangGraph `StateGraph` that manages state flow through nodes.

### State Schema (`graph/state.py`)

```python
class TravelState(TypedDict):
    # Input
    user_query: str
    user_id: str
    session_id: str

    # Parsed intent
    intent: dict[str, Any]  # TravelIntent (destination, budget, dates, interests)

    # Collaboration tracking
    collaboration_round: int  # 1, 2, or 3
    agent_messages: list[CollaborationMessage]
    shared_discoveries: dict[str, Any]
    conflicts: list[dict]
    synergies: list[dict]

    # Conflict lifecycle tracking
    conflict_lifecycle_state: dict  # Serialized ConflictLifecycleTracker
    conflict_lifecycle: list[dict]  # All lifecycle records
    conflicts_introduced: list[dict]
    conflicts_resolved: list[dict]
    conflicts_persisting: list[dict]
    conflicts_reopened: list[dict]

    # Research results (refined over rounds)
    flights: list[dict]
    hotels: list[dict]
    experiences: list[dict]
    weather: dict
    visa_safety: dict

    # Budget validation
    budget_breakdown: dict
    budget_ok: bool

    # Multi-option output
    trip_options: list[TripOption]  # 3 variants
    selected_option_id: int | None

    # Refinement
    refinement_request: str | None
    refinement_history: list[dict]

    # Control
    status: str
    errors: dict[str, str]
```

### Graph Flow (`graph/travel_graph.py`)

```python
StateGraph(TravelState):

  personalisation
      ↓
  intent_parser
      ↓
  research_round_1  (parallel: flight, hotel, experience, weather, visa/safety)
      ↓
  collaboration_hub_1  (analyze, send messages, lifecycle audit)
      ↓ (conditional)
      ├─ If messages/conflicts → research_round_2
      └─ Else → final_conflict_audit
      ↓
  research_round_2  (selective re-run of targeted agents only)
      ↓
  collaboration_hub_2  (check if resolved, lifecycle audit)
      ↓ (conditional)
      ├─ If conflicts & round < 3 → research_round_3
      └─ Else → final_conflict_audit
      ↓
  research_round_3  (final refinement round)
      ↓
  final_conflict_audit  (detect_conflicts_only + convergence summary)
      ↓
  budget_guardrail  (validate costs)
      ↓
  option_generator  (create 3 variants)
      ↓
  END
```

The round cap is structural, not a configurable constant: `research_round_1`,
`research_round_2`, and `research_round_3` are distinct hard-wired nodes, so the
refinement loop is bounded by the shape of the graph rather than by a counter.

### Conditional Routing

```python
def route_after_hub_1(state):
    if state.get("agent_messages") or state.get("conflicts"):
        return "research_round_2"  # Need refinement
    return "final_conflict_audit"  # No issues

def route_after_hub_2(state):
    if state.get("conflicts") and state.get("collaboration_round") < 3:
        return "research_round_3"  # Final round
    return "final_conflict_audit"  # Done collaborating
```

**Key Design**: Each node returns a partial dict of state updates. LangGraph automatically merges them into the running state.

---

## Agent Architecture

All agents extend `BaseAgent` (`agents/base_agent.py`):

```python
class BaseAgent(ABC):
    name: str          # Full agent name (e.g. "hotel_agent")
    short_name: str    # Hub-convention name (e.g. "hotel") — optional class attr
    description: str

    @traceable(name="agent_run")
    async def run(self, state: dict) -> dict:
        # Wrapper with LangSmith tracing + error handling
        result = await self._execute(state)
        return result

    @abstractmethod
    async def _execute(self, state: dict) -> dict:
        # Agent logic - must return state updates
        ...

    def _messages_for_me(self, state: dict) -> list[dict]:
        # Returns collaboration messages from prior rounds targeting this agent.
        # Matches both `name` and `short_name` so hub messages addressed to
        # "hotel" are received by HotelAgent (whose name is "hotel_agent").
        # Includes all prior-round messages — constraints are idempotent so
        # re-applying them is safe.
        current_round = state.get("collaboration_round", 1)
        my_ids = {self.name} | ({self.short_name} if hasattr(self, "short_name") else set())
        return [
            m for m in state.get("agent_messages", [])
            if m.get("to_agent") in my_ids | {"all"}
            and m.get("round", 0) < current_round
        ]
```

**The feedback loop** (Round 1 → Hub → Round 2) is closed by `_messages_for_me`. In Round 2, each research agent calls this helper and applies any constraints before selecting its result:
- `HotelAgent` — prefers candidates whose coordinates are within 25km of the activity centroid (typed constraint), falls back to substring matching on location hint (mock-compatible)
- `FlightAgent` — prefers options arriving before `preferred_arrival` hour
- `ExperienceAgent` — prepends weather/timing guidance to the LLM prompt via `location_focus`

Across the benchmark, the agents re-run in a refinement round are the ones
implicated by the detected conflicts; untargeted agents stay dormant and their
Round-1 outputs stand.

### Research Agents (Parallel Execution)

#### 1. FlightAgent (`agents/flight_agent.py`)

**Purpose**: Search for flights matching user intent.

**API**: SerpApi Google Flights (free tier: 100 searches/month)
- Single GET endpoint with IATA airport codes
- IATA resolution via internal `IATA_MAP` (~50 destinations); unresolvable names fall back to mock data rather than making a doomed API call

**Fallback**: Mock data (realistic prices/routes)

**Model**: `claude-haiku-4-5-20251001` (retrieval-shaped task)

**Output**: List of 3-5 flight options with:
- Airline, price, departure/arrival times
- Number of stops, duration
- Departure/arrival airports

**Code Location**: `agents/flight_agent.py`

#### 2. HotelAgent (`agents/hotel_agent.py`)

**Purpose**: Find hotels matching destination and budget.

**API**: Nuitee / LiteAPI (sandbox available)
- Three-call flow: destination → placeId (locality-preferred) → rates → per-hotel details
- Returns name, address, geo coordinates, pricing

**Fallback**: Mock data (realistic hotels, string-matched to hub location hints)

**Model**: `claude-haiku-4-5-20251001` (retrieval-shaped task)

**Output**: List of 5 hotel options with:
- Name, location, total price, geo coordinates
- Rating, amenities
- Description

**Code Location**: `agents/hotel_agent.py`

#### 3. ExperienceAgent (`agents/experience_agent.py`)

**Purpose**: Recommend activities based on user interests, with geocoded locations.

**Data Source**:
- Claude Sonnet with RAG over `data/knowledge_base/destinations.json`
- Contains curated experiences for multiple destinations

**Geocoding**: Each experience's human-readable location string is resolved to
lat/lon coordinates via the OpenWeather `/geo/1.0/direct` endpoint (free, no
subscription required). Geocoding is gated to `capture`/`replay` inventory modes
only — mock mode stays fully offline and deterministic. The coordinates feed the
collaboration hub's activity centroid, enabling distance-based hotel matching
against real inventory.

**Model**: `claude-sonnet-4-6` (reasoning + synthesis)

**Output**: List of 5-10 experiences with:
- Name, description, category
- Best time of day, location string
- Latitude/longitude (live modes only)
- Estimated cost

**Code Location**: `agents/experience_agent.py`

#### 4. WeatherAgent (`agents/weather_agent.py`)

**Purpose**: Provide weather information for travel dates.

**API**: OpenWeather One Call 3.0 (requires separate subscription beyond free tier)
- Geocoding: destination → lat/lon
- One Call: current conditions + 8-day daily forecast
- Source label: `openweather_current_8day` (honest about the forecast horizon)

**Fallback**: Historical climate averages by destination/month (`source: historical_average`)

**Output**: Weather data with:
- Average temperature (C/F)
- Summary conditions
- Source label for transparency

**Code Location**: `agents/weather_agent.py`

#### 5. VisaSafetyAgent (`agents/visa_safety_agent.py`)

**Purpose**: Provide visa requirements and safety information.

**Data Source**:
- DuckDuckGo search (free, no API key)
- Claude Haiku for summarization

**Model**: `claude-haiku-4-5-20251001` (summarization task)

**Output**: Visa & safety info with:
- Visa required (yes/no)
- Safety level (1-5)
- Entry requirements
- Travel advisories

**Code Location**: `agents/visa_safety_agent.py`

### Coordination Agents

#### 6. CollaborationHubAgent (`agents/collaboration_hub.py`)

**Purpose**: Coordinate multi-agent collaboration by analyzing findings and generating targeted messages.

**Responsibilities**:
1. Analyze all research agent outputs
2. Identify conflicts (hotel location, flight timing, weather mismatches) — deterministic, rule-based
3. Detect synergies (beachfront hotel + beach activities)
4. Generate targeted messages to agents — templated, with structured data payloads including typed constraints (activity centroid, preferred arrival, weather advisory labels)
5. Track conflict resolution progress via `ConflictLifecycleTracker`

Detection, routing, and the feedback messages themselves are all deterministic. The hub
also makes one Claude call per round to produce a narrative analysis surfaced in the UI,
but that narrative is deliberately ignored for routing — control flow depends only on the
typed conflict objects, which keeps benchmarks reproducible and re-runs grounded.

**Conflict Detection**:
```python
# Example: Hotel-Experience location mismatch
# Hub computes activity centroid from geocoded experience coordinates,
# checks hotel coordinates against 25km radius

# Message generated:
{
    "from_agent": "collaboration_hub",
    "to_agent": "hotel",
    "message_type": "constraint",
    "content": "Top experiences are located far from selected hotels. Consider hotels closer to activity hubs.",
    "data": {
        "activity_locations": ["Oia, Santorini", "Fira center"],
        "activity_centroid": {"lat": 36.42, "lon": 25.43},
        "current_hotel_location": "600 Center Place Drive, Greece, US (43.21,-77.67)"
    },
    "round": 1
}
```

**Message Types**:
- `insight`: Information sharing
- `constraint`: Hard requirement
- `question`: Request for alternatives
- `proposal`: Suggestion
- `conflict`: Flag incompatibility

**Model**: `claude-sonnet-4-6` (narrative analysis only; routing is rule-based)

**Code Location**: `agents/collaboration_hub.py`

#### 7. ConflictLifecycleTracker (`agents/conflicts.py`)

**Purpose**: Give every conflict a stable identity across rounds so the system can measure convergence vs. oscillation.

**How It Works**:
- Each conflict gets a **content-addressed fingerprint**: SHA-256 digest over its type, sorted agents, and normalized evidence data (never prose)
- Prose descriptions and round numbers are excluded so the same logical conflict keeps the same fingerprint
- Different queries' conflicts have different fingerprints (different evidence → different identity)
- Lifecycle classification: `new`, `persisting`, `resolved`, `reopened`
- State is fully serializable — travels through the LangGraph state dict between nodes

**Why It Matters**: Without content-addressed fingerprints, the tracker can't distinguish "same conflict persisting" from "new conflict introduced" — churn becomes invisible.

**Code Location**: `agents/conflicts.py`

#### 8. HybridConflictDetector (`agents/hybrid_conflict_detector.py`)

**Purpose**: Let an LLM propose candidate conflicts beyond what the rules enumerate, with deterministic validation gating.

**Architecture**: "LLM proposes, rules validate"
- LLM generates candidate conflicts from agent outputs (temperature 0, multiple repetitions for self-consistency)
- Each candidate is checked against deterministic validators before earning routing authority
- Candidates that fail validation are recorded as `unverified` but never trigger re-runs

**Flag-Gated**: Controlled by `VOYAGER_ENABLE_LLM_CONFLICT_CANDIDATES` (default: `False`). When disabled, the LLM never proposes and never spends tokens.

**Evaluation**: `scripts/eval_hybrid_detection.py` measures precision, recall, false-positive rate, and self-consistency against the rule-based baseline.

**Code Location**: `agents/hybrid_conflict_detector.py`, `scripts/eval_hybrid_detection.py`

#### 9. OptionGeneratorAgent (`agents/option_generator.py`)

**Purpose**: Generate 3 distinct trip variants from refined research.

**Strategies**:

**Budget Option (75% of budget)**:
- Cheapest flight (`min(flights, key=lambda f: f["price"])`)
- Budget hotel
- Free + low-cost experiences

**Balanced Option (100% of budget)**:
- Best value flight (custom scoring: price vs duration vs stops)
- Mid-range hotel (best rating-to-price ratio)
- Curated mix of free and paid experiences

**Premium Option (115% of budget)**:
- Direct flight, optimal timing
- Highest-rated luxury hotel
- Exclusive experiences

**Itinerary Generation**:
- Uses Claude Sonnet to build day-by-day plans
- Each option gets a unique itinerary tailored to its style
- Includes morning/afternoon/evening activities, meals, notes

**Booking URL Generation**:
```python
# Templates from config/api_config.py
flight_url = config.flight.booking_url_template.format(
    origin="JFK", destination="ATH", date="2026-07-01"
)
# → "https://www.google.com/travel/flights?q=JFK+to+ATH+2026-07-01"

hotel_url = config.hotel.booking_url_template.format(
    destination="Athens", checkin="2026-07-01", checkout="2026-07-08"
)
# → Nuitee deep link

experience_url = config.experience.booking_url_template.format(
    destination="Athens"
)
# → "https://www.getyourguide.com/s/?q=Athens"
```

**Model**: `claude-sonnet-4-6` (synthesis)

**Output**: 3 `TripOption` objects with:
- Full itinerary (day-by-day)
- All booking URLs
- Highlights & trade-offs
- Budget breakdown

**Code Location**: `agents/option_generator.py`

#### 10. BudgetGuardrailAgent (`agents/budget_guardrail.py`)

**Purpose**: Aggregate costs and validate against budget.

**Allocation Ratios**:
- Flights: 45%
- Hotel: 45%
- Activities: 10%
- Food: 15%
- Misc: 5%

(Total > 100% is intentional — triggers if sum exceeds budget)

**Output**: Budget breakdown with validation status.

**Code Location**: `agents/budget_guardrail.py`

### Support Agents

#### 11. PersonalisationAgent (`agents/personalisation.py`)

**Purpose**: Load user profile from DynamoDB or local storage.

**Data**: Previous trips, preferences, budget history

**Code Location**: `agents/personalisation.py`

#### 12. IntentParserAgent (`agents/intent_parser.py`)

**Purpose**: Parse natural language query into structured `TravelIntent`.

**Method**: Claude Sonnet with `with_structured_output(TravelIntent)`

**Model**: `claude-sonnet-4-6`

**Output**:
```python
{
    "destination": "Greece",
    "budget_usd": 2000,
    "duration_days": 7,
    "travel_month": "July",
    "interests": ["beaches", "local food"],
    "flexibility": "flexible"
}
```

**Code Location**: `agents/intent_parser.py`

#### 13. ItineraryBuilderAgent (`agents/itinerary_builder.py`)

**Purpose**: Legacy agent for building single itinerary.

**Status**: Still used as fallback, but `OptionGeneratorAgent` is primary.

**Code Location**: `agents/itinerary_builder.py`

---

## Infrastructure Components

### InventoryManager (`agents/inventory.py`)

**Purpose**: Manage the three inventory modes (mock/capture/replay) with hash-verified fixtures.

**Modes**:
- **mock**: Fully offline, deterministic fixtures. The deterministic fixture is the whole point (CI, unit tests, demos).
- **capture**: Hit real APIs, save responses as hash-verified JSON fixtures with a manifest.
- **replay**: Re-run against captured fixtures with zero network calls. Hash verification ensures fixture integrity.

**Key Constraint**: Capture and replay must run the same day. Effective trip dates are derived from the capture date (today + 90 days outbound), so query IDs embed dates. Running replay the next day produces different query IDs → `FileNotFoundError`.

**Fixture Format**: Each fixture is a sanitized JSON payload with a SHA-256 content hash recorded in `manifest.json`. Sanitization strips API keys and opaque tokens.

**Code Location**: `agents/inventory.py`

### MetricsCollector (`metrics/collector.py`)

**Purpose**: Record benchmark sessions and compute aggregate metrics.

**Records per session**:
- Conflict counts by round, resolution rate, convergence round
- Conflict lifecycle records (fingerprints, statuses, transitions)
- Token usage and cost per model
- Latency by round
- Agent-call savings vs. naive full re-run
- Feedback metrics (constraint applied, satisfiable, fallback reason)

**Aggregate outputs**:
- `run_summary.json`: Headline metrics
- `conflicts_by_round.csv`: Per-session round counts
- `conflict_lifecycle.csv`: Per-conflict identity + transitions
- `hybrid_candidates.csv`: LLM candidate isolation counts

**Code Location**: `metrics/collector.py`

### TokenTracker (`metrics/token_tracker.py`)

**Purpose**: Per-model token usage and cost tracking.

- Tracks input/output tokens per model ID (exact Anthropic model strings)
- Cost computation uses per-model pricing rates; unknown models fall back to Sonnet rates with a warning
- Conservation regression test ensures no tokens are silently dropped

**Code Location**: `metrics/token_tracker.py`

---

## Configuration System

### Centralized API Configuration (`config/api_config.py`)

All external API credentials managed through Pydantic models:

```python
from config import get_api_config

config = get_api_config()
llm_config = config.llm  # LLMConfig
```

### Runtime Behavior Settings (`config/settings.py`)

Separate from API credentials — controls *how* the system behaves:

```python
from config.settings import get_settings

settings = get_settings()
print(settings.inventory_mode)                      # "mock" | "capture" | "replay"
print(settings.enable_llm_conflict_candidates)      # False (default)
print(settings.llm_detector_repetitions)            # 3
print(settings.llm_detector_temperature)            # 0.0
```

### LLM Configuration

Per-agent model selection, so each agent can run on the right tier:
- `intent_parser_model`: `claude-sonnet-4-6`
- `experience_model`: `claude-sonnet-4-6`
- `collaboration_hub_model`: `claude-sonnet-4-6`
- `option_generator_model`: `claude-sonnet-4-6`
- `itinerary_builder_model`: `claude-sonnet-4-6`
- `flight_model` / `hotel_model` / `visa_safety_model`: `claude-haiku-4-5-20251001`

### Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional (auto-fallback to mock)
SERPAPI_API_KEY=...
NUITEE_API_KEY=...
OPENWEATHER_API_KEY=...

# Optional (benchmark inventory)
VOYAGER_INVENTORY_MODE=mock

# Optional (observability)
LANGSMITH_API_KEY=...
LANGCHAIN_TRACING_V2=true
```

---

## API Layer

### FastAPI Application (`api/main.py`)

**Collaborative Endpoints**:

#### POST `/api/travel/collaborative`

Generate 3 trip options.

**Request**:
```json
{
  "query": "Greece under $2000, beaches, summer 2026",
  "user_id": "user123",
  "session_id": "optional-uuid"
}
```

**Response**:
```json
{
  "session_id": "abc-123",
  "status": "complete",
  "trip_options": [...],
  "collaboration_messages": [...],
  "conflicts": [...],
  "synergies": [...]
}
```

#### POST `/api/travel/select-option`

User selects one of the 3 options.

#### POST `/api/travel/refine`

Refine selected option based on follow-up query.

#### WebSocket `/ws/travel/collaborative/{session_id}`

Real-time streaming of agent progress.

**Event Types**: `agent_update`, `collaboration`, `options_ready`

**Code Location**: `api/main.py`

### Session Management

In-memory dict for development. **Production**: Use Redis or DynamoDB.

---

## Frontend Architecture

### Component Hierarchy

```
App
 └─ CollaborativeChatInterface (main orchestrator)
     ├─ View: Input
     │   └─ Search bar + example queries
     ├─ View: Planning
     │   ├─ AgentStatusPanel (progress tracking)
     │   └─ CollaborationFeed (agent messages)
     ├─ View: Options
     │   └─ OptionSelector
     │       ├─ TripOptionCard (budget)
     │       ├─ TripOptionCard (balanced)
     │       ├─ TripOptionCard (premium)
     │       └─ Comparison table
     └─ View: Details
         └─ DetailedItineraryView
             ├─ Booking buttons (flight/hotel/experiences)
             ├─ Budget breakdown
             ├─ Day-by-day itinerary (expandable)
             └─ Refinement input
```

### Key Components

- **CollaborativeChatInterface**: View state management, WebSocket connection, real-time event handling
- **TripOptionCard**: Single option display with highlights/trade-offs
- **OptionSelector**: 3-option grid + comparison table
- **DetailedItineraryView**: Full itinerary + booking links + refinement input
- **CollaborationFeed**: Real-time agent messages, color-coded by type

---

## Collaboration Examples

> Across all examples, the hub routes a constraint to a **single** agent per
> conflict type. Bidirectional messaging (nudging both sides of a conflict) causes
> oscillation — each round pushes the other back — so each conflict type names one
> agent responsible for resolving it.

### Example 1: Hotel-Experience Location Conflict

**Round 1**:
```
Hotel Agent → "Downtown Athens Hotel" ($90/night, Athens city center)
Experience Agent → "Santorini caldera tour" (3hr ferry from Athens each way)
```

**Collaboration Hub Analysis**:
```
Conflict detected: Hotel in Athens, but top experience is Santorini (6hr round trip)

Message (hotel only — experiences are the "truth"; hotel adapts):
  To Hotel Agent:
   "Top experiences are located far from selected hotels."
   Data: {
     activity_locations: ["Oia, Santorini", "Fira center"],
     activity_centroid: {"lat": 36.42, "lon": 25.43}
   }
```

**Round 2**:
```
Hotel Agent → re-runs, distance-matches against centroid:
  Santorini beachfront resort ($85/night, 3km from centroid)

(Experience, flight, weather, and visa agents are not targeted — their Round-1 outputs stand.)
```

### Example 2: Flight Timing Inefficiency

**Round 1**:
```
Flight Agent → JFK→ATH departing 11:00pm, arriving 6:00pm+1
Experience Agent → Suggests "Morning Acropolis tour" (Day 1)
```

**Collaboration Hub Analysis**:
```
Conflict detected: Late arrival wastes first day

Message to Flight Agent (flight only):
   Data: { preferred_arrival: "before 14:00" }
```

**Round 2**:
```
Flight Agent → re-runs, filters for arrival window:
  • JFK→ATH departing 5:00pm, arriving 11:00am+1 (+$80)

(Other agents are not targeted — their Round-1 outputs stand.)
```

### Example 3: Weather-Activity Mismatch

**Round 1**:
```
Weather Agent → "July 15-20: Heatwave, 38°C average"
Experience Agent → Suggests beach + hiking activities
```

**Collaboration Hub Analysis**:
```
Conflict detected: Extreme heat + outdoor activities

Message to Experience Agent (experience only):
   Data: { suggested_activity_times: ["morning", "evening"] }
```

**Round 2**:
```
Experience Agent → re-runs with weather guidance:
  • Sunset cruises, morning beach visits, indoor museums, evening taverna tours

(Weather is read-only and not asked to re-run; other agents are not targeted.)
```

---

## Observability & Monitoring

### LangSmith Integration

Every node execution is traced via `@traceable` decorators. Enable in `.env`:
```bash
LANGCHAIN_TRACING_V2=true
LANGSMITH_API_KEY=...
```

**Traced Functions**: `BaseAgent.run()`, `run_collaborative_travel_query()`, `CollaborationHubAgent._execute()`, `OptionGeneratorAgent._execute()`

**Viewing Traces**: https://smith.langchain.com

In a full-mode trace, the `research_round_2` / `collaboration_hub_2` nodes are present
and the conflicts array is populated; in a baseline trace the run stops after the first
hub. This contrast is the clearest visual evidence of selective re-execution.

---

## Data Flow Example

Complete trace of a single user query:

```
1. User Input
   Query: "Greece under $2000, beaches, summer 2026"

2. Intent Parser → Anthropic API
   { destination: "Greece", budget_usd: 2000, ... }

3. Round 1: Parallel Research
   • Flight Agent → SerpApi (or mock) → [3 flight options]
   • Hotel Agent → Nuitee (or mock) → [5 hotel options]
   • Experience Agent → Claude + geocoding → [8 experiences with coords]
   • Weather Agent → OpenWeather One Call (or mock) → { avg_temp_c: 33 }
   • Visa/Safety Agent → DuckDuckGo → { visa_required: false }

4. Collaboration Hub 1
   Rule-based conflict detection → typed conflict objects with fingerprints
   Lifecycle audit: [location_mismatch: new, timing_inefficiency: new]
   Message (hotel only): { activity_centroid: {lat: 36.42, lon: 25.43}, ... }

5. Round 2: Selective Refinement
   • Hotel Agent → re-runs, distance-matches against centroid
   • Flight Agent → re-runs, filters for arrival window
   • (Experience, weather, visa agents skipped)

6. Collaboration Hub 2
   Re-detect: location_mismatch resolved, timing_inefficiency resolved
   Lifecycle audit: [location_mismatch: resolved_in_round_2, ...]

7. Final Conflict Audit
   detect_conflicts_only() → no conflicts
   Convergence summary: converged_round=2, introduced=0, reopened=0

8. Budget Guardrail → costs within budget ✓

9. Option Generator → 3 variants (budget/balanced/premium)

10. WebSocket → options_ready event → UI renders 3 cards
```

---

## Deployment Architecture (AWS)

### Infrastructure Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         PUBLIC INTERNET                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓ HTTPS/WSS
┌─────────────────────────────────────────────────────────────────┐
│  Application Load Balancer (ALB)                                │
│  • HTTPS termination, WebSocket upgrade, health checks          │
│  • Idle timeout: 300s (for long-running agents)                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  ECS Fargate (Private Subnet)                                   │
│  • Service: voyager-api                                         │
│  • Task: FastAPI container                                      │
│  • Instances: 2+ (auto-scaling)                                 │
└─────────────────────────────────────────────────────────────────┘
          ↓                 ↓                    ↓
┌──────────────┐  ┌──────────────────┐  ┌─────────────────┐
│  DynamoDB    │  │  SQS Queues      │  │  Qdrant         │
│  • Sessions  │  │  • Agent events  │  │  • Destinations │
│  • Profiles  │  │  • Async tasks   │  │  • Vector DB    │
└──────────────┘  └──────────────────┘  └─────────────────┘

External Services (API calls):
• Anthropic Claude API
• SerpApi Google Flights
• Nuitee / LiteAPI
• OpenWeather API
• LangSmith (observability)
```

### Why Fargate over Lambda?

Collaborative queries take 60-120 seconds. API Gateway WebSocket timeout is 29 seconds — Lambda would kill the connection mid-execution. Fargate's ALB supports long-lived WebSocket connections (300s+ idle timeout).

### Infrastructure as Code

**Terraform** (`infra/terraform/`): VPC, ECS cluster, ALB, DynamoDB, SQS, security groups, IAM roles.

### CI/CD Pipeline

**GitHub Actions** (`.github/workflows/ci.yml`): test → build → deploy (rolling).

### Environment Variables (Production)

Stored in **AWS SSM Parameter Store**, injected into ECS task definition at runtime.

### Monitoring

**CloudWatch**: Container logs, metrics, alarms.
**LangSmith**: Trace-level observability, token usage, cost analysis.

---

## Key Design Decisions

### 1. Why Multi-Round Collaboration?

Single-pass agents miss optimization opportunities. Iterative refinement allows cross-agent constraint satisfaction. Trade-off: higher latency (60-240s), but significantly better recommendations.

### 2. Why 3 Options Instead of 1?

Users have different priorities. Variants (budget/balanced/premium) provide user choice + explicit trade-offs.

### 3. Why LangGraph?

Conditional routing, automatic state management, one-line agent addition, built-in streaming, LangSmith integration.

### 4. Why Mock Fallbacks for All APIs?

System works with only `ANTHROPIC_API_KEY`. Local development, CI/CD, and demos work without paid APIs.

### 5. Why asyncio.gather for Parallel Execution?

Sequential (5 agents × 5s each) = 25 seconds. Parallel = ~5-7 seconds. Budget guardrail can't run until all agents finish, so parallelism is mandatory.

### 6. Why deterministic conflict detection?

Typed conflicts are the contract that targeted routing and selective re-execution depend on. Deterministic detection makes benchmarks reproducible. A controlled evaluation (`scripts/eval_hybrid_detection.py`) measured an LLM detector against the rules: at temperature 0 it was fully self-consistent and caught conflict types the rules don't enumerate (visa lead-time, dietary preference, budget component sums), but it also asserted an unverifiable budget violation on a clean control case. The conclusion shapes the design — let the LLM *propose* candidate conflicts and let deterministic rules *validate* before anything triggers a re-run, since in this pattern a detection event spends money.

### 7. Why content-addressed conflict fingerprints?

Without them, the lifecycle tracker can't distinguish "same conflict persisting" from "new conflict introduced" — churn becomes invisible. Fingerprints are SHA-256 digests over (type, sorted agents, normalized evidence data). Prose is excluded. Different queries produce different fingerprints (different evidence → different identity). This makes introduced/resolved/reopened classifications honest rather than vacuous.

### 8. Why typed constraints over prose feedback?

Round-1 feedback messages initially carried human-readable location strings ("Oia, Santorini"). On real inventory, the hotel agent's substring matching against real addresses ("600 Center Place Drive, Greece, US") could never succeed — 100% of location constraints were unsatisfiable *by construction*. The fix: the experience agent geocodes each activity location to lat/lon coordinates, the hub computes an activity centroid, and the hotel agent distance-matches against real hotel coordinates. The typed payload's *producer* must emit the type the *consumer* needs.

---

## Testing

### Unit Tests (`tests/unit/`)

Test individual agents with mocked LLM responses. No API keys needed.

**Run**: `pytest tests/unit -v`  (~200 tests, ~10s)

### Integration Tests (`tests/integration/`)

Test full graph with real Anthropic API.

**Run**: `pytest tests/integration -v` (requires `ANTHROPIC_API_KEY`)

### Code Location

- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- Test configuration: `pyproject.toml`

---

## Benchmark Methodology

### What the benchmark measures

The benchmark runs queries through the complete collaborative graph in two modes — *full* (with hub routing and refinement rounds) and *baseline* (Round 1 → audit → options, hub routing disabled). Both modes run identical conflict detectors at audit time, and both see identical inventory per query (mock fixtures or captured live inventory), so final-conflict counts are directly comparable.

Reported metrics measure the **coordination layer**, not absolute travel quality:

| Metric | What it measures |
|---|---|
| Conflict resolution rate | % of Round-1 conflicts eliminated by selective refinement |
| Convergence | Which round the system converges (R1/R2/R3) |
| Churn | Post-refinement introductions and reopens (via content-addressed fingerprints) |
| Cost overhead | Extra API spend added by hub + refinement, vs. baseline |
| Agent-call savings | Reduction in research-agent invocations vs. naive full re-run |
| Unsatisfiable constraint rate | % of full-mode queries where an agent reports `no_qualifying_option` — the constraint cannot be satisfied with available inventory |

### Inventory Modes

The benchmark supports three inventory modes, controlled by `VOYAGER_INVENTORY_MODE`:

- **mock**: Fully offline, deterministic. No travel API keys needed. Mock hotel/flight data is constructed so that every query starts in conflict (location_mismatch + timing_inefficiency), making resolution rate precisely measurable.
- **capture**: Hits real APIs (SerpApi, Nuitee, OpenWeather), saves hash-verified fixtures. Real inventory may not contain options that satisfy constraints — this is where the unsatisfiable constraint rate becomes meaningful.
- **replay**: Re-runs against captured fixtures with zero network calls. Must run the same day as capture (effective dates are date-keyed).

### Conflict Identity

Every conflict gets a content-addressed fingerprint (SHA-256 over type, agents, evidence data). This enables the lifecycle tracker to classify each conflict as `new`, `persisting`, `resolved`, or `reopened` — making churn visible rather than masked by constant fingerprints.

### Models

Agents run on a tiered selection: `claude-sonnet-4-6` for reasoning/synthesis-heavy nodes (intent parser, experience, collaboration hub, option generator) and `claude-haiku-4-5-20251001` for retrieval/summarization-shaped agents (flight, hotel, visa/safety).

### Cost estimation

Costs are estimated from per-model token usage at published Anthropic rates. Session estimates are computed by `metrics/token_tracker.py`, which sums per-model costs so Haiku tokens are never priced at Sonnet rates.

### Benchmark Commands

```bash
# Mock — 25 queries × 2 modes (full + baseline), ~3 hours, ~$9 in tokens
python scripts/benchmark_queries.py --mode compare --inventory mock

# Capture — 12 queries × 2 modes, ~45 min, ~$3 in tokens + Nuitee sandbox calls
python scripts/benchmark_queries.py --mode compare --inventory capture --query-count 12

# Replay — same day as capture, zero network calls
python scripts/benchmark_queries.py --mode compare --inventory replay --query-count 12

# Summary of existing sessions
python scripts/benchmark_queries.py --summary

# Hybrid LLM detector evaluation
python scripts/eval_hybrid_detection.py
```

### Latest Results (v1.1)

**Mock (25 queries × 2 modes)**:
- Resolution rate: 100% (2.0 → 0.0 final conflicts per query)
- Converged after Round 2: 25/25
- Post-refinement introductions: 0; Reopened: 0
- Agent-call savings: 30%; Cost: ~$0.175/query

**Live capture (12 queries × 2 modes)**:
- Resolution rate: 10% (1.2 → 1.1 final conflicts per query)
- Converged: R1 2/12, R2 1/12, R3 4/12
- Post-refinement introductions: 5 (0.42/query); Reopened: 0
- Unsatisfiable constraint rate: 67%
- Agent-call savings: 41%; Cost: ~$0.105/query

The mock/live contrast is the key finding: on synthetic inventory, the pattern resolves everything; on real inventory, the dominant conflict class (location_mismatch) is frequently unsatisfiable because real hotel inventory within 25km of the activity centroid often doesn't exist. The pattern detects, routes, and attempts resolution — but it cannot conjure inventory that doesn't exist. The introductions on live inventory are caused by LLM nondeterminism in the experience agent's Round-3 re-execution (different activity sets → different location constraints), a behavior invisible to the old constant-fingerprint instrumentation.

---

## Future Enhancements

### Near-Term

- **Persistent sessions**: Redis/DynamoDB instead of in-memory
- **Refinement agent**: Dedicated LLM-powered query parser for follow-ups
- **Real-time re-pricing**: Poll APIs during user decision, update costs
- **User authentication**: Accounts with saved preferences

### Medium-Term

- **Multi-destination trips**: "Greece then Italy" → 2 sub-graphs
- **Group trip planning**: Multiple users vote on options
- **Booking API integration**: Complete reservations in-app
- **Mobile app**: iOS/Android with native UX

### Long-Term

- **Adaptive constraint relaxation**: When a constraint is unsatisfiable (agent reports `no_qualifying_option`), relax the constraint (e.g., widen the 25km radius) or escalate to the user rather than re-attempting the same impossible constraint
- **Validators for LLM-proposed conflict types**: Write deterministic validators for the conflict classes the LLM catches but rules don't enumerate (visa lead-time, dietary preference, budget component sums), then re-measure the validated_extra rate
- **Evaluation suite**: Test collaboration quality, option diversity
- **Multi-language support**: i18n for global users

---

## Summary

Voyager is a collaborative multi-agent travel planning system that:

**Generates 3 personalized trip options** (budget, balanced, premium)
**Enables agent collaboration** across multiple rounds with typed constraint feedback
**Tracks conflict identity** via content-addressed fingerprints for honest churn measurement
**Benchmarks against real inventory** with capture/replay for reproducible evaluation
**Provides booking URLs** for flights, hotels, and experiences
**Streams real-time progress** to the UI via WebSocket
**Scales to production** on AWS Fargate with full observability

**Tech Stack**: LangGraph + Claude + React + FastAPI + AWS
**Cost**: ~$0.10-0.18 per query (Anthropic API, depends on inventory mode)
**Latency**: ~40-240 seconds (varies by mode and conflict count)
**Reliability**: Mock fallbacks ensure uptime without external APIs

---

For detailed API documentation, see **[API_REQUIREMENTS.md](API_REQUIREMENTS.md)**.
For quick overview and setup, see **[README.md](README.md)**.