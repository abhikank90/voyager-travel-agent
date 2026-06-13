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
│  8. Budget Guardian → Validate costs                            │
│  9. Option Generator→ Create 3 trip variants                    │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                       AGENT LAYER                               │
│                                                                 │
│  Research Agents (Parallel):                                   │
│  • FlightAgent       → Amadeus API / mock                       │
│  • HotelAgent        → Booking.com API / mock                   │
│  • ExperienceAgent   → Claude + destinations.json RAG           │
│  • WeatherAgent      → OpenWeather API / mock                   │
│  • VisaSafetyAgent   → DuckDuckGo search + Claude               │
│                                                                 │
│  Coordination Agents:                                           │
│  • CollaborationHubAgent → Conflict detection, message routing  │
│  • OptionGeneratorAgent  → Generate 3 trip variants             │
│  • BudgetGuardrailAgent  → Cost validation                      │
│                                                                 │
│  Support Agents:                                                │
│  • PersonalisationAgent  → User profile loading                 │
│  • IntentParserAgent     → Query → TravelIntent                 │
│  • ItineraryBuilderAgent → Legacy synthesis                     │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                    EXTERNAL SERVICES                            │
│                                                                 │
│  • Anthropic Claude API   (required)                            │
│  • Amadeus Flight API     (optional - has mock)                 │
│  • Booking.com API        (optional - has mock)                 │
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
  collaboration_hub_1  (analyze, send messages)
      ↓ (conditional)
      ├─ If messages/conflicts → research_round_2
      └─ Else → budget_guardrail
      ↓
  research_round_2  (selective re-run of agents with messages)
      ↓
  collaboration_hub_2  (check if resolved)
      ↓ (conditional)
      ├─ If conflicts & round < 3 → research_round_3
      └─ Else → budget_guardrail
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
    return "budget_guardrail"  # No issues

def route_after_hub_2(state):
    if state.get("conflicts") and state.get("collaboration_round") < 3:
        return "research_round_3"  # Final round
    return "budget_guardrail"  # Done collaborating
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
- `HotelAgent` — prefers candidates whose location matches `activity_locations` hint
- `FlightAgent` — prefers options arriving before `preferred_arrival` hour
- `ExperienceAgent` — prepends weather/timing guidance to the LLM prompt via `location_focus`

Across the 25-query benchmark, the agents re-run in a refinement round were the flight
and hotel agents (the two implicated in every query's conflicts); the experience, weather,
and visa agents stayed dormant unless directly targeted.

### Research Agents (Parallel Execution)

#### 1. FlightAgent (`agents/flight_agent.py`)

**Purpose**: Search for flights matching user intent.

**API**: Amadeus Test API (free)
- OAuth token endpoint
- Flight offers search endpoint

**Fallback**: Mock data (realistic prices/routes)

**Model**: `claude-haiku-4-5` (retrieval-shaped task)

**Output**: List of 3-5 flight options with:
- Airline, price, departure/arrival times
- Number of stops, duration
- Departure/arrival airports

**Code Location**: `agents/flight_agent.py:20-80`

#### 2. HotelAgent (`agents/hotel_agent.py`)

**Purpose**: Find hotels matching destination and budget.

**API**: Booking.com via RapidAPI

**Fallback**: Mock data (realistic hotels)

**Model**: `claude-haiku-4-5` (retrieval-shaped task)

**Output**: List of 5 hotel options with:
- Name, location, price per night
- Rating, amenities
- Description

**Code Location**: `agents/hotel_agent.py:18-90`

#### 3. ExperienceAgent (`agents/experience_agent.py`)

**Purpose**: Recommend activities based on user interests.

**Data Source**:
- Claude Sonnet with RAG over `data/knowledge_base/destinations.json`
- Contains curated experiences for Greece, Japan, France

**Model**: `claude-sonnet-4-6` (reasoning + synthesis)

**Output**: List of 5-10 experiences with:
- Name, description, category
- Best time of day
- Estimated cost

**Code Location**: `agents/experience_agent.py:15-70`

#### 4. WeatherAgent (`agents/weather_agent.py`)

**Purpose**: Provide weather information for travel dates.

**API**: OpenWeather API

**Fallback**: Climate averages by destination/month

**Output**: Weather data with:
- Average temperature (C/F)
- Conditions (sunny, rainy, etc.)
- Precipitation, sunshine hours
- Sea temperature (if coastal)

**Code Location**: `agents/weather_agent.py:20-65`

#### 5. VisaSafetyAgent (`agents/visa_safety_agent.py`)

**Purpose**: Provide visa requirements and safety information.

**Data Source**:
- DuckDuckGo search (free, no API key)
- Claude Haiku for summarization

**Model**: `claude-haiku-4-5` (summarization task)

**Output**: Visa & safety info with:
- Visa required (yes/no)
- Safety level (1-5)
- Entry requirements
- Travel advisories

**Code Location**: `agents/visa_safety_agent.py:18-75`

### Coordination Agents

#### 6. CollaborationHubAgent (`agents/collaboration_hub.py`)

**Purpose**: Coordinate multi-agent collaboration by analyzing findings and generating targeted messages.

**Responsibilities**:
1. Analyze all research agent outputs
2. Identify conflicts (hotel location, flight timing, weather mismatches) — deterministic, rule-based
3. Detect synergies (beachfront hotel + beach activities)
4. Generate targeted messages to agents — templated, with structured data payloads
5. Track conflict resolution progress

Detection, routing, and the feedback messages themselves are all deterministic. The hub
also makes one Claude call per round to produce a narrative analysis surfaced in the UI,
but that narrative is deliberately ignored for routing — control flow depends only on the
typed conflict objects, which keeps benchmarks reproducible and re-runs grounded.

**Conflict Detection**:
```python
# Example: Hotel-Experience location mismatch
hotel_location = "Athens"
top_experiences = ["Santorini caldera", "Navagio Beach"]
# → Conflict: 3-6 hour travel time

# Message generated:
{
    "from_agent": "collaboration_hub",
    "to_agent": "hotel",
    "message_type": "constraint",
    "content": "Top experiences are in Santorini (3hr away). Find Santorini hotels?",
    "data": {"suggested_areas": ["Santorini", "Fira"]},
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

**Code Location**: `agents/collaboration_hub.py:30-380`

#### 7. OptionGeneratorAgent (`agents/option_generator.py`)

**Purpose**: Generate 3 distinct trip variants from refined research.

**Strategies**:

**Budget Option (75% of budget)**:
- Cheapest flight (`min(flights, key=lambda f: f["price"])`)
- Budget hotel (`min(hotels, key=lambda h: h["price_per_night"])`)
- Free + low-cost experiences (`[e for e in exps if e["price"] < 50]`)

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
# → "https://www.booking.com/searchresults.html?ss=Athens&..."

experience_url = config.experience.booking_url_template.format(
    destination="Athens"
)
# → "https://www.getyourguide.com/s/?q=Athens"
```

**Model**: `claude-sonnet-4-6` (synthesis)

**Output**: 3 `TripOption` objects with:
- Full itinerary (day-by-day)
- All booking URLs
- Highlights ("Direct flight", "5★ hotel")
- Trade-offs ("$300 over budget", "1 stop flight")
- Budget breakdown

**Code Location**: `agents/option_generator.py:28-450`

#### 8. BudgetGuardrailAgent (`agents/budget_guardrail.py`)

**Purpose**: Aggregate costs and validate against budget.

**Allocation Ratios**:
- Flights: 45%
- Hotel: 45%
- Activities: 10%
- Food: 15%
- Misc: 5%

(Total > 100% is intentional — triggers if sum exceeds budget)

**Output**: Budget breakdown with validation status.

**Code Location**: `agents/budget_guardrail.py:15-90`

### Support Agents

#### 9. PersonalisationAgent (`agents/personalisation.py`)

**Purpose**: Load user profile from DynamoDB or local storage.

**Data**: Previous trips, preferences, budget history

**Code Location**: `agents/personalisation.py`

#### 10. IntentParserAgent (`agents/intent_parser.py`)

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

**Code Location**: `agents/intent_parser.py:15-50`

#### 11. ItineraryBuilderAgent (`agents/itinerary_builder.py`)

**Purpose**: Legacy agent for building single itinerary.

**Status**: Still used as fallback, but `OptionGeneratorAgent` is primary.

**Code Location**: `agents/itinerary_builder.py`

---

## Configuration System

### Centralized API Configuration (`config/api_config.py`)

All external API settings are managed through Pydantic models:

```python
from config import get_api_config

config = get_api_config()

# Access API settings
flight_config = config.flight  # FlightAPIConfig
hotel_config = config.hotel     # HotelAPIConfig
llm_config = config.llm         # LLMConfig

# Check if using mock
if config.flight.use_mock:
    # Fallback to mock data
    ...

# Get booking URL
url = config.flight.booking_url_template.format(
    origin="JFK", destination="ATH", date="2026-07-01"
)
```

### Configuration Classes

**FlightAPIConfig**:
- `provider`: API provider name
- `api_key`, `api_secret`: Credentials
- `base_url`: API base URL
- `booking_url_template`: Deep link template
- `use_mock`: Auto-set if no API key

**HotelAPIConfig**: Similar structure for hotels

**WeatherAPIConfig**: Similar structure for weather

**ExperienceAPIConfig**: Activity booking configuration

**LLMConfig**: Per-agent model selection, so each agent can run on the right
tier. Model strings are exact Anthropic API IDs.
- `api_key`: Anthropic API key (required)
- `intent_parser_model`: `claude-sonnet-4-6`
- `experience_model`: `claude-sonnet-4-6`
- `collaboration_hub_model`: `claude-sonnet-4-6`
- `option_generator_model`: `claude-sonnet-4-6`
- `itinerary_builder_model`: `claude-sonnet-4-6`
- `flight_model` / `hotel_model` / `visa_safety_model`: `claude-haiku-4-5-20251001`
  (cheaper tier for retrieval/summarization-shaped agents)

### Environment Variables

All config loaded from `.env`:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional (auto-fallback to mock)
AMADEUS_API_KEY=...
AMADEUS_API_SECRET=...
BOOKING_API_KEY=...
OPENWEATHER_API_KEY=...

# Optional (observability)
LANGSMITH_API_KEY=...
LANGCHAIN_TRACING_V2=true
```

**Code Location**: `config/api_config.py:1-180`

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
  "trip_options": [
    {
      "option_id": 0,
      "style": "budget",
      "title": "Budget Explorer - Greece",
      "total_cost_usd": 1500,
      "flight": {...},
      "hotel": {...},
      "experiences": [...],
      "day_by_day": [...],
      "flight_booking_url": "https://...",
      "hotel_booking_url": "https://...",
      "highlights": ["Save $500", "Local experiences"],
      "trade_offs": ["1 stop flight", "Basic hotel"]
    },
    // ... balanced and premium options
  ],
  "collaboration_messages": [...],
  "conflicts": [...],
  "synergies": [...]
}
```

#### POST `/api/travel/select-option`

User selects one of the 3 options.

**Request**:
```json
{
  "session_id": "abc-123",
  "option_id": 1,
  "user_id": "user123"
}
```

**Response**: Selected option details

#### POST `/api/travel/refine`

Refine selected option based on follow-up query.

**Request**:
```json
{
  "session_id": "abc-123",
  "selected_option_id": 1,
  "refinement_query": "Use the hotel from the budget option",
  "user_id": "user123"
}
```

**Response**: Refined option

#### WebSocket `/ws/travel/collaborative/{session_id}`

Real-time streaming of agent progress.

**Connection**:
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/travel/collaborative/session-123')
ws.send(JSON.stringify({ query: "Greece under $2000..." }))
```

**Event Types**:

1. **agent_update**: Node completion
```json
{
  "type": "agent_update",
  "agent": "research_round_1",
  "message": "Round 1: Researching in parallel...",
  "data": {...}
}
```

2. **collaboration**: Agent messages
```json
{
  "type": "collaboration",
  "agent": "collaboration_hub_1",
  "message": "Agents are discussing...",
  "collaboration_messages": [
    {
      "from_agent": "collaboration_hub",
      "to_agent": "hotel",
      "content": "Activities far from hotel..."
    }
  ]
}
```

3. **options_ready**: Final event
```json
{
  "type": "options_ready",
  "message": "3 trip options ready!",
  "trip_options": [...],
  "session_id": "abc-123"
}
```

**Code Location**: `api/main.py:113-372`

### Session Management

In-memory dict (`_session_store`) for development.

**Production**: Use Redis or DynamoDB for session persistence.

**Code Location**: `api/main.py:138-202`

---

## Frontend Architecture

### Component Hierarchy

```
App
 └─ CollaborativeChatInterface (main orchestrator)
     ├─ View: Input
     │   └─ Search bar + example queries
     │
     ├─ View: Planning
     │   ├─ AgentStatusPanel (progress tracking)
     │   └─ CollaborationFeed (agent messages)
     │
     ├─ View: Options
     │   └─ OptionSelector
     │       ├─ TripOptionCard (budget)
     │       ├─ TripOptionCard (balanced)
     │       ├─ TripOptionCard (premium)
     │       └─ Comparison table
     │
     └─ View: Details
         └─ DetailedItineraryView
             ├─ Booking buttons (flight/hotel/experiences)
             ├─ Budget breakdown
             ├─ Day-by-day itinerary (expandable)
             └─ Refinement input
```

### Key Components

#### CollaborativeChatInterface (`frontend/src/components/CollaborativeChatInterface.tsx`)

**Responsibilities**:
- Manage view state (input → planning → options → details)
- WebSocket connection to `/ws/travel/collaborative/{session_id}`
- Handle real-time events (agent updates, collaboration, options)
- Route to appropriate view based on state

**State Management**:
```typescript
const [viewMode, setViewMode] = useState<'input' | 'planning' | 'options' | 'details'>('input')
const [tripOptions, setTripOptions] = useState<TripOption[]>([])
const [selectedOption, setSelectedOption] = useState<TripOption | null>(null)
const [collaborationMessages, setCollaborationMessages] = useState<CollaborationMessage[]>([])
```

**Code Location**: `frontend/src/components/CollaborativeChatInterface.tsx`

#### TripOptionCard (`frontend/src/components/TripOptionCard.tsx`)

**Purpose**: Display a single trip option (budget/balanced/premium).

**Features**:
- Color-coded by style (green/blue/purple)
- Shows flight, hotel, experiences summary
- Highlights & trade-offs sections
- Budget breakdown
- "Select" and "View Details" buttons

**Code Location**: `frontend/src/components/TripOptionCard.tsx`

#### OptionSelector (`frontend/src/components/OptionSelector.tsx`)

**Purpose**: Display all 3 options side-by-side with comparison.

**Features**:
- Grid of 3 TripOptionCard components
- Feature comparison table
- Selection state management
- CTA button when option selected

**Code Location**: `frontend/src/components/OptionSelector.tsx`

#### DetailedItineraryView (`frontend/src/components/DetailedItineraryView.tsx`)

**Purpose**: Show full itinerary with booking links.

**Features**:
- Day-by-day schedule (expandable cards)
  - Morning/afternoon/evening activities
  - Meal recommendations
- Booking buttons with external links:
  - ✈️ Book Flight (Google Flights)
  - 🏨 Book Hotel (Booking.com)
  - 🎯 Book Experiences (GetYourGuide)
- Budget breakdown visualization
- Refinement input with example prompts
- Back navigation

**Code Location**: `frontend/src/components/DetailedItineraryView.tsx`

#### CollaborationFeed (`frontend/src/components/CollaborationFeed.tsx`)

**Purpose**: Display real-time agent collaboration messages.

**Features**:
- Color-coded by message type (insight/constraint/question/proposal/conflict)
- Shows agent-to-agent communication
- Displays collaboration round number
- Auto-scrolling message list

**Code Location**: `frontend/src/components/CollaborationFeed.tsx`

### TypeScript Types (`frontend/src/types/index.ts`)

**Core Types**:
- `TripOption`: Complete trip option with itinerary + URLs
- `CollaborationMessage`: Inter-agent communication
- `DayPlan`: Day-by-day schedule structure
- `Conflict`, `Synergy`: Collaboration analysis
- `CollaborativeAgentUpdate`: WebSocket event types
- `CollaborativeTravelState`: Extended state

**Code Location**: `frontend/src/types/index.ts:108-209`

---

## Collaboration Examples

> Across all three examples, the hub routes a constraint to a **single** agent per
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

Message generated (hotel only — experiences are the "truth"; hotel adapts):
1. To Hotel Agent:
   "Top experiences are located far from selected hotels. Consider hotels closer to activity hubs."
   Data: { activity_locations: ["Oia, Santorini", "Fira center"] }
```

> **One resolution direction per conflict type.** Sending a constraint to both hotel *and* experience agents causes oscillation (each round nudges the other back). The hub picks the single agent best positioned to resolve each conflict type and routes only to them.

**Round 2**:
```
Hotel Agent → re-runs, prefers an affordable Santorini candidate:
  Santorini beachfront resort ($85/night)

(Experience, flight, weather, and visa agents are not targeted — their Round-1 outputs stand.)
```

**Final Options**:
```
Budget Option: Athens-focused (saves ferry costs)
  • Athens hotel
  • Local Athens experiences
  • Total: $1,500

Premium Option: Santorini luxury
  • Santorini beachfront resort
  • Caldera tours, wine tasting
  • Total: $2,300
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

Message to Flight Agent (flight only — the implicated agent):
   "Arrival at 6pm means Day 1 is lost. Look for earlier flights?"
   Data: { preferred_arrival: "before 14:00" }
```

**Round 2**:
```
Flight Agent → re-runs, prefers an option satisfying the arrival window:
  • JFK→ATH departing 5:00pm, arriving 11:00am+1 (+$80)
  • Allows full afternoon on Day 1

(Other agents are not targeted — their Round-1 outputs stand.)
```

**Final Options**:
```
Budget: Evening flight ($680) → dinner only Day 1
Balanced: Afternoon arrival ($760) → half-day Day 1
Premium: Morning arrival ($820) → full Day 1 + upgrade to business
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

Message to Experience Agent (experience only — the implicated agent):
   "High temperatures (38°C). Prioritize indoor/evening activities?"
   Data: { suggested_times: ["morning", "evening"], indoor: true }
```

**Round 2**:
```
Experience Agent → re-runs with weather guidance, adds evening/indoor alternatives:
  • Sunset cruises
  • Morning beach visits
  • Indoor museums
  • Evening taverna tours

(Weather is a read-only source and is not asked to re-run; other agents are not targeted.)
```

**Final Options**:
```
Budget: All evening/indoor activities
Balanced: Mixed schedule weighted to mornings and evenings
Premium: AC-upgraded hotels + indoor experiences
```

---

## Observability & Monitoring

### LangSmith Integration

Every node execution is traced via `@traceable` decorators:

```python
@traceable(name="agent_run")
async def run(self, state: dict) -> dict:
    # Automatically captures:
    # - Input state
    # - Output state updates
    # - Duration
    # - Token usage (for LLM calls)
    # - Errors/exceptions
    ...
```

**Traced Functions**:
- `BaseAgent.run()` - All agent executions
- `run_collaborative_travel_query()` - Full graph execution
- `CollaborationHubAgent._execute()` - Collaboration analysis
- `OptionGeneratorAgent._execute()` - Option generation

**Viewing Traces**:
1. Enable in `.env`: `LANGCHAIN_TRACING_V2=true`
2. Set API key: `LANGSMITH_API_KEY=...`
3. Visit: https://smith.langchain.com

**Trace Details**:
- Input/output for every agent
- Collaboration messages generated
- Conflicts/synergies identified
- Token usage per Claude call
- End-to-end latency (per round + total)

In a full-mode trace, the `research_round_2` / `collaboration_hub_2` nodes are present
and the conflicts array is populated; in a baseline trace the run stops after the first
hub. This contrast is the clearest visual evidence of selective re-execution.

**Code Location**: `agents/base_agent.py:25`, `graph/travel_graph.py:321-345`

---

## Data Flow Example

Complete trace of a single user query:

```
1. User Input
   Query: "Greece under $2000, beaches, summer 2026"

2. WebSocket Connection
   ws://localhost:8000/ws/travel/collaborative/session-abc123

3. Intent Parser
   Input: Raw query string
   Output: {
     destination: "Greece",
     budget_usd: 2000,
     interests: ["beaches", "local food"],
     travel_month: "July"
   }

4. Round 1: Parallel Research
   • Flight Agent → [3 flight options]
   • Hotel Agent → [5 hotel options]
   • Experience Agent → [8 experiences]
   • Weather Agent → { avg_temp_c: 33, conditions: "Sunny" }
   • Visa/Safety Agent → { visa_required: false, safety_level: 1 }

5. Collaboration Hub 1
   Analysis: "Hotel on beachfront, top experiences cluster inland → location mismatch"
   Message (hotel only — experiences are the source of truth, hotel adapts): [
     {to: "hotel", content: "Find hotels near the top activities",
      data: {activity_locations: ["Oia, Santorini", ...]}}
   ]
   Conflicts: [{ type: "location_mismatch", severity: "medium" }]

6. Round 2: Selective Refinement
   • Hotel Agent → re-runs, prefers an affordable candidate near the activities
   • (Flight, experience, weather, visa agents skipped — Round-1 outputs stand)

7. Collaboration Hub 2
   Analysis: "location_mismatch no longer fires; conflict resolved"
   Conflicts: []

8. Budget Guardrail
   Flight: $680 (34%)
   Hotel: $680 (34%)
   Experiences: $200 (10%)
   Food: $300 (15%)
   Misc: $100 (5%)
   Total: $1,960 / $2,000 ✓

9. Option Generator
   Creates 3 variants:

   Budget ($1,500):
   • Cheapest flight ($680, 1 stop)
   • Budget Athens hotel ($60/night)
   • Free experiences (Acropolis, beaches)

   Balanced ($2,000):
   • Best value flight ($750, direct)
   • Mid-range Santorini hotel ($85/night)
   • Mix of paid/free experiences

   Premium ($2,300):
   • Direct luxury flight ($850, extra legroom)
   • 5★ Santorini resort ($150/night)
   • Exclusive wine tours, private sunset cruise

10. WebSocket Event
    {
      type: "options_ready",
      trip_options: [budget, balanced, premium],
      session_id: "abc123"
    }

11. User Selects "Balanced"
    POST /api/travel/select-option
    { session_id: "abc123", option_id: 1 }

12. Detailed View Rendered
    • Full day-by-day itinerary
    • Booking URLs:
      - Flight: https://www.google.com/travel/flights?q=JFK+to+ATH+2026-07-01
      - Hotel: https://www.booking.com/searchresults.html?ss=Santorini&...
      - Experiences: https://www.getyourguide.com/s/?q=Santorini

13. (Optional) User Refinement
    "Use the hotel from the budget option"
    POST /api/travel/refine
    → System updates itinerary with Athens hotel
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
│  • HTTPS termination                                            │
│  • WebSocket upgrade                                            │
│  • Health checks                                                │
│  • Idle timeout: 300s (for long-running agents)                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│  ECS Fargate (Private Subnet)                                   │
│  • Service: voyager-api                                         │
│  • Task: FastAPI container                                      │
│  • Instances: 2+ (auto-scaling)                                 │
│  • CPU: 2 vCPU                                                  │
│  • Memory: 4 GB                                                 │
└─────────────────────────────────────────────────────────────────┘
          ↓                 ↓                    ↓
┌──────────────┐  ┌──────────────────┐  ┌─────────────────┐
│  DynamoDB    │  │  SQS Queues      │  │  Qdrant         │
│  • Sessions  │  │  • Agent events  │  │  • Destinations │
│  • Profiles  │  │  • Async tasks   │  │  • Vector DB    │
└──────────────┘  └──────────────────┘  └─────────────────┘

External Services (API calls):
• Anthropic Claude API
• Amadeus Flight API
• Booking.com API
• OpenWeather API
• LangSmith (observability)
```

### Why Fargate over Lambda?

**Challenge**: Collaborative queries take 60-120 seconds (9 nodes, 3 rounds, 5 parallel APIs, multiple Claude calls).

**Lambda Limitations**:
- API Gateway WebSocket timeout: 29 seconds
- Connection would be killed mid-execution

**Fargate Advantages**:
- ALB supports long-lived WebSocket connections (300s+ idle timeout)
- No hard timeout limits
- Better for long-running agentic workflows

### Infrastructure as Code

**Terraform** (`infra/terraform/`):
- VPC with public/private subnets
- ECS cluster + Fargate service
- ALB with target groups
- DynamoDB tables
- SQS queues
- Security groups
- IAM roles

### CI/CD Pipeline

**GitHub Actions** (`.github/workflows/ci.yml`):

```yaml
on: [push]
jobs:
  test:
    - Run pytest
    - Run ruff

  build:
    - Build Docker image
    - Push to ECR

  deploy:
    - Update ECS service
    - Rolling deployment
```

### Environment Variables (Production)

Stored in **AWS SSM Parameter Store**:

```
/voyager/prod/ANTHROPIC_API_KEY
/voyager/prod/AMADEUS_API_KEY
/voyager/prod/LANGSMITH_API_KEY
...
```

Injected into ECS task definition at runtime.

### Monitoring

**CloudWatch**:
- Container logs
- Metrics (CPU, memory, request count)
- Alarms (error rate, latency)

**LangSmith**:
- Trace-level observability
- Token usage tracking
- Cost analysis
- Error debugging

**Code Location**: `infra/terraform/`

---

## Key Design Decisions

### 1. Why Multi-Round Collaboration?

**Problem**: Single-pass agents miss optimization opportunities.

**Solution**: Iterative refinement allows:
- Hotel agent to relocate based on experience locations
- Experience agent to adapt to weather warnings
- Flight agent to adjust timing based on activity schedule

**Trade-off**: Higher latency (60-120s vs 30-45s), but significantly better recommendations.

### 2. Why 3 Options Instead of 1?

**Problem**: Users have different priorities (cost vs comfort vs luxury).

**Solution**: Generate variants:
- Budget: Cost-conscious travelers
- Balanced: Most users (best value)
- Premium: Luxury seekers

**Benefit**: User choice + explicit trade-offs.

### 3. Why LangGraph?

**Advantages**:
- Conditional routing (round 2 vs skip) is native
- State management is automatic
- Adding agents is one `add_node` call
- Built-in streaming support
- LangSmith integration

**Alternative Considered**: Custom orchestration with asyncio
- More control, but much more code
- No built-in observability
- Manual state management

**Decision**: LangGraph's benefits outweigh learning curve.

### 4. Why Mock Fallbacks for All APIs?

**Goal**: System should work with only `ANTHROPIC_API_KEY`.

**Benefits**:
- Local development without paid APIs
- CI/CD doesn't need API keys
- Demos work offline
- Realistic mock data for testing

**Implementation**: Each agent checks for API key, falls back to hardcoded realistic data.

### 5. Why asyncio.gather for Parallel Execution?

**Sequential (5 agents × 5s each)**: 25 seconds
**Parallel (max of 5 agents)**: ~5-7 seconds

**Critical**: Budget guardrail can't run until all agents finish, so parallelism is mandatory for acceptable UX.

### 6. Why deterministic conflict detection?

Conflict detection stays rule-based — each detector is a cheap predicate over typed agent
outputs — because typed conflicts are the contract that targeted routing and selective
re-execution depend on, and because deterministic detection makes benchmarks reproducible.
A controlled evaluation (`scripts/eval_hybrid_detection.py`) measured an LLM detector
against the rules: at temperature 0 it was fully self-consistent and caught conflict types
the rules don't enumerate, but it also asserted an unverifiable budget violation on a clean
control case. The conclusion shapes the roadmap — let the LLM *propose* candidate conflicts
and let deterministic rules *validate* before anything triggers a re-run, since in this
pattern a detection event spends money.

---

## Testing

### Unit Tests (`tests/unit/`)

Test individual agents with mocked LLM responses:

```python
@pytest.fixture
def mock_anthropic():
    with patch('anthropic.Anthropic') as mock:
        yield mock

def test_intent_parser(mock_anthropic):
    mock_anthropic.return_value.messages.create.return_value = ...
    agent = IntentParserAgent()
    result = await agent.run({"user_query": "Greece under $2000"})
    assert result["intent"]["destination"] == "Greece"
```

**Run**: `pytest tests/unit -v`  (116 tests, ~5s, no API keys needed)

### Integration Tests (`tests/integration/`)

Test full graph with real Anthropic API:

```python
@pytest.mark.integration
async def test_full_collaborative_flow():
    result = await run_collaborative_travel_query(
        "Greece under $2000, beaches, summer 2026"
    )
    assert len(result["trip_options"]) == 3
    assert result["trip_options"][0]["style"] == "budget"
```

**Run**: `pytest tests/integration -v` (requires `ANTHROPIC_API_KEY`)

### Code Location

- Unit tests: `tests/unit/`
- Integration tests: `tests/integration/`
- Test configuration: `pyproject.toml:44-46`

---

## Benchmark Methodology

### What the benchmark measures

The benchmark runs 25 diverse trip queries (beach, city, adventure, budget, family) through the
complete collaborative graph in two modes — *full* (with hub routing and refinement rounds) and
*baseline* (Round 1 → audit → options, hub routing disabled). Both modes run identical conflict
detectors at audit time, and both see identical simulated inventory per query, so final-conflict
counts are directly comparable and isolated from inventory drift.

Reported metrics measure the **coordination layer**, not absolute travel quality:

| Metric | What it measures |
|---|---|
| Conflict resolution rate | % of Round-1 conflicts eliminated by selective refinement |
| Cost overhead | Extra API spend added by hub + refinement, vs. baseline |
| Agent-call savings | Reduction in research-agent invocations vs. naive full re-run |

Canonical results (25 queries × 2 modes, June 2026, tag `v1.0-infoq`): resolution rate 97%
(2.04 → 0.08 final conflicts per query, paired); cost overhead +1.8% (+$0.0032/query mean
paired delta, median +$0.0026, σ $0.0086); end-to-end latency +2.7% (+6.0s mean paired,
median +4.3s, σ 11.9s); Round 3 needed on 1/25 queries; 30% agent-call savings vs. full
re-run. Cost and latency are reported as **paired per-query deltas** because per-query output
variance dominates the overhead — the cost overhead's standard deviation is roughly three
times its mean, so it is statistically indistinguishable from generation-length noise at the
per-query level and visible only in aggregate.

### Models

Agents run on a tiered selection (per `config/api_config.py`): `claude-sonnet-4-6` for the
reasoning- and synthesis-heavy nodes (intent parser, experience, collaboration hub,
option generator, itinerary builder) and `claude-haiku-4-5-20251001` for the
retrieval/summarization-shaped agents (flight, hotel, visa/safety).

### Controlled workload: simulated inventory

The benchmark runs against **simulated flight and hotel inventory** — the `mock: True` catalogs
returned by `_mock_flight_data()` in [agents/flight_agent.py](agents/flight_agent.py) and
`_mock_hotel_data()` in [agents/hotel_agent.py](agents/hotel_agent.py). The fixtures are
constructed so that locally-optimal agent choices (cheapest flight, best-value hotel) reliably
produce cross-agent conflicts after Round 1:

- The cheapest flight arrives at 22:30, triggering `timing_inefficiency`.
- The best-value hotel is on the beachfront while top experiences cluster inland, triggering `location_mismatch`.
- July weather flags heat advisories for outdoor activities, triggering `weather_activity_mismatch`.

This design makes conflict scenarios **reproducible and measurable**: every query in the benchmark
starts in conflict, so resolution rate and coordination cost can be computed precisely. Using the
same inventory for both modes is deliberate — it lets baseline and full runs see an identical world
per query and isolates the coordination pattern. Agent *selections* remain stochastic
(temperature 0.3), so Round-1 conflict *counts* vary slightly across runs even on fixed inventory.

**What is and is not real:**

- All LLM calls (intent parsing, experience generation, hub narrative, option synthesis) are real Anthropic API calls.
- Conflict detection, feedback routing, and selective re-execution logic are identical in benchmark and production modes.
- Flight and hotel data are simulated. Weather, visa/safety, and experience data use the same mock/fallback paths as development without API keys.
- Reported conflict frequency (2.0 per query, 100% of queries) is a property of this controlled workload, not an empirical claim about production travel systems. Real inventory does not guarantee satisfiable conflict resolution; the pattern routes feedback, it cannot conjure inventory that does not exist.

### Cost estimation

Costs are estimated from per-model token usage at published Anthropic rates (June 2026):
`claude-sonnet-4-6` at $3/$15 per MTok (input/output), `claude-haiku-4-5-20251001` at $1/$5.
Session estimates are computed by `metrics.token_tracker.compute_session_cost()`, which sums
per-model costs so Haiku tokens are never priced at Sonnet rates and unattributed tokens are
never silently dropped (a conservation regression test guards this). Estimated costs were
cross-checked against billed API usage for the benchmark window and agreed within 1%.

### Planned future work

Record/replay of real Amadeus and OpenWeather inventory to measure resolution rate and cost
overhead against non-guaranteed satisfiability — the regime where the coordination pattern's
practical limits become visible — captured once into fixtures and replayed deterministically to
preserve reproducibility.

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

- **Voting mechanism**: Agents vote when conflicts can't be resolved
- **Evaluation suite**: Test collaboration quality, option diversity
- **Multi-language support**: i18n for global users
- **Carbon footprint tracking**: Show environmental impact of options

---

## Summary

Voyager v1 is a production-ready collaborative multi-agent travel planning system that:

**Generates 3 personalized trip options** (budget, balanced, premium)
**Enables agent collaboration** across multiple rounds with visible communication
**Provides booking URLs** for flights, hotels, and experiences
**Supports follow-up refinements** ("use hotel from option 3")
**Streams real-time progress** to the UI via WebSocket
**Scales to production** on AWS Fargate with full observability

**Tech Stack**: LangGraph + Claude + React + FastAPI + AWS
**Cost**: ~$0.175 per query (Anthropic API, full mode)
**Latency**: ~220 seconds (3-round collaboration)
**Reliability**: Mock fallbacks ensure uptime without external APIs

---

For detailed API documentation, see **[API_REQUIREMENTS.md](API_REQUIREMENTS.md)**.
For developer guide, see **[CLAUDE.md](CLAUDE.md)**.
For quick overview, see **[README.md](README.md)**.