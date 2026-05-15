# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Voyager is a **collaborative multi-agent travel planning system**. Unlike traditional single-pass systems, agents communicate across multiple rounds, identify conflicts, propose solutions, and generate 3 distinct trip options (budget, balanced, premium) for the user to choose from.

## Development Commands

### Python Backend

```bash
# Install dependencies (from repo root)
pip install -e ".[dev]"

# Run API server
uvicorn api.main:app --reload --port 8000

# Run tests
pytest tests/unit -v                    # Unit tests only (no API keys needed)
pytest tests/integration -v             # Integration tests (requires ANTHROPIC_API_KEY)
pytest --cov=agents --cov=graph         # All tests with coverage

# Lint and format
ruff check .
ruff format .

# Type check
mypy .
```

### Frontend

```bash
# Install dependencies
cd frontend && npm install

# Development server (from frontend/)
npm run dev                    # Runs on http://localhost:5173

# Build
npm run build                  # Outputs to frontend/dist

# Lint
npm run lint
```

### Full Stack Development

```bash
# One-command local start (from repo root)
bash scripts/local_dev.sh      # Starts both API and frontend

# Docker Compose
docker compose up --build      # Runs api, frontend, and Qdrant
```

## Architecture Overview

Voyager is a **collaborative multi-agent travel planning system** built on LangGraph. A user submits a natural-language query like "Greece under $2000, beaches and local food, summer 2026" and receives **3 distinct trip options** after agents collaborate across multiple rounds to identify conflicts and optimize recommendations.

### Collaborative Agent Execution Flow

```
User Query
    ↓
[Personalisation] ← loads user profile from DynamoDB/local JSON
    ↓
[Intent Parser] ← Claude Sonnet structured output → TravelIntent
    ↓
┌─── ROUND 1: Initial Research (Parallel) ───┐
│  [Flight Agent]       Amadeus API           │
│  [Hotel Agent]        Booking.com API       │
│  [Experience Agent]   Claude + RAG          │
│  [Weather Agent]      OpenWeather API       │
│  [Visa/Safety Agent]  DuckDuckGo + Claude   │
└──────────────────────────────────────────────┘
    ↓
[Collaboration Hub] ← Analyzes findings, identifies conflicts & synergies
    │
    ├─ Sends targeted messages to agents:
    │   • "Hotel: Activities 45min away, find closer options"
    │   • "Flight: Late arrival wastes Day 1, earlier flight?"
    ↓
┌─── ROUND 2: Refinement (Selective Re-run) ───┐
│  Agents that received messages re-execute    │
│  with new constraints from peer feedback     │
└───────────────────────────────────────────────┘
    ↓
[Collaboration Hub] ← Check if conflicts resolved
    ↓ (if needed)
[ROUND 3: Final Optimization]
    ↓
[Budget Guardrail] ← Validate costs
    ↓
[Option Generator] ← Create 3 variants: Budget | Balanced | Premium
    ↓
3 Trip Options (streamed to frontend)
    ↓
User selects option → Detailed view with booking URLs → Optional refinement
```

All five research agents run in **true parallel** via `asyncio.gather()`. Subsequent rounds selectively re-run only agents that received collaboration messages, optimizing latency.

### State Management (LangGraph)

The entire system is a `StateGraph` defined in `graph/travel_graph.py`. State is a `TravelState` TypedDict (`graph/state.py`) that flows through nodes. Each agent returns a partial dict of updates; LangGraph merges them into the running state.

**Conditional routing** at the budget guardrail:
- If `budget_loop_back=True` and `budget_retry_count <= 2`, route to `retry_research` (re-runs flight + hotel with 80% of budget)
- Otherwise, proceed to `itinerary_builder`

### Agent Design Pattern

Every agent inherits from `BaseAgent` (`agents/base_agent.py`):
- `run(state)` — public entry, wraps `_execute()` with LangSmith tracing and error logging
- `_execute(state)` — abstract method, returns a dict of state updates
- `_error_state(message)` — returns a non-fatal error dict (graph continues)

All agents detect missing API keys and fall back to realistic mock data — the system works end-to-end with only `ANTHROPIC_API_KEY`.

### API Layer

FastAPI (`api/main.py`) exposes:
- `POST /api/travel/plan` — synchronous endpoint, returns when complete
- `WebSocket /ws/travel/{session_id}` — streams agent events as they complete using `travel_graph.astream(stream_mode="updates")`

The frontend connects via WebSocket to receive real-time updates for the "Agents at work" status panel.

### Frontend Structure

React + TypeScript + Vite + Tailwind CSS single-page app:
- `ChatInterface.tsx` — orchestrates WebSocket connection and renders all UI zones
- `useWebSocket.ts` — typed hook for WebSocket lifecycle
- `AgentStatusPanel.tsx` — real-time agent progress (pending → running → done)
- `BudgetTracker.tsx` — visual budget breakdown with progress bar
- `ItineraryCard.tsx` — per-day card with morning/afternoon/evening sections

## Collaborative Agents

### CollaborationHubAgent (`agents/collaboration_hub.py`)

Coordinates agent collaboration by analyzing findings and generating messages.

**Key responsibilities**:
- Identify conflicts (hotel far from activities, flight timing issues)
- Detect synergies (beachfront hotel + beach experiences)
- Generate targeted messages to agents for refinement
- Track conflict resolution across rounds

**Example conflict detection**:
```python
def _check_hotel_experience_mismatch(self, state):
    hotel_location = state["selected_hotel"]["location"].lower()
    exp_locations = [e["location"].lower() for e in state["experiences"][:3]]
    # If hotel doesn't match any top experience locations
    matches = any(loc in hotel_location for loc in exp_locations)
    return not matches
```

**Message generation**:
```python
{
    "from_agent": "collaboration_hub",
    "to_agent": "hotel",
    "message_type": "constraint",
    "content": "Top experiences are 45min+ from selected hotel",
    "data": {"suggested_areas": ["Santorini Old Town", "Fira"]},
    "round": 1
}
```

### OptionGeneratorAgent (`agents/option_generator.py`)

Generates 3 distinct trip variants from refined research.

**Strategies**:
- **Budget** (75% of budget): Cheapest options, free experiences
- **Balanced** (100% of budget): Best value, comfort + cost balance
- **Premium** (115% of budget): Luxury hotels, exclusive experiences

**Key methods**:
- `_select_flight(flights, style)`: Choose flight based on option style
- `_select_hotel(hotels, style)`: Choose hotel based on option style
- `_generate_itinerary(...)`: Use Claude to build day-by-day plan
- `_generate_booking_url(...)`: Create deep links for bookings

**Booking URL templates** come from `config/api_config.py`:
```python
flight_url = config.flight.booking_url_template.format(
    origin="JFK", destination="Athens", date="2026-07-01"
)
```

## Adding a New Agent

1. Create `agents/my_agent.py` extending `BaseAgent`
2. Implement `_execute(state) -> dict` (must return state updates)
3. If collaborating, read `state.get("agent_messages", [])` and filter for your agent
4. Export it from `agents/__init__.py`
5. Add a node function in `graph/travel_graph.py`:
   ```python
   async def my_agent_node(state: TravelState) -> TravelState:
       return await _my_agent.run(state)
   ```
6. In `build_collaborative_graph()`, add the node and wire edges:
   ```python
   g.add_node("my_agent", my_agent_node)
   g.add_edge("previous_node", "my_agent")
   g.add_edge("my_agent", "next_node")
   ```
7. Update `graph/state.py` if your agent adds new state fields

## Configuration

### Environment Variables

All configuration is via environment variables (`.env` file locally):

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | **Yes** | Powers all Claude calls |
| `LANGSMITH_API_KEY` | No | Enables LangSmith tracing |
| `LANGCHAIN_TRACING_V2` | No | Set `true` to enable tracing |
| `AMADEUS_API_KEY` / `AMADEUS_API_SECRET` | No | Real flight data (mock if absent) |
| `BOOKING_API_KEY` | No | Real hotel data (mock if absent) |
| `OPENWEATHER_API_KEY` | No | Real weather (historical fallback if absent) |
| `AWS_ACCESS_KEY_ID` / `DYNAMODB_TABLE` | No | For DynamoDB user profiles |

Copy `.env.example` to `.env` and populate at minimum `ANTHROPIC_API_KEY`.

### API Configuration System (`config/api_config.py`)

Centralized configuration for all external APIs and booking URL templates:

```python
from config import get_api_config

config = get_api_config()

# Access specific configs
flight_config = config.flight  # FlightAPIConfig
hotel_config = config.hotel    # HotelAPIConfig
llm_config = config.llm        # LLMConfig

# Check if using mock
if config.flight.use_mock:
    # Use fallback data
    ...

# Generate booking URLs
booking_url = config.hotel.booking_url_template.format(
    destination="Athens",
    checkin="2026-07-01",
    checkout="2026-07-08"
)
```

**To update API providers**: Edit `config/api_config.py` and change the `booking_url_template` fields or add new API configs.

## Key Design Decisions

**LangGraph state machine**: The conditional retry loop and parallel fan-out are native LangGraph patterns. Adding a new agent is one `add_node` call. The graph is inspectable, testable, and LangSmith traces each node automatically.

**asyncio.gather for parallel research**: Five research agents running sequentially would take 15–30s. In parallel they take ~5s (bounded by the slowest single call). The budget guardrail can't run until all five are done, so true parallelism is critical.

**Mock fallbacks for every API**: The system should be runnable with only `ANTHROPIC_API_KEY`. This makes local development, CI, and demos independent of paid third-party API access. Mock data is realistic enough for UI development and evaluation runs.

**Fargate over Lambda (production)**: A complex multi-step query (9 nodes, 5 parallel external APIs, one 4096-token synthesis) regularly takes 45–90 seconds. Lambda's API Gateway WebSocket connection timeout (29s) would kill the connection. Fargate with ALB has no such constraint.

## Observability

LangSmith traces every node automatically via `@traceable` on `BaseAgent.run()` and `run_travel_query()`. Each trace captures input/output, tool calls, token usage, and latency.

Evaluation suite in `langsmith/evaluators.py` tests:
- Intent accuracy (destination + budget extraction)
- Budget compliance (final plan within budget)
- Itinerary completeness (all required fields present)

## Production Deployment

Infrastructure as Code in `infra/terraform/` provisions:
- ECS Fargate for API container (long-running agents exceed Lambda limits)
- DynamoDB for user profiles and session state
- SQS for agent event fan-out
- Qdrant (self-hosted on ECS) for destination knowledge RAG
- ALB for HTTPS termination and WebSocket upgrade

CI/CD in `.github/workflows/ci.yml` automates build → push to ECR → ECS rolling deploy on every push to `main`.

## API Endpoints

### Collaborative Endpoints (`api/main.py`)

**POST `/api/travel/collaborative`** - Generate 3 trip options
```python
{
    "query": "Greece under $2000, beaches, summer 2026",
    "user_id": "user123",
    "session_id": "optional-session-id"
}
```
Returns:
```python
{
    "session_id": "abc-123",
    "trip_options": [...],  # 3 variants
    "collaboration_messages": [...],
    "conflicts": [...],
    "synergies": [...]
}
```

**POST `/api/travel/select-option`** - User selects an option
```python
{
    "session_id": "abc-123",
    "option_id": 1  # 0, 1, or 2
}
```

**POST `/api/travel/refine`** - Refine selected option
```python
{
    "session_id": "abc-123",
    "selected_option_id": 1,
    "refinement_query": "Use hotel from option 3"
}
```

**WebSocket `/ws/travel/collaborative/{session_id}`** - Stream real-time updates

Events emitted:
- `agent_update`: Node progress ("Round 2: Refining...")
- `collaboration`: Agent messages ("Hotel: Looking for closer options")
- `options_ready`: Final event with 3 trip options

## Common Patterns

**Structured output from Claude**: `IntentParserAgent` uses `llm.with_structured_output(TravelIntent)` where `TravelIntent` is a Pydantic model. This ensures deterministic parsing with zero-temperature.

**Multi-round collaboration**: Agents read `state.get("agent_messages", [])` to check for messages targeting them. In rounds 2+, agents adapt their search based on peer feedback.
```python
round_num = state.get("collaboration_round", 1)
if round_num > 1:
    my_messages = [m for m in state.get("agent_messages", [])
                   if m["to_agent"] in ["my_agent", "all"]]
    # Adapt based on messages
    for msg in my_messages:
        if msg["message_type"] == "constraint":
            # Apply constraint to search
```

**Option generation with variants**: `OptionGeneratorAgent` creates 3 variants by selecting different flights/hotels:
- Budget: `min(flights, key=lambda f: f["price"])`
- Premium: `max(hotels, key=lambda h: h["rating"])`
- Balanced: Custom `_best_value_hotel()` scoring function

**Booking URL generation**: URLs come from `config.api_config`:
```python
config = get_api_config()
url = config.flight.booking_url_template.format(
    origin=intent["origin"],
    destination=intent["destination"],
    date=intent["departure_date"]
)
```

**WebSocket streaming**: `api/main.py` uses `collaborative_travel_graph.astream(stream_mode="updates")` to emit JSON events as each node completes, enabling real-time UI updates.

**Error handling**: Agents use `_error_state(message)` to return non-fatal errors. The graph continues even if one research agent fails (e.g., weather API timeout). Errors accumulate in `state["errors"]` and are surfaced in the final options.

**Session management**: `_session_store` (in-memory dict) holds state after option generation for selection and refinement. In production, use Redis or DynamoDB for persistence.
