# External API Requirements & Calls

**Minimum to run the system**: Only **1 API key** required!

```bash
# .env file
ANTHROPIC_API_KEY=add-your-key-here
```
Everything else uses realistic mock data automatically unless api key is provided.

---

## All External API Calls

### 1. **Anthropic Claude API** - REQUIRED

**Used By**:
- `IntentParserAgent` - Parse user query into structured intent
- `CollaborationHubAgent` - Analyze findings, generate collaboration messages
- `OptionGeneratorAgent` - Generate 3 trip variants with day-by-day plans
- `ItineraryBuilderAgent` - Build detailed itinerary (legacy)
- `ExperienceAgent` - Recommend activities based on destination
- `VisaSafetyAgent` - Summarize visa/safety search results

**API Calls Per Query**:
- Intent parsing: 1 call (~500 tokens)
- Collaboration analysis: 2 calls (round 1 & 2, ~2000 tokens each)
- Option generation: 4 calls (itinerary per option + main, ~15000 tokens total)
- **Total**: ~7-8 Claude API calls per user query

**Estimated Cost Per Query**: $0.05 - $0.15 (depending on complexity)

**Models Used**:
- `claude-sonnet-4-5-20250929` - Intent, collaboration, options, itinerary
- `claude-haiku-4-20250514` - Visa/safety (cheaper for simple tasks)

**Environment Variables**:
```bash
ANTHROPIC_API_KEY=sk-ant-xxxxx  # REQUIRED
```

**Get API Key**: https://console.anthropic.com

**Code Location**:
- `agents/intent_parser.py:15`
- `agents/collaboration_hub.py:23`
- `agents/option_generator.py:28`
- All use: `Anthropic(api_key=config.llm.api_key)`

---

### 2. **Amadeus Flight API** OPTIONAL

**Used By**: `FlightAgent`

**What It Does**:
- Searches real flight options
- Gets pricing and schedules
- Finds multi-leg routes

**API Calls**:
1. OAuth token: `POST https://test.api.amadeus.com/v1/security/oauth2/token`
2. Flight search: `GET https://test.api.amadeus.com/v2/shopping/flight-offers`

**Mock Fallback** (if no API key):
```python
# Returns realistic mock data:
[
    {
        "airline": "United Airlines",
        "price": 680,
        "departure": "JFK",
        "arrival": "ATH",
        "stops": 1,
        "duration": "14h 15m"
    },
    {
        "airline": "Delta",
        "price": 750,
        "departure": "JFK",
        "arrival": "ATH",
        "stops": 0,
        "duration": "10h 30m"
    }
]
```

**Environment Variables**:
```bash
AMADEUS_API_KEY=your-key        
AMADEUS_API_SECRET=your-secret  
```
**Get API Key**: https://developers.amadeus.com (Free test API)

**Code Location**: `agents/flight_agent.py:20-45`

---

### 3. **Booking.com API** 

**Used By**: `HotelAgent`

**What It Does**:
- Searches hotels by destination
- Gets pricing, ratings, amenities
- Filters by preferences

**API Calls**:
```
GET https://booking-com.p.rapidapi.com/v1/hotels/search
Headers:
  X-RapidAPI-Key: your-key
  X-RapidAPI-Host: booking-com.p.rapidapi.com
```

**Mock Fallback** (if no API key):
```python
# Returns realistic mock data:
[
    {
        "name": "Aegean Bliss Resort",
        "price_per_night": 85,
        "rating": 4.5,
        "location": "Santorini, Greece",
        "amenities": ["Pool", "Beach Access", "Free WiFi", "Breakfast"]
    },
    {
        "name": "Athens Grand Hotel",
        "price_per_night": 120,
        "rating": 4.7,
        "location": "Athens City Center",
        "amenities": ["Rooftop Bar", "Gym", "Free WiFi"]
    }
]
```

**Environment Variables**:
```bash
BOOKING_API_KEY=your-rapidapi-key  
```
**Get API Key**: https://rapidapi.com/apidojo/api/booking-com (Subscription required)

**Code Location**: `agents/hotel_agent.py:18-60`

---

### 4. **OpenWeather API** 

**Used By**: `WeatherAgent`

**What It Does**:
- Gets weather forecasts
- Historical weather data
- Climate averages

**API Calls**:
```
GET https://api.openweathermap.org/data/3.0/onecall
Params:
  lat: 37.9838
  lon: 23.7275
  appid: your-key
```

**Mock Fallback** (if no API key):
```python
# Climate averages by destination:
{
    "Greece": {
        "July": {
            "avg_temp_c": 33,
            "avg_temp_f": 91,
            "conditions": "Sunny and hot",
            "precipitation_mm": 6,
            "sunshine_hours": 12,
            "sea_temp_c": 26
        }
    }
}
```

**Environment Variables**:
```bash
OPENWEATHER_API_KEY=your-key  
```

**Get API Key**: https://openweathermap.org/api (Free tier: 1000 calls/day)

**Code Location**: `agents/weather_agent.py:25-50`

---

### 5. **DuckDuckGo Search** 🔍 FREE

**Used By**: `VisaSafetyAgent`

**What It Does**:
- Searches visa requirements
- Travel safety advisories
- Entry requirements

**API Calls**:
- Uses `duckduckgo-search` Python library
- No API key needed
- Free unlimited searches

**Search Queries**:
```python
f"{destination} visa requirements for US citizens"
f"{destination} travel safety 2026"
```

**No API Key Needed!** Uses public search.

**Fallback** (if search fails):
```python
{
    "visa_required": False,
    "safety_level": 1,  # 1-5 scale
    "notes": "Generally safe for travelers"
}
```

**Code Location**: `agents/visa_safety_agent.py:18-40`

---

## Configuration File

All API settings are in `config/api_config.py`:

```python
from config import get_api_config

config = get_api_config()

# Check what's being used
print(f"Flight API: {config.flight.provider}")
print(f"Using mock: {config.flight.use_mock}")

# Get booking URL templates
flight_url = config.flight.booking_url_template.format(
    origin="JFK",
    destination="ATH",
    date="2026-07-01"
)
# → "https://www.google.com/travel/flights?q=JFK+to+ATH+2026-07-01"
```

**Booking URL Templates** (no API calls, just URL generation):
- Flights → Google Flights
- Hotels → Booking.com search page
- Experiences → GetYourGuide search page

These are just deep links for users to click, not API calls!

---

## Cost Breakdown

### With ONLY Anthropic (Recommended for Testing)

```
Per User Query:
- Anthropic Claude: $0.05 - $0.15
- All other agents: $0.00 (using mocks)
Total: ~$0.10 per query

For 100 test queries: ~$10
```

### With All Real APIs

```
Per User Query:
- Anthropic Claude: $0.05 - $0.15
- Amadeus (test): Free
- Booking.com: ~$0.001 (RapidAPI pricing)
- OpenWeather (free tier): Free
- DuckDuckGo: Free
Total: ~$0.10 per query (same!)

The paid APIs are so cheap they're negligible.
```

---

## Setup Instructions

### Option 1: Minimum (Testing Only)

```bash
# 1. Create .env file
cat > .env << EOF
ANTHROPIC_API_KEY=sk-ant-your-key-here
EOF

# 2. Run
uvicorn api.main:app --reload
```

**Result**: Everything works with realistic mock data!

### Option 2: Full Production Setup

```bash
# 1. Get all API keys
# - Anthropic: https://console.anthropic.com
# - Amadeus: https://developers.amadeus.com
# - Booking: https://rapidapi.com/apidojo/api/booking-com
# - OpenWeather: https://openweathermap.org/api

# 2. Create .env file
cat > .env << EOF
# Required
ANTHROPIC_API_KEY=sk-ant-xxxxx

# Optional (Real Data)
AMADEUS_API_KEY=xxxxx
AMADEUS_API_SECRET=xxxxx
BOOKING_API_KEY=xxxxx
OPENWEATHER_API_KEY=xxxxx

# Optional (LangSmith Tracing)
LANGSMITH_API_KEY=xxxxx
LANGCHAIN_TRACING_V2=true
LANGSMITH_PROJECT=voyager-travel-agent
EOF
```

---

## How to Test With/Without APIs

### Test with Anthropic Only

```bash
export ANTHROPIC_API_KEY=sk-ant-xxxxx
uvicorn api.main:app --reload
```

Visit http://localhost:5173 and search for "Greece under $2000, beaches, summer 2026"

**You'll get**:
- Real AI-powered intent parsing
- Real collaboration between agents
- Real itinerary generation
- 3 real options with day-by-day plans
- Mock flight/hotel/weather data (but realistic!)

### Test with Real Flight Data

```bash
export ANTHROPIC_API_KEY=sk-ant-xxxxx
export AMADEUS_API_KEY=your-key
export AMADEUS_API_SECRET=your-secret
uvicorn api.main:app --reload
```

---

## API Call Flow (Single Query)

```
User: "Greece under $2000, beaches, summer 2026"

1. IntentParser → Anthropic API
   "Parse this into structured intent"

2. FlightAgent → Amadeus API (or mock)
   "Find JFK → ATH flights in July 2026"

3. HotelAgent → Booking API (or mock)
   "Find hotels in Greece, beach, $50-150/night"

4. ExperienceAgent → Anthropic API
   "Recommend beach/food experiences in Greece"

5. WeatherAgent → OpenWeather API (or mock)
   "July 2026 weather in Greece"

6. VisaSafetyAgent → DuckDuckGo (free)
   "Greece visa requirements US citizens"
   → Anthropic API (summarize results)

7. CollaborationHub → Anthropic API
   "Analyze findings, identify conflicts"

8. [Round 2 if needed]
   Selected agents re-run based on messages

9. OptionGenerator → Anthropic API (3-4 calls)
   "Generate budget itinerary"
   "Generate balanced itinerary"
   "Generate premium itinerary"

Total External Calls: 7-10 (depending on rounds)
Total Cost: ~$0.10
```

---

## ⚠️ Important Notes

1. **Mock data is very realistic** 
2. **Amadeus test API is free** 
3. **OpenWeather free tier** - 1000 calls/day 
4. **Booking.com API** - This is the only one that costs money on RapidAPI
5. **DuckDuckGo is always free** - No limits

---

