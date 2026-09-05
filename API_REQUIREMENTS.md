# External API Requirements & Calls

**Minimum to run the system**: Only **1 API key** required!

```bash
# .env file
ANTHROPIC_API_KEY=add-your-key-here
```
Everything else uses realistic mock data automatically unless an API key is provided.

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
- `HybridConflictDetector` (optional, flag-gated) - Propose candidate conflicts beyond rule coverage

**API Calls Per Query**:
- Intent parsing: 1 call (~500 tokens)
- Collaboration analysis: 2 calls (round 1 & 2, ~2000 tokens each)
- Option generation: 4 calls (itinerary per option + main, ~15000 tokens total)
- **Total**: ~7-8 Claude API calls per user query

**Estimated Cost Per Query**: $0.05 - $0.15 (depending on complexity)

**Models Used**:
- `claude-sonnet-4-6` - Intent, collaboration, options, itinerary
- `claude-haiku-4-5-20251001` - Visa/safety (cheaper for simple tasks)

**Environment Variables**:
```bash
ANTHROPIC_API_KEY=sk-ant-xxxxx  # REQUIRED
```

**Get API Key**: https://console.anthropic.com

**Code Location**:
- `agents/intent_parser.py`
- `agents/collaboration_hub.py`
- `agents/option_generator.py`
- All use: `Anthropic(api_key=config.llm.api_key)`

**Token Cost Tracking**: All calls are tracked per-model via `metrics/token_tracker.py`. Session-level cost estimates appear in benchmark output. Unknown models fall back to Sonnet pricing rates.

---

### 2. **SerpApi Google Flights** ✈️ OPTIONAL

**Used By**: `FlightAgent`

**What It Does**:
- Searches real flight options via Google Flights
- Gets pricing, schedules, airlines, layovers
- Finds multi-leg routes

**API Calls**:
```
GET https://serpapi.com/search.json
Params:
  engine: google_flights
  departure_id: JFK          # IATA code required — see note below
  arrival_id: ATH            # IATA code required
  outbound_date: 2026-07-01
  return_date: 2026-07-14
  currency: USD
  hl: en
  api_key: your-key
```

**⚠️ IATA Code Resolution**: SerpApi requires valid 3-letter IATA airport codes. Sending raw city names ("Tokyo") or truncated codes yields a 400 error and an empty result set. `FlightAgent` maintains an internal `IATA_MAP` covering ~50 common destinations; unresolvable locations fall back to mock data rather than making a doomed API call (an empty flight list would silently invalidate the run downstream).

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
SERPAPI_API_KEY=your-key
```

**Get API Key**: https://serpapi.com (Free tier: 100 searches/month)

**Code Location**: `agents/flight_agent.py`

---

### 3. **Nuitee / LiteAPI Hotels** 🏨 OPTIONAL

**Used By**: `HotelAgent`

**What It Does**:
- Searches hotels by destination
- Gets pricing, ratings, amenities, geo coordinates
- Three-call flow: destination → placeId → rates → per-hotel details

**API Calls** (three sequential calls per query):
```
# 1) Destination → placeId (locality-preferred)
GET https://api.liteapi.travel/v3.0/data/places
Headers: X-API-Key: your-key
Params: textQuery=Greece, language=en, type=locality

# 2) placeId → rates (with bundled hotel data)
POST https://api.liteapi.travel/v3.0/hotels/rates
Headers: X-API-Key: your-key, Content-Type: application/json
Body: {
  "placeId": "...",
  "occupancies": [{"adults": 2}],
  "currency": "USD",
  "guestNationality": "US",
  "checkin": "2026-07-01",
  "checkout": "2026-07-14",
  "roomMapping": true,
  "maxRatesPerHotel": 1,
  "includeHotelData": true
}

# 3) hotelId → static details (name, address, geo coordinates)
GET https://api.liteapi.travel/v3.0/data/hotel
Headers: X-API-Key: your-key
Params: hotelId=...
```

**Rate Limits**: Sandbox ~5 req/s. `HotelAgent` paces requests with built-in delays.

**⚠️ Place Resolution Note**: `textQuery` matches against Nuitee's place database, which can resolve ambiguous destination names to wrong geographies (e.g., "Greece" → Greece, NY; "Bali" → Balıkesir, Türkiye). The `type=locality` filter prefers city-level results over regions, which reduces but does not eliminate this. The collaboration hub's `location_mismatch` detector flags these cases as conflicts — an honest signal of real provider behavior.

**Mock Fallback** (if no API key):
```python
# Returns realistic mock data (string-matched to hub location hints):
[
    {
        "name": "Aegean Bliss Resort",
        "total_usd": 85,
        "rating": 4.5,
        "location": "Santorini, Greece",
        "amenities": ["Pool", "Beach Access", "Free WiFi", "Breakfast"]
    },
    ...
]
```

**Environment Variables**:
```bash
NUITEE_API_KEY=your-key
```

**Get API Key**: https://nuitee.com or https://liteapi.travel (Sandbox key available)

**Code Location**: `agents/hotel_agent.py`

---

### 4. **OpenWeather API** 🌤️ OPTIONAL

**Used By**: `WeatherAgent`, `ExperienceAgent` (geocoding)

**What It Does**:
- **Weather**: Gets current conditions and 8-day forecast via One Call 3.0
- **Geocoding**: Resolves location strings to lat/lon coordinates (used by `ExperienceAgent` to attach real coordinates to activity locations, enabling distance-based hotel matching)

**API Calls**:
```
# Geocoding (used by both WeatherAgent and ExperienceAgent)
GET http://api.openweathermap.org/geo/1.0/direct
Params: q=Santorini, limit=1, appid=your-key

# One Call 3.0 (current + 8-day daily forecast)
GET https://api.openweathermap.org/data/3.0/onecall
Params:
  lat: 36.4071
  lon: 25.4567
  exclude: minutely,hourly,alerts
  units: metric
  appid: your-key
```

**⚠️ Subscription Note**: One Call 3.0 requires a separate "One Call by Call" subscription beyond the free tier. Without it, the API returns a 401 and the agent falls back to historical climate averages. The subscription is ~$0.0014/call with the first 1,000 calls/day free.

**⚠️ Forecast Horizon Note**: The 8-day forecast window starts *today*, not at the trip dates. For trip dates months away, the weather data represents current/near-term conditions as a **seasonal proxy**, not an actual forecast for the travel window. The `source` field in the response payload records this as `openweather_current_8day` for transparency.

**Mock Fallback** (if no API key):
```python
# Climate averages by destination and month:
{
    "avg_temp_c": 33,
    "avg_temp_f": 91,
    "summary": "Hot and dry, perfect for beaches. Minimal rain. Meltemi winds possible on islands.",
    "source": "historical_average"
}
```

**Environment Variables**:
```bash
OPENWEATHER_API_KEY=your-key
```

**Get API Key**: https://openweathermap.org/api (Free tier + One Call subscription)

**Code Location**: `agents/weather_agent.py`, `agents/experience_agent.py` (geocoding)

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

**Code Location**: `agents/visa_safety_agent.py`

---

## Configuration Files

### External API credentials — `config/api_config.py`:

```python
from config import get_api_config

config = get_api_config()

# LLM model configuration
print(f"Default model: {config.llm.default_model}")
```

### Runtime behavior settings — `config/settings.py`:

```python
from config.settings import get_settings

settings = get_settings()

# Inventory mode (mock | capture | replay)
print(f"Inventory mode: {settings.inventory_mode}")

# Hybrid LLM conflict detector (flag-gated, default off)
print(f"LLM candidates enabled: {settings.enable_llm_conflict_candidates}")
```

**Environment Variables for settings** (prefix `VOYAGER_`):
```bash
VOYAGER_INVENTORY_MODE=mock                    # mock | capture | replay
VOYAGER_INVENTORY_DIR=fixtures/live_inventory  # fixture storage
VOYAGER_ENABLE_LLM_CONFLICT_CANDIDATES=false   # hybrid detector flag
VOYAGER_LLM_DETECTOR_REPETITIONS=3             # self-consistency runs
VOYAGER_LLM_DETECTOR_TEMPERATURE=0.0           # deterministic proposals
```

**Booking URL Templates** (no API calls, just URL generation):
- Flights → Google Flights
- Hotels → Nuitee search page
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
- SerpApi (free tier): Free (100 searches/month)
- Nuitee (sandbox): Free
- OpenWeather (free tier + One Call): ~$0.001
- DuckDuckGo: Free
Total: ~$0.10 per query (essentially same!)

The paid APIs are so cheap they're negligible at this scale.
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
# - SerpApi: https://serpapi.com
# - Nuitee: https://nuitee.com or https://liteapi.travel
# - OpenWeather: https://openweathermap.org/api

# 2. Create .env file
cat > .env << EOF
# Required
ANTHROPIC_API_KEY=sk-ant-xxxxx

# Optional (Real Data)
SERPAPI_API_KEY=xxxxx
NUITEE_API_KEY=xxxxx
OPENWEATHER_API_KEY=xxxxx

# Optional (Benchmark Inventory Mode)
VOYAGER_INVENTORY_MODE=mock

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
export SERPAPI_API_KEY=your-key
uvicorn api.main:app --reload
```

### Benchmark with Live Inventory

```bash
export ANTHROPIC_API_KEY=sk-ant-xxxxx
export SERPAPI_API_KEY=your-key
export NUITEE_API_KEY=your-key
export OPENWEATHER_API_KEY=your-key

# Capture real API responses as hash-verified fixtures
python scripts/benchmark_queries.py --mode compare --inventory capture --query-count 12

# Replay them deterministically (same day as capture)
python scripts/benchmark_queries.py --mode compare --inventory replay --query-count 12
```

---

## API Call Flow (Single Query)

```
User: "Greece under $2000, beaches, summer 2026"

1. IntentParser → Anthropic API
   "Parse this into structured intent"

2. FlightAgent → SerpApi (or mock)
   "Find JFK → ATH flights"
   (IATA codes resolved internally before API call)

3. HotelAgent → Nuitee/LiteAPI (or mock)
   "Find hotels in Greece, beach, within budget"
   (3-call flow: places → rates → details)

4. ExperienceAgent → Anthropic API + OpenWeather geocoding
   "Recommend beach/food experiences in Greece"
   (each experience location geocoded to lat/lon)

5. WeatherAgent → OpenWeather One Call (or mock)
   "Current weather + 8-day forecast for Greece"

6. VisaSafetyAgent → DuckDuckGo (free)
   "Greece visa requirements US citizens"
   → Anthropic API (summarize results)

7. CollaborationHub → Anthropic API
   "Analyze findings, identify conflicts"
   (emits typed constraint payloads with geocoded centroids)

8. [Round 2-3 if needed]
   Selected agents re-run based on targeted feedback

9. OptionGenerator → Anthropic API (3-4 calls)
   "Generate budget itinerary"
   "Generate balanced itinerary"
   "Generate premium itinerary"

Total External Calls: 8-12 (depending on rounds and inventory mode)
Total Cost: ~$0.10
```

---

## ⚠️ Important Notes

1. **Mock data is very realistic** — designed to produce deterministic benchmark results.
2. **SerpApi free tier** — 100 searches/month, sufficient for development and benchmarking.
3. **Nuitee sandbox** — free test environment with realistic hotel data; rate-limited to ~5 req/s.
4. **OpenWeather One Call** — requires separate subscription beyond free tier (~$0.0014/call, first 1,000/day free). Geocoding endpoint is free and does not require the subscription.
5. **DuckDuckGo is always free** — No limits.
6. **Inventory capture/replay** — When `VOYAGER_INVENTORY_MODE=capture`, all external API responses are saved as hash-verified fixtures. Replay mode re-runs against these fixtures with zero network calls. Replay must run the same day as capture (effective dates are derived from the capture date).
7. **Dead providers** — Amadeus (shut down 2026-07-17) and Booking.com have been removed. Their env vars remain in `.env.example` as placeholders but are unused.

---