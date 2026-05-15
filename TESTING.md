# Testing Guide - Voyager Travel Agent

Comprehensive testing guide for the Voyager Travel Agent multi-agent system.

---

## **Test Coverage Summary**

| Component | Test Type | Files | Coverage Target |
|-----------|-----------|-------|-----------------|
| **Agents** | Unit | 10 test files | ≥ 80% |
| **Graph** | Integration | 2 test files | ≥ 70% |
| **API** | Integration | 1 test file | ≥ 75% |
| **Frontend** | Component | 3 test files | ≥ 70% |
| **Overall** | All | 16 test files | ≥ 70% |

---

## **Test Structure**

```
tests/
├── unit/                              # Backend unit tests (no external dependencies)
│   ├── test_collaboration_hub.py      # CollaborationHub agent tests
│   ├── test_option_generator.py       # OptionGenerator agent tests
│   ├── test_flight_agent.py           # FlightAgent tests (API + mock)
│   ├── test_hotel_agent.py            # HotelAgent tests (API + mock)
│   ├── test_experience_agent.py       # ExperienceAgent tests (Claude + RAG)
│   ├── test_weather_agent.py          # WeatherAgent tests
│   ├── test_visa_safety_agent.py      # VisaSafetyAgent tests
│   ├── test_budget_guardrail.py       # BudgetGuardrail tests
│   └── test_intent_parser.py          # IntentParser tests
│
├── integration/                       # Backend integration tests (require API keys)
│   ├── test_graph.py                  # Full graph execution tests
│   └── test_api_endpoints.py          # FastAPI endpoint tests
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
```

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

## 📋 **Test Coverage**

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

### **1. Collaboration Hub Agent (13 tests)**
- Round 1 conflict detection (location mismatch)
- Round 1 message generation to agents
- Round 1 synergy identification
- Round 2 conflict resolution checking
- Flight timing conflict detection
- Weather-activity conflict detection
- Message type validation
- Shared insights extraction
- Anthropic API integration

### **2. Option Generator Agent (25 tests)**
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

### **3. Research Agents (30+ tests)**

**FlightAgent:**
- Amadeus API integration
- Mock fallback when API not configured
- Required fields validation
- Price validation (realistic ranges)
- Multiple options returned
- Flight cost calculation
- Error handling
- API timeout graceful fallback

**HotelAgent:**
- Mock hotel data generation
- Required fields (name, price, rating, location)
- Price validation
- Rating validation (0-5 range)
- Amenities as list
- Location matching destination
- Beach preference handling
- Budget constraint filtering
- Hotel cost calculation

**ExperienceAgent:**
- RAG-based recommendations
- Claude API integration
- Free experiences included
- Experiences match user interests
- Price validation
- Multiple options returned
- Valid experience types
- Destination-specific recommendations

### **4. Weather & Visa/Safety Agents (15+ tests)**

**WeatherAgent:**
- Climate averages fallback
- Temperature data included
- Conditions description
- Precipitation data
- Seasonal variation (summer vs winter)
- Missing month handling

**VisaSafetyAgent:**
- DuckDuckGo search integration
- Claude summarization
- Visa required boolean
- Safety level rating
- Search failure handling
- Destination-specific requirements

### **5. API Endpoints (12 tests)**
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

### **6. Frontend Components (30+ tests)**

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
   @patch("agents.flight_agent.requests")
   async def test_flight_search(mock_requests):
       mock_requests.get.return_value = mock_response
   ```

4. **Test both success and error cases**
   ```python
   async def test_handles_api_timeout_gracefully(agent):
       # Test error handling
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
| **CollaborationHub** | ~85% | ≥ 80% |
| **OptionGenerator** | ~90% | ≥ 80% |
| **FlightAgent** | ~75% | ≥ 75% |
| **HotelAgent** | ~75% | ≥ 75% |
| **ExperienceAgent** | ~75% | ≥ 75% |
| **WeatherAgent** | ~70% | ≥ 70% |
| **VisaSafetyAgent** | ~70% | ≥ 70% |
| **API Endpoints** | ~80% | ≥ 75% |
| **Frontend Components** | ~75% | ≥ 70% |
| **Overall** | ~75% | ≥ 70% |

---

## **What's NOT Tested (Yet)**

- [ ] End-to-end browser tests (Playwright/Cypress)
- [ ] WebSocket real-time streaming
- [ ] PersonalisationAgent (DynamoDB integration)
- [ ] ItineraryBuilderAgent (legacy)
- [ ] BaseAgent class
- [ ] Remaining frontend components (DetailedItineraryView, etc.)
- [ ] Error boundary components
- [ ] Loading states
- [ ] Performance tests

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

4. **Visual regression tests**
   - Screenshot comparisons
   - UI consistency checks

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

