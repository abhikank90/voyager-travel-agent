# Testing Guide - Voyager Travel Agent

Comprehensive testing guide for the Voyager Travel Agent multi-agent system.

---

## **Test Coverage Summary**

| Component | Test Type | Files | Coverage Target |
|-----------|-----------|-------|-----------------|
| **Agents** | Unit | 12 test files | ≥ 80% |
| **Graph** | Integration | 3 test files | ≥ 70% |
| **API** | Integration | 1 test file | ≥ 75% |
| **Frontend** | Component | 3 test files | ≥ 70% |
| **Overall** | All | 19 test files | ≥ 70% |

**Current backend coverage: ~84%**

---

## **Test Structure**

```
tests/
├── unit/                              # Backend unit tests (no external dependencies)
│   ├── test_collaboration_hub.py      # CollaborationHub agent tests
│   ├── test_conflicts.py              # Conflict fingerprint + lifecycle tracker tests
│   ├── test_option_generator.py       # OptionGenerator agent tests
│   ├── test_flight_agent.py           # FlightAgent tests (SerpApi + mock)
│   ├── test_hotel_agent.py            # HotelAgent tests (Nuitee + mock)
│   ├── test_experience_agent.py       # ExperienceAgent tests (Claude + RAG + geocoding)
│   ├── test_weather_agent.py          # WeatherAgent tests
│   ├── test_visa_safety_agent.py      # VisaSafetyAgent tests
│   ├── test_budget_guardrail.py       # BudgetGuardrail tests
│   ├── test_intent_parser.py          # IntentParser tests
│   ├── test_token_tracker.py          # Per-model cost tracking tests
│   └── test_collector.py              # Metrics collector tests
│
├── integration/                       # Backend integration tests (require API keys)
│   ├── test_graph.py                  # Full graph execution tests
│   ├── test_api_endpoints.py          # FastAPI endpoint tests
│   └── test_selective_reexecution.py  # Selective re-execution efficiency tests
│
└── e2e/                               # End-to-end tests (future)

frontend/src/components/__tests__/    # Frontend component tests
├── TripOptionCard.test.tsx           # TripOptionCard component tests
├── OptionSelector.test.tsx           # OptionSelector component tests
└── CollaborationFeed.test.tsx        # CollaborationFeed component tests
```

---

## **Running Tests**

### **Quick Start - Run All Tests**

```bash
# Run all tests (backend + frontend) with coverage
bash scripts/run_all_tests.sh
```

### **Backend Tests**

#### **Unit Tests (No API Keys Required)**

```bash
# All unit tests
pytest tests/unit -v

# Specific agent tests
pytest tests/unit/test_collaboration_hub.py -v
pytest tests/unit/test_conflicts.py -v
pytest tests/unit/test_option_generator.py -v
pytest tests/unit/test_flight_agent.py -v

# With coverage
pytest tests/unit --cov=agents --cov=graph --cov-report=html
```

#### **Integration Tests (Requires ANTHROPIC_API_KEY)**

```bash
# Set API key
export ANTHROPIC_API_KEY=sk-ant-your-key-here

# Run integration tests
pytest tests/integration -v

# Full graph test
pytest tests/integration/test_graph.py -v

# API endpoint tests
pytest tests/integration/test_api_endpoints.py -v

# Selective re-execution tests
pytest tests/integration/test_selective_reexecution.py -v
```

#### **Known Pre-Existing Failure**

`tests/integration/test_graph.py::test_full_graph_greece` fails with a `TypeError` — the intent parser returns `duration_days: None` for the Greece query, and `itinerary_builder.py:70` crashes on `1 + duration`. This is a pre-existing bug in the intent parser's edge-case handling, unrelated to the collaboration or benchmark code. All other 199+ tests pass.

### **Frontend Tests**

```bash
cd frontend

# Run tests once
npm run test:run

# Run tests in watch mode
npm test

# Run with coverage
npm run test:coverage

# Run with UI
npm run test:ui
```

---

## **Test Coverage**

### **Backend Coverage**

```bash
# Generate coverage report
pytest tests/ --cov=agents --cov=graph --cov=api --cov-report=html

# Open coverage report
open coverage_report/html/index.html
```

### **Frontend Coverage**

```bash
cd frontend

# Generate coverage
npm run test:coverage

# Open report
open coverage/index.html
```

### **Coverage Reports Location**

- **Backend**: `coverage_report/html/index.html`
- **Frontend**: `frontend/coverage/index.html`

---

## **What's Tested**

### **1. Conflict Fingerprint & Lifecycle Tracker (15 tests)**
- Same conflict across rounds has stable fingerprint
- Agent order does not affect fingerprint
- Activity locations sorted/normalized in fingerprint
- Round number excluded from fingerprint
- Different evidence produces different fingerprints (per-query distinction)
- Different conflict types produce different fingerprints
- Prose description excluded from fingerprint
- Float rounding doesn't split identity
- Conflict dataclass fingerprint stability
- Lifecycle: new → persisting → resolved transitions
- Lifecycle: resolved → reopened transitions
- Introduced conflict detection
- Convergence summary computation
- State serialization/deserialization round-trip
- Empty state handling

### **2. Collaboration Hub Agent (13 tests)**
- Round 1 conflict detection (location mismatch)
- Round 1 message generation to agents
- Round 1 synergy identification
- Round 2 conflict resolution checking
- Flight timing conflict detection
- Weather-activity conflict detection
- Message type validation
- Shared insights extraction
- Anthropic API integration
- Deterministic conflict detection (detect_conflicts_only)
- Typed constraint payloads (activity_centroid, preferred_arrival)
- Experience centroid computation from geocoded coordinates
- Weather advisory label generation

### **3. Option Generator Agent (25 tests)**
- Generates exactly 3 options (budget, balanced, premium)
- Budget option at 75% of budget
- Balanced option at 100% of budget
- Premium option at 115% of budget
- Budget uses cheapest flight/hotel
- Premium uses best quality flight/hotel
- All options have booking URLs
- Booking URL format validation
- Highlights and trade-offs generation
- Day-by-day itinerary generation
- Error handling for missing data

### **4. Research Agents (35+ tests)**

**FlightAgent:**
- SerpApi Google Flights integration
- IATA code resolution (IATA_MAP lookup)
- Fallback to mock when IATA unresolvable
- Mock fallback when API key absent
- Required fields validation
- Price validation (realistic ranges)
- Multiple options returned
- Arrival constraint application (preferred_arrival)
- Feedback metrics recording
- API timeout graceful fallback

**HotelAgent:**
- Nuitee/LiteAPI three-call flow (places → rates → details)
- Mock hotel data generation
- Required fields (name, price, rating, location, coordinates)
- Price validation
- Rating validation (0-5 range)
- Location constraint application (activity_centroid distance matching)
- Fallback to string-hint matching (mock-compatible)
- Feedback metrics recording (no_qualifying_option)
- Constraint parsing (break placement regression test)
- Budget constraint filtering

**ExperienceAgent:**
- RAG-based recommendations
- Claude API integration
- Geocoding of experience locations (capture/replay modes only)
- Geocoding skipped in mock mode (regression test)
- Weather constraint guidance in prompt
- Free experiences included
- Experiences match user interests
- Destination-specific recommendations

### **5. Weather & Visa/Safety Agents (15+ tests)**

**WeatherAgent:**
- OpenWeather One Call 3.0 integration
- Geocoding (destination → lat/lon)
- Source label honesty (openweather_current_8day)
- Climate averages fallback
- Historical climate by destination/month
- Missing month handling

**VisaSafetyAgent:**
- DuckDuckGo search integration
- Claude summarization
- Visa required boolean
- Safety level rating
- Search failure handling

### **6. Metrics & Infrastructure (15+ tests)**

**TokenTracker:**
- Per-model token tracking
- Cost computation at correct per-model rates
- Haiku tokens priced at Haiku rates (not Sonnet)
- Unknown model fallback to Sonnet pricing
- Session cost aggregation
- Conservation: no tokens silently dropped

**Collector:**
- Session recording to JSONL
- Aggregate summary computation
- Convergence percentage calculations
- Unsatisfiable constraint rate (per-query, not summed)
- Results artifact writing (run_summary, CSVs)
- Schema version tracking

### **7. API Endpoints (12 tests)**
- Health endpoint
- Collaborative endpoint returns 3 options
- Request validation
- Option selection endpoint
- Invalid option ID handling
- Refinement endpoint
- Refinement validation
- Error handling
- Collaboration messages in response
- Booking URLs in options

### **8. Selective Re-Execution (integration)**
- Only targeted agents re-run in Round 2
- Untargeted agents' Round-1 outputs preserved
- Agent-call savings computation
- Round 3 triggering on unresolved conflicts
- Full re-run vs selective comparison

### **9. Frontend Components (30+ tests)**

**TripOptionCard:**
- Renders title and cost
- Displays flight and hotel info
- Shows highlights and trade-offs
- onSelect callback
- onViewDetails callback
- Color coding by style (green/blue/purple)
- Selected state styling

**OptionSelector:**
- Renders all 3 option cards
- Displays all costs
- Comparison table
- Forwards callbacks to cards
- Empty state handling

**CollaborationFeed:**
- Renders collaboration messages
- Displays round number
- Shows from/to agents
- Color coding by message type
- Icons for message types
- All message types displayed correctly

---

## **Benchmark Testing**

The benchmark suite (`scripts/benchmark_queries.py`) doubles as an integration test harness for the collaboration layer.

### **Mock Benchmark (CI-friendly, no travel API keys)**

```bash
# 25 queries × 2 modes (full + baseline), deterministic
python scripts/benchmark_queries.py --mode compare --inventory mock
```

Expected: 100% conflict resolution, converged at Round 2, zero introductions/reopens.

### **Live Capture + Replay (requires API keys)**

```bash
# Capture — hits real SerpApi/Nuitee/OpenWeather
python scripts/benchmark_queries.py --mode compare --inventory capture --query-count 12

# Replay — same day, zero network calls
python scripts/benchmark_queries.py --mode compare --inventory replay --query-count 12
```

Expected: Lower resolution rate than mock (real inventory can't always satisfy constraints), measurable unsatisfiable constraint rate, some post-refinement introductions from LLM nondeterminism.

### **Hybrid LLM Detector Evaluation**

```bash
python scripts/eval_hybrid_detection.py
```

Evaluates the LLM conflict proposer against rule-based detection on hand-built probe states. Measures precision, recall, false-positive rate, self-consistency.

---

## **Test Best Practices**

### **Writing Tests**

1. **Use descriptive test names**
   ```python
   async def test_round_1_identifies_location_conflict(agent, state):
   ```

2. **Arrange, Act, Assert pattern**
   ```python
   # Arrange
   state = {"intent": {"destination": "Greece"}}

   # Act
   result = await agent._execute(state)

   # Assert
   assert "conflicts" in result
   ```

3. **Mock external dependencies**
   ```python
   @patch("agents.flight_agent.httpx")
   async def test_flight_search(mock_httpx):
       mock_httpx.AsyncClient.return_value.__aenter__.return_value.get.return_value = mock_response
   ```

4. **Test both success and error cases**
   ```python
   async def test_handles_api_timeout_gracefully(agent):
       # Test error handling
   ```

5. **Guard against mode leakage**
   ```python
   async def test_geocoding_skipped_in_mock_mode(agent):
       \"\"\"Geocoding must not fire in mock mode — mock is offline-deterministic.\"\"\"
       with patch("agents.experience_agent.httpx.AsyncClient", side_effect=AssertionError("geocoding leaked")):
           await agent._execute(state)  # should complete without geocoding
   ```

### **Frontend Testing**

1. **Test user interactions**
   ```typescript
   fireEvent.click(selectButton)
   expect(mockSelect).toHaveBeenCalledWith(0)
   ```

2. **Test rendering**
   ```typescript
   expect(screen.getByText('Budget Explorer')).toBeInTheDocument()
   ```

3. **Test accessibility**
   ```typescript
   const button = screen.getByRole('button', { name: /select/i })
   ```

---

## **Configuration Files**

- **`pytest.ini`** - Pytest configuration, coverage settings
- **`.coveragerc`** - Coverage.py configuration
- **`frontend/vitest.config.ts`** - Vitest configuration
- **`frontend/src/test/setup.ts`** - Test environment setup

---

## **Coverage Goals**

| Component | Current | Target |
|-----------|---------|--------|
| **conflicts.py** | ~94% | ≥ 90% |
| **CollaborationHub** | ~78% | ≥ 75% |
| **OptionGenerator** | ~94% | ≥ 80% |
| **FlightAgent** | ~88% | ≥ 80% |
| **HotelAgent** | ~92% | ≥ 80% |
| **ExperienceAgent** | ~90% | ≥ 80% |
| **WeatherAgent** | ~65% | ≥ 65% |
| **VisaSafetyAgent** | ~87% | ≥ 75% |
| **InventoryManager** | ~96% | ≥ 90% |
| **HybridConflictDetector** | ~98% | ≥ 90% |
| **MetricsCollector** | ~85% | ≥ 80% |
| **TokenTracker** | ~100% | ≥ 90% |
| **API Endpoints** | ~80% | ≥ 75% |
| **Frontend Components** | ~75% | ≥ 70% |
| **Overall** | ~84% | ≥ 70% |

---

## **What's NOT Tested (Yet)**

- [ ] End-to-end browser tests (Playwright/Cypress)
- [ ] WebSocket real-time streaming
- [ ] PersonalisationAgent (DynamoDB integration)
- [ ] ItineraryBuilderAgent (legacy)
- [ ] Remaining frontend components (DetailedItineraryView, etc.)
- [ ] Error boundary components
- [ ] Loading states
- [ ] Performance tests
- [ ] `test_full_graph_greece` — pre-existing intent parser bug (duration_days: None)

---

## **Future Improvements**

1. **Add E2E tests** with Playwright
   - Full user journey: search → options → selection → refinement
   - WebSocket streaming tests
   - Browser compatibility tests

2. **Increase frontend coverage**
   - Test DetailedItineraryView component
   - Test CollaborativeChatInterface orchestration
   - Test useWebSocket hook
   - Test error states and loading states

3. **Performance tests**
   - Load testing with Locust
   - Response time benchmarks
   - Concurrent user tests

4. **Fix pre-existing intent parser bug**
   - `duration_days: None` on Greece query → TypeError in itinerary_builder

---

## **Adding New Tests**

### **Backend Unit Test Template**

```python
"""
Unit tests for NewAgent.
"""

import pytest
from unittest.mock import patch, MagicMock
from agents.new_agent import NewAgent


@pytest.fixture
def agent():
    \"\"\"Create agent with mocked dependencies.\"\"\"
    with patch("agents.new_agent.ExternalAPI") as mock_api:
        agent = NewAgent()
        return agent


@pytest.mark.asyncio
async def test_new_functionality(agent):
    \"\"\"Test new functionality.\"\"\"
    state = {"intent": {"destination": "Greece"}}

    result = await agent._execute(state)

    assert "expected_key" in result
```

### **Frontend Component Test Template**

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { NewComponent } from '../NewComponent'

describe('NewComponent', () => {
  it('renders correctly', () => {
    render(<NewComponent />)
    expect(screen.getByText('Expected Text')).toBeInTheDocument()
  })

  it('handles user interaction', () => {
    const mockCallback = vi.fn()
    render(<NewComponent onAction={mockCallback} />)

    fireEvent.click(screen.getByRole('button'))
    expect(mockCallback).toHaveBeenCalled()
  })
})
```

---

## **Resources**

- **Pytest docs**: https://docs.pytest.org/
- **Vitest docs**: https://vitest.dev/
- **React Testing Library**: https://testing-library.com/react
- **FastAPI Testing**: https://fastapi.tiangolo.com/tutorial/testing/
- **Coverage.py**: https://coverage.readthedocs.io/

---