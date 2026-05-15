# Voyager Travel Agent

## Overview

Voyager is a collaborative multi-agent AI travel planning system that generates three personalized trip options (budget, balanced, premium) through iterative agent collaboration.

**Key Innovation**: Unlike traditional single-pass systems, Voyager's agents communicate across multiple rounds, identify conflicts (e.g., hotel location vs activities), propose solutions, and refine recommendations collaboratively — mimicking how a human travel planning team would work together.

**Tech Stack**:
- **Backend**: Python 3.11+, FastAPI, LangGraph, LangChain
- **AI**: Anthropic Claude (Sonnet & Haiku)
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS
- **Infrastructure**: AWS (ECS Fargate, DynamoDB, SQS, ALB)
- **Observability**: LangSmith

---

## Demo

![Voyager Travel Agent Demo](docs/demo/voyager-demo.gif)

*Watch Voyager generate personalized trip options in real-time as agents collaborate to find flights, hotels, and experiences.*

---

## Documentation

📚 **Complete documentation for this project:**

- **[GETTING_STARTED.md](GETTING_STARTED.md)** - Installation, setup, and quick start guide
- **[API_REQUIREMENTS.md](API_REQUIREMENTS.md)** - External API requirements, keys, and mock fallbacks
- **[TESTING.md](TESTING.md)** - Comprehensive testing guide with coverage targets
- **[CLAUDE.md](CLAUDE.md)** - Development guidance for Claude Code and contributors

---

## System Architecture

<img src="docs/diagrams/Voyager-travel-agent.drawio.png" alt="Voyager Travel Agent - System Architecture" width="75%">

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
    name: str
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
```

### Research Agents (Parallel Execution)

#### 1. FlightAgent (`agents/flight_agent.py`)

**Purpose**: Search for flights matching user intent.

**API**: Amadeus Test API (free)
- OAuth token endpoint
- Flight offers search endpoint

**Fallback**: Mock data (realistic prices/routes)

**Output**: List of 3-5 flight options with:
- Airline, price, departure/arrival times
- Number of stops, duration
- Departure/arrival airports

**Code Location**: `agents/flight_agent.py:20-80`

#### 2. HotelAgent (`agents/hotel_agent.py`)

**Purpose**: Find hotels matching destination and budget.

**API**: Booking.com via RapidAPI

**Fallback**: Mock data (realistic hotels)

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
2. Identify conflicts (hotel location, flight timing, weather mismatches)
3. Detect synergies (beachfront hotel + beach activities)
4. Generate targeted messages to agents
5. Track conflict resolution progress

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

**LLMConfig**:
- `api_key`: Anthropic API key (required)
- `default_model`: claude-sonnet-4-5-20250929
- `intent_parser_model`: Model for intent parsing
- `collaboration_hub_model`: Model for collaboration
- `option_generator_model`: Model for option generation
- `quick_tasks_model`: claude-haiku (cheaper for simple tasks)

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

### Example 1: Hotel-Experience Location Conflict

**Round 1**:
```
Hotel Agent → "Downtown Athens Hotel" ($90/night, Athens city center)
Experience Agent → "Santorini caldera tour" (3hr ferry from Athens each way)
```

**Collaboration Hub Analysis**:
```
Conflict detected: Hotel in Athens, but top experience is Santorini (6hr round trip)

Messages generated:
1. To Hotel Agent:
   "Top experiences are in Santorini (3hr away). Consider Santorini hotels to reduce travel time."
   Data: { suggested_areas: ["Santorini", "Fira", "Oia"] }

2. To Experience Agent:
   "Can you find Athens-based activities if we keep the Athens hotel?"
   Data: { hotel_location: "Athens", radius_km: 20 }
```

**Round 2**:
```
Hotel Agent → Proposes 2 options:
  A) Santorini beachfront resort ($85/night)
  B) Athens hotel + nearby experiences

Experience Agent → Finds Athens alternatives:
  • Acropolis tour
  • Ancient Agora
  • Plaka food tour
  • Cape Sounion day trip
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

Message to Flight Agent:
   "Arrival at 6pm means Day 1 is lost. Look for earlier flights?"
   Data: { preferred_arrival: "before 14:00", flexible_date: true }
```

**Round 2**:
```
Flight Agent → Found earlier option:
  • JFK→ATH departing 5:00pm, arriving 11:00am+1 (+$80)
  • Allows full afternoon on Day 1
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

Messages:
1. To Experience Agent:
   "High temperatures (38°C). Prioritize indoor/evening activities?"
   Data: { suggested_times: ["morning", "evening"], indoor: true }

2. To Flight Agent:
   "Could we shift dates to avoid heatwave?"
   Data: { alternative_dates: ["July 1-7", "July 22-28"] }
```

**Round 2**:
```
Flight Agent → July 8 flight available (-5°C average temp)
Experience Agent → Adds evening/indoor alternatives:
  • Sunset cruises
  • Morning beach visits
  • Indoor museums
  • Evening taverna tours
```

**Final Options**:
```
Budget: Keep July 15, all evening activities
Balanced: July 8 flights (+$50), mixed schedule
Premium: July 8 + AC-upgraded hotels
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
   Analysis: "Hotel in Athens, experiences in Santorini → 3hr travel"
   Messages: [
     {to: "hotel", content: "Find Santorini hotels?"},
     {to: "experience", content: "Find Athens activities?"}
   ]
   Conflicts: [{ type: "location_mismatch", severity: "medium" }]

6. Round 2: Refinement
   • Hotel Agent → [5 Santorini hotels + 3 Athens hotels]
   • Experience Agent → [5 Athens experiences + 3 Santorini experiences]

7. Collaboration Hub 2
   Analysis: "Conflicts resolved, have options for both locations"
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

**Run**: `pytest tests/unit -v`

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
**Cost**: ~$0.10 per query (Anthropic API)
**Latency**: 60-120 seconds (3-round collaboration)
**Reliability**: Mock fallbacks ensure uptime without external APIs

---

For detailed API documentation, see **[API_REQUIREMENTS.md](API_REQUIREMENTS.md)**.
For developer guide, see **[CLAUDE.md](CLAUDE.md)**.
For quick overview, see **[README.md](README.md)**.
