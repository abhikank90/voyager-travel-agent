# Voyager Travel Agent

> "I want a vacation in Greece under $2000, with good beaches and local food around summer 2026"

**Three personalized trip options** — budget, balanced, and premium.

Voyager is a **collaborative multi-agent travel planning system** built on [LangGraph](https://github.com/langchain-ai/langgraph) and [LangSmith](https://smith.langchain.com). Agents communicate across multiple rounds to identify conflicts, refine recommendations, and generate three distinct itineraries tailored to different priorities — all streamed live to the browser.

---

## Demo

![Voyager Travel Agent Demo](docs/demo/voyager-demo.gif)

*Watch Voyager generate personalized trip options in real-time as agents collaborate to find flights, hotels, and experiences.*

---

## What Makes Voyager Different

**Agent Collaboration** - Agents don't just work independently; they communicate, identify conflicts (hotel far from activities), and refine together

**3 Personalized Options** - Get budget-conscious, balanced, and premium variants to choose from

**Multi-Round Refinement** - Up to 3 rounds of collaboration ensure optimal recommendations

**Direct Booking Links** - One-click access to book flights (Google Flights), hotels (Nuitee), and experiences (GetYourGuide)

**Follow-up Refinements** - "Use the hotel from option 3" or "Add more museums" - the system adapts

**Real-time Transparency** - Watch agents collaborate live in the UI

**Live Inventory Benchmarking** - Capture real API responses, replay them deterministically, and measure conflict resolution with content-addressed conflict fingerprints

---

## Demo Flow

```
User: "Greece under $2000, beaches and local food, summer 2026"

→ Round 1: All agents research in parallel
  [Flight]      UA JFK→ATH $680, 1 stop
  [Hotel]       Downtown Athens Hotel €90/night
  [Experience]  Santorini day trip (3hr ferry each way)
  [Weather]     July: 33°C, sunny, perfect beach weather
  [Visa/Safety] No visa required, very safe

→ Collaboration Hub analyzes findings
  "Hotel is in Athens, but top experience is Santorini (6hr round trip)"
  Message to Hotel: "Consider Santorini hotels to reduce travel"
  Message to Experience: "Find Athens-based activities if staying"

→ Round 2: Agents refine based on feedback
  Hotel Agent: Found Santorini beachfront resort €85/night
  Experience Agent: Added Acropolis, Plaka food tour (Athens options)

→ Budget validated → 3 options generated:

  ┌─────────────────────────────────────────────────────┐
  │ 💚 BUDGET - $1,500                                  │
  │ Athens-focused, budget hotel, free experiences      │
  │ ✓ Save $500  ⚠️ Basic hotel, 1 stop flight         │
  └─────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────┐
  │ 💙 BALANCED - $2,000                                │
  │ Mix of Athens & islands, mid-range, best value      │
  │ ✓ Perfect balance  ⚠️ Some compromises on luxury   │
  └─────────────────────────────────────────────────────┘

  ┌─────────────────────────────────────────────────────┐
  │ 💜 PREMIUM - $2,300                                 │
  │ Santorini resort, direct flight, exclusive tours    │
  │ ✓ Luxury & convenience  ⚠️ $300 over budget        │
  └─────────────────────────────────────────────────────┘

User selects "Balanced" → Full day-by-day itinerary with booking links
```
---

## Quick Start (Local)

### Prerequisites

- **Python 3.11+**
- **Node.js 20+**
- **[Anthropic API key](https://console.anthropic.com)** (required)
- Optional: Other travel APIs (all have mock fallbacks)

### 1. Clone and configure

```bash
git clone https://github.com/your-org/voyager-travel-agent
cd voyager-travel-agent
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY (that's all you need!)
```

### 2. Install Python dependencies

```bash
pip install -e ".[dev]"
```

### 3. Install frontend dependencies

```bash
cd frontend && npm install && cd ..
```

### 4. Run

**Option A — One command:**
```bash
bash scripts/local_dev.sh
```

**Option B — Separate terminals:**
```bash
# Terminal 1 — API
uvicorn api.main:app --reload --port 8000

# Terminal 2 — UI
cd frontend && npm run dev
```

**Option C — Docker Compose:**
```bash
docker compose up --build
```

Open [http://localhost:5173](http://localhost:5173)

API docs at [http://localhost:8000/docs](http://localhost:8000/docs)

---

## Project Structure

```
voyager-travel-agent/
├── agents/                         # Agent implementations
│   ├── base_agent.py               # Abstract base with tracing + shared date logic
│   ├── intent_parser.py            # Query → structured TravelIntent
│   ├── flight_agent.py             # Flight search (SerpApi Google Flights)
│   ├── hotel_agent.py              # Hotel search (Nuitee / LiteAPI)
│   ├── experience_agent.py         # Activity recommendations (Claude + RAG + geocoding)
│   ├── weather_agent.py            # Weather data (OpenWeather One Call API)
│   ├── visa_safety_agent.py        # Visa/safety info (DuckDuckGo + Claude)
│   ├── collaboration_hub.py        # Coordinates agent collaboration + conflict detection
│   ├── conflicts.py                # Conflict fingerprint identity + lifecycle tracker
│   ├── hybrid_conflict_detector.py # LLM conflict proposer with rule validation (flag-gated)
│   ├── inventory.py                # Capture/replay/mock fixture management
│   ├── option_generator.py         # Generates 3 trip variants
│   ├── budget_guardrail.py         # Cost validation
│   ├── itinerary_builder.py        # Synthesis (legacy)
│   └── personalisation.py          # User profile loading
│
├── graph/
│   ├── state.py                    # TravelState, TripOption, CollaborationMessage
│   └── travel_graph.py             # LangGraph multi-round state machine
│
├── config/
│   ├── api_config.py               # External API credentials and endpoints
│   ├── settings.py                 # Runtime behavior settings (inventory mode, LLM flags)
│   └── __init__.py
│
├── metrics/
│   ├── collector.py                # Benchmark session recording + aggregation
│   └── token_tracker.py            # Per-model token usage + cost tracking
│
├── api/
│   └── main.py                     # FastAPI + WebSocket (collaborative endpoints)
│
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── CollaborativeChatInterface.tsx   # Main UI orchestrator
│       │   ├── TripOptionCard.tsx               # Single option display
│       │   ├── OptionSelector.tsx               # 3-option comparison
│       │   ├── DetailedItineraryView.tsx        # Full itinerary + bookings
│       │   ├── CollaborationFeed.tsx            # Agent messages
│       │   ├── AgentStatusPanel.tsx             # Progress tracking
│       │   ├── BudgetTracker.tsx                # Budget visualization
│       │   ├── ItineraryCard.tsx                # Day-by-day display
│       │   └── __tests__/                       # Component tests
│       ├── hooks/
│       │   └── useWebSocket.ts                  # WebSocket hook
│       ├── types/
│       │   └── index.ts                         # TypeScript types
│       └── test/
│           └── setup.ts                         # Test environment setup
│
├── data/knowledge_base/
│   └── destinations.json           # Destination data for RAG
│
├── fixtures/
│   └── live_inventory/             # Captured real API responses (hash-verified)
│       └── manifest.json           # Fixture hashes + capture metadata
│
├── results/                        # Benchmark artifacts (written by benchmark runs)
│   ├── run_summary.json            # Aggregate metrics
│   ├── conflicts_by_round.csv      # Per-session round conflict counts
│   ├── conflict_lifecycle.csv      # Per-conflict identity + transitions
│   └── hybrid_candidates.csv       # LLM candidate isolation counts
│
├── tests/
│   ├── unit/                       # Agent unit tests
│   │   ├── test_collaboration_hub.py
│   │   ├── test_conflicts.py
│   │   ├── test_option_generator.py
│   │   ├── test_flight_agent.py
│   │   ├── test_hotel_agent.py
│   │   └── ... (more)
│   └── integration/                # API & graph tests
│       ├── test_api_endpoints.py
│       ├── test_graph.py
│       └── test_selective_reexecution.py
│
├── scripts/
│   ├── local_dev.sh                # One-command local start
│   ├── run_all_tests.sh            # Comprehensive test runner
│   ├── benchmark_queries.py        # Benchmark runner (mock/capture/replay)
│   ├── eval_hybrid_detection.py    # Hybrid LLM detector evaluation
│   └── seed_knowledge_base.py      # Populate vector DB
│
├── infra/
│   ├── terraform/                  # AWS infrastructure
│   └── docker/                     # Dockerfiles
│
├── .env.example                    # Environment variables template
├── pytest.ini                      # Pytest configuration
├── .coveragerc                     # Coverage configuration
├── pyproject.toml                  # Python dependencies
├── docker-compose.yml              # Local development stack
├── ARCHITECTURE.md                 # 📖 System architecture documentation
├── API_REQUIREMENTS.md             # 📖 External API documentation
├── TESTING.md                      # 📖 Comprehensive testing guide
└── README.md                       # This file
```

---

## Configuration

All configuration via environment variables (`.env` file):

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | **Yes** | Powers all Claude calls (~$0.10/query) |
| `VOYAGER_API_KEY` | 🔒 **Production** | API key for endpoint protection (optional in dev) |
| `ALLOWED_ORIGINS` | No | CORS allowed origins (default: localhost:5173,3000) |
| `LANGSMITH_API_KEY` | No | LangSmith tracing for debugging |
| `LANGCHAIN_TRACING_V2` | No | Enable tracing (`true`/`false`) |
| `SERPAPI_API_KEY` | No | Real flight data via Google Flights (mock if absent) |
| `NUITEE_API_KEY` | No | Real hotel data via LiteAPI (mock if absent) |
| `OPENWEATHER_API_KEY` | No | Real weather via One Call 3.0 (historical averages if absent) |
| `VOYAGER_INVENTORY_MODE` | No | Inventory provider mode: `mock` (default), `capture`, `replay` |
| `VOYAGER_INVENTORY_DIR` | No | Fixture directory (default: `fixtures/live_inventory`) |
| `AWS_ACCESS_KEY_ID` | No | For DynamoDB user profiles |
| `DYNAMODB_TABLE` | No | User profiles table name |

**See `API_REQUIREMENTS.md` for detailed API documentation.**

---

## Benchmarking

Voyager includes a deterministic benchmarking system that measures multi-agent conflict resolution across mock, live, and replayed inventory.

### Quick Start

```bash
# Mock — fully offline, deterministic (no travel API keys needed)
python scripts/benchmark_queries.py --mode compare --inventory mock

# Capture — hits real APIs, saves hash-verified fixtures
python scripts/benchmark_queries.py --mode compare --inventory capture --query-count 12

# Replay — re-runs against captured fixtures (must run the SAME DAY as capture)
python scripts/benchmark_queries.py --mode compare --inventory replay --query-count 12

# Print summary of existing recorded sessions
python scripts/benchmark_queries.py --summary
```

### What It Measures

- **Conflict detection rate**: How often Round 1 produces conflicts
- **Resolution rate**: How often targeted feedback resolves them
- **Convergence**: Which round the system converges (R1/R2/R3)
- **Churn**: Post-refinement introductions and reopens (via content-addressed fingerprints)
- **Efficiency**: Agent-call savings vs. full re-execution
- **Cost**: Token usage and per-query cost

### Key Concepts

- **Content-addressed fingerprints**: Every conflict gets a stable identity from its type, agents, and normalized evidence data — so the lifecycle tracker can distinguish "same conflict persisting" from "new conflict introduced" across rounds
- **Capture/Replay**: Fixtures are hash-verified and date-keyed. Replay must run the same day as capture, because effective trip dates are derived from the capture date
- **Sharding**: Use `VOYAGER_QUERY_OFFSET=N` to parallelize long benchmark runs across terminals

### Hybrid LLM Detector Evaluation

```bash
# Evaluate the LLM conflict proposer against deterministic rule-based detection
python scripts/eval_hybrid_detection.py
```

---

## Security

Voyager includes production-ready security features:

### ** API Key Authentication**
- **Development**: Authentication disabled by default (no `VOYAGER_API_KEY` set)
- **Production**: Set `VOYAGER_API_KEY` in `.env` to require authentication
- **Usage**: Include `X-API-Key: your-key-here` header in all API requests

```bash
# Generate a strong API key
openssl rand -hex 32

# Add to .env
VOYAGER_API_KEY=your-generated-key-here
```

### ** Rate Limiting**
Protects against abuse and cost overruns:
- `/api/travel/plan` - 10 requests/minute per IP
- `/api/travel/collaborative` - 10 requests/minute per IP
- `/api/travel/select-option` - 30 requests/minute per IP
- `/api/travel/refine` - 20 requests/minute per IP
- Global default: 100 requests/hour per IP

### **🌐 CORS Protection**
- **Development**: Allows `localhost:5173` and `localhost:3000`
- **Production**: Set `ALLOWED_ORIGINS` to your frontend domain(s)

```bash
# In .env
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
```

### ** WebSocket Authentication**
WebSocket endpoints require API key via query parameter:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/travel/collaborative/session-123?token=your-api-key')
```

### **🛡️ Additional Security**
- `.gitignore` protects sensitive files (.env, credentials)
- Pydantic input validation on all endpoints
- Error messages sanitized (no stack traces to clients)
- Environment-based API key management
- Session isolation (in-memory, use Redis for production)

**For production deployment**: Enable HTTPS, use Redis for sessions, monitor rate limits, and rotate API keys regularly.

---

## Development

### Run tests

**Quick Start - Run All Tests:**
```bash
# Run comprehensive test suite (backend + frontend)
bash scripts/run_all_tests.sh
```

**Backend Tests:**
```bash
# Unit tests (no API keys needed - uses mocks)
pytest tests/unit -v

# Integration tests (requires ANTHROPIC_API_KEY)
export ANTHROPIC_API_KEY=sk-ant-your-key
pytest tests/integration -v

# With coverage report
pytest tests/ --cov=agents --cov=graph --cov=api --cov-report=html
open coverage_report/html/index.html
```

**Frontend Tests:**
```bash
cd frontend

# Install test dependencies (first time only)
npm install

# Run tests
npm test                    # Watch mode
npm run test:run            # Run once
npm run test:coverage       # With coverage
npm run test:ui             # Interactive UI

# View coverage
open coverage/index.html
```

**Test Coverage:**
- **200+ tests** across backend and frontend
- **~85% backend coverage** (target: ≥70%)
- See **[TESTING.md](TESTING.md)** for comprehensive testing guide

**Test Structure:**
- `tests/unit/` - Agent unit tests (including conflict fingerprint/lifecycle tests)
- `tests/integration/` - API, graph & selective re-execution tests
- `frontend/src/components/__tests__/` - Component tests

### Lint & Format

```bash
ruff check .
ruff format .
```

### Frontend development

```bash
cd frontend
npm run dev      # Dev server on :5173
npm run build    # Production build
npm run lint     # ESLint check
```

---

## API Usage

### REST Endpoint (Collaborative)

**Development (no auth):**
```bash
curl -X POST http://localhost:8000/api/travel/collaborative \
  -H "Content-Type: application/json" \
  -d '{"query": "Greece under $2000, beaches, summer 2026"}'
```

**Production (with API key):**
```bash
curl -X POST http://localhost:8000/api/travel/collaborative \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{"query": "Greece under $2000, beaches, summer 2026"}'
```

Returns:
```json
{
  "session_id": "abc-123",
  "trip_options": [
    {
      "option_id": 0,
      "style": "budget",
      "title": "Budget Explorer - Greece",
      "total_cost_usd": 1500,
      "flight": {...},
      "hotel": {...},
      "day_by_day": [...],
      "flight_booking_url": "https://...",
      "highlights": ["Save $500", "Local experiences"],
      "trade_offs": ["1 stop flight", "Basic hotel"]
    },
    // ... balanced and premium options
  ],
  "collaboration_messages": [
    {
      "from_agent": "collaboration_hub",
      "to_agent": "hotel",
      "content": "Activities far from hotel, find closer options"
    }
  ]
}
```

### WebSocket (Real-time Streaming)

**Development (no auth):**
```javascript
const ws = new WebSocket('ws://localhost:8000/ws/travel/collaborative/session-123')

ws.onopen = () => ws.send(JSON.stringify({
  query: "Greece under $2000, beaches, summer 2026"
}))
```

**Production (with API key):**
```javascript
const apiKey = 'your-api-key-here'
const ws = new WebSocket(`ws://localhost:8000/ws/travel/collaborative/session-123?token=${apiKey}`)

ws.onopen = () => ws.send(JSON.stringify({
  query: "Greece under $2000, beaches, summer 2026"
}))

ws.onmessage = (e) => {
  const msg = JSON.parse(e.data)

  if (msg.type === 'agent_update') {
    console.log(`Agent ${msg.agent}: ${msg.message}`)
  }

  if (msg.type === 'collaboration') {
    console.log('Agents collaborating:', msg.collaboration_messages)
  }

  if (msg.type === 'options_ready') {
    console.log('3 options ready:', msg.trip_options)
  }
}
```

### Option Selection & Refinement

```bash
# User selects option 1 (balanced)
curl -X POST http://localhost:8000/api/travel/select-option \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc-123", "option_id": 1}'

# User requests refinement
curl -X POST http://localhost:8000/api/travel/refine \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "abc-123",
    "selected_option_id": 1,
    "refinement_query": "Use the hotel from the budget option"
  }'
```

---

## Architecture Highlights

### Multi-Round Collaboration

Agents don't just run once — they iterate:

1. **Round 1**: All agents research in parallel
2. **Collaboration Hub**: Analyzes findings, identifies conflicts
3. **Round 2**: Agents refine based on peer feedback
4. **Collaboration Hub**: Checks if conflicts resolved
5. **Round 3** (optional): Final optimization if needed
6. **Option Generator**: Creates 3 variants (budget/balanced/premium)

### Conflict Detection Examples

- **Location mismatch**: Hotel in Athens, but top activities in Santorini
- **Timing inefficiency**: Flight arrives at 11pm, wastes first day
- **Weather conflicts**: Outdoor activities during rainy season
- **Budget pressure**: Spending too much on flights vs experiences

### Conflict Identity & Lifecycle Tracking

Every conflict gets a **content-addressed fingerprint** — a SHA-256 digest over its type, agents, and normalized evidence data (never prose). This enables:

- **Stable identity across rounds**: The same logical conflict keeps the same fingerprint when it reappears after refinement
- **Per-query distinction**: Two different queries' location mismatches have different fingerprints (different activity locations → different identity)
- **Lifecycle classification**: Each conflict is tracked as `new`, `persisting`, `resolved`, or `reopened`
- **Honest churn measurement**: Post-refinement introductions and reopens are measured, not masked

### Typed Constraints with Geocoded Evidence

The collaboration hub sends **typed constraint payloads**, not prose: activity centroids computed from geocoded experience coordinates, structured arrival-time preferences, and weather advisory labels. Consumers (hotel, flight agents) apply these via distance-based matching against real inventory coordinates — substring matching against human-readable location strings does not survive contact with real hotel-inventory payloads.

### Option Generation Strategy

**Budget (75% of budget)**:
- Cheapest flight (may have stops)
- Budget hotel (3-4 stars)
- Mix of free and low-cost experiences

**Balanced (100% of budget)**:
- Best value flight (price vs convenience)
- Mid-range hotel (4 stars)
- Curated mix of experiences

**Premium (115% of budget)**:
- Direct flights, optimal times
- Luxury hotel (4.5-5 stars)
- Exclusive experiences

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests (`bash scripts/run_all_tests.sh` or see [TESTING.md](TESTING.md))
5. Run linters (`ruff check . && ruff format .`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

---

## Roadmap

- [ ] Persistent session storage (Redis/DynamoDB)
- [ ] Refinement agent with LLM-powered query parsing
- [ ] Multi-destination trips ("Greece then Italy")
- [ ] Real-time price updates during user decision time
- [ ] User accounts & saved preferences
- [ ] Booking API integration (complete reservations in-app)
- [ ] Mobile app (iOS/Android)
- [ ] Group trip planning with voting
- [ ] AI-powered packing list generation
- [ ] Evaluation suite for collaboration quality
- [ ] Adaptive constraint relaxation for unsatisfiable conflicts
- [ ] Validators for LLM-proposed conflict types (visa timing, dietary, etc.)

---

## Documentation

- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Complete system architecture
- **[API_REQUIREMENTS.md](API_REQUIREMENTS.md)** - External API documentation
- **[TESTING.md](TESTING.md)** - Comprehensive testing guide

---

## License
MIT
---