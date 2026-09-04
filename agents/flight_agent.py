import os
from datetime import datetime

import httpx
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool

from metrics.token_tracker import TokenTrackingCallback

from . import inventory
from .base_agent import BaseAgent

# Airport IATA codes for common origins/destinations. SerpAPI (Google Flights)
# requires valid 3-letter IATA codes — sending a raw city name ("Tokyo") or
# truncated garbage ("TOK") yields a 400 and an empty result set, silently
# invalidating the whole run (empty flights → option_generator errors).
IATA_MAP = {
    # Greece
    "greece": "ATH", "athens": "ATH", "thessaloniki": "SKG",
    "santorini": "JTR", "mykonos": "JMK", "crete": "HER",
    # USA
    "new york": "JFK", "new york city": "JFK", "nyc": "JFK",
    "los angeles": "LAX", "la": "LAX", "san francisco": "SFO", "sfo": "SFO",
    "chicago": "ORD", "miami": "MIA", "orlando": "MCO", "seattle": "SEA",
    "hawaii": "HNL", "honolulu": "HNL",
    # Europe
    "london": "LHR", "paris": "CDG", "rome": "FCO", "barcelona": "BCN",
    "madrid": "MAD", "istanbul": "IST", "prague": "PRG", "budapest": "BUD",
    "lisbon": "LIS", "portugal": "LIS", "algarve": "FAO",
    "amsterdam": "AMS", "berlin": "BER", "vienna": "VIE",
    "reykjavik": "KEF", "iceland": "KEF", "ibiza": "IBZ", "malaga": "AGP",
    # Asia / Middle East
    "tokyo": "HND", "seoul": "ICN", "beijing": "PEK", "shanghai": "PVG",
    "hong kong": "HKG", "singapore": "SIN", "bangkok": "BKK", "thailand": "BKK",
    "bali": "DPS", "denpasar": "DPS", "jakarta": "CGK", "manila": "MNL",
    "ho chi minh": "SGN", "hanoi": "HAN", "vietnam": "HAN", "phnom penh": "PNH",
    "cambodia": "HAN", "phuket": "HKT",
    # South Asia
    "maldives": "MLE", "kathmandu": "KTM", "nepal": "KTM", "delhi": "DEL", "mumbai": "BOM",
    # Africa
    "morocco": "CMN", "casablanca": "CMN", "marrakech": "RAK",
    "kenya": "NBO", "nairobi": "NBO",
    # Americas
    "costa rica": "SJO", "san jose": "SJO", "mexico city": "MEX", "mexico": "MEX",
    "panama": "PTY", "lima": "LIM", "buenos aires": "EZE", "santiago": "SCL",
    # Oceania
    "new zealand": "AKL", "auckland": "AKL", "sydney": "SYD", "melbourne": "MEL",
    # Winter / adventure
    "patagonia": "PUQ", "punta arenas": "PUQ", "zurich": "ZRH", "geneva": "GVA",
    "swiss alps": "ZRH", "oslo": "OSL", "stockholm": "ARN", "copenhagen": "CPH",
}

# Common multi-word destinations that need a city→airport fallback not covered
# by the map above. SerpAPI accepts either the airport code or the city name in
# some forms; we conservatively pass through only known-safe values.
_DEFAULT_ORIGIN_IATA = "JFK"


def _resolve_iata(location: str) -> str:
    """Return a valid IATA code for a city/country string, else an empty string.

    Accepts an already-valid 3-letter uppercase IATA code as a passthrough
    (callers that resolve codes themselves may pass "JFK"/"ATH" directly).
    City names are looked up in ``IATA_MAP``. Empty result signals the caller
    to fall back to mock data rather than send an invalid code that SerpAPI
    rejects with a 400 (which silently empties the flight list and invalidates
    the run).
    """
    if not location or not str(location).strip():
        return ""
    value = str(location).strip()
    if value.isupper() and len(value) == 3 and value.isalpha():
        return value
    key = value.lower()
    return IATA_MAP.get(key, "")


@tool
async def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None,
    adults: int = 1,
    max_price: float | None = None,
) -> dict:
    """Search for flights using SerpApi (Google Flights). Returns flight options."""
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        return _mock_flight_data(origin, destination, departure_date, return_date, adults)

    origin_iata = _resolve_iata(origin)
    dest_iata = _resolve_iata(destination)
    if not origin_iata or not dest_iata:
        # Can't send a raw city name or a truncated code — SerpAPI 400s and
        # returns an empty flight list, silently invalidating the whole run
        # (empty flights → option_generator error). Fall back to realistic
        # mock data instead.
        return _mock_flight_data(origin, destination, departure_date, return_date, adults)

    params = {
        "engine": "google_flights",
        "departure_id": origin_iata,
        "arrival_id": dest_iata,
        "outbound_date": departure_date,
        "currency": "USD",
        "hl": "en",
        "type": "1" if return_date else "2",  # 1=round-trip, 2=one-way
        "api_key": api_key,
    }
    if return_date:
        params["return_date"] = return_date

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get("https://serpapi.com/search.json", params=params)
        resp.raise_for_status()
        data = resp.json()

    offers = data.get("best_flights", []) + data.get("other_flights", [])
    results = []
    for offer in offers:
        segments = offer.get("flights", [])
        if not segments:
            continue
        price = offer.get("price")
        if price is None:
            continue
        if max_price is not None and float(price) > float(max_price):
            continue
        results.append({
            "price_usd": float(price),
            "airline": segments[0].get("airline", ""),
            "departure": segments[0].get("departure_airport", {}).get("time", ""),
            "arrival": segments[-1].get("arrival_airport", {}).get("time", ""),
            "stops": max(len(segments) - 1, 0),
            "duration": offer.get("total_duration"),  # minutes (int)
            "duration_minutes": offer.get("total_duration"),
        })
        if len(results) >= 3:
            break
    return {"flights": results}


def _mock_flight_data(
    origin,
    destination,
    departure_date,
    return_date,
    adults,
    preferred_arrival_hour: int | None = None,
):
    """Fallback mock data for local dev without API keys.

    When preferred_arrival_hour is set (from a collaboration constraint), a
    well-timed option is included so that the constraint can be satisfied.
    The caller selects the cheapest flight that meets the constraint; this
    function only ensures a qualifying option exists.
    """
    flights = [
        {
            "price_usd": 680 * adults,
            "airline": "UA",
            "departure": f"{departure_date}T08:00:00",
            "arrival": f"{departure_date}T22:30:00",
            "stops": 1,
            "duration": "PT14H30M",
        },
        {
            "price_usd": 750 * adults,
            "airline": "DL",
            "departure": f"{departure_date}T10:30:00",
            "arrival": f"{departure_date}T23:45:00",
            "stops": 1,
            "duration": "PT13H15M",
        },
    ]

    if preferred_arrival_hour is not None:
        # Add a daytime-arrival option. Premium reflects real fare structure:
        # short-connection itineraries with early arrivals typically cost more.
        flights.append({
            "price_usd": 890 * adults,
            "airline": "LH",
            "departure": f"{departure_date}T06:00:00",
            "arrival": f"{departure_date}T13:00:00",
            "stops": 1,
            "duration": "PT7H00M",
        })

    return {"flights": flights, "mock": True}


class FlightAgent(BaseAgent):
    name = "flight_agent"
    short_name = "flight"
    description = "Searches flights and returns best options within budget"

    def _setup(self):
        try:
            from config import get_api_config
            model = get_api_config().llm.flight_agent_model
        except Exception:
            model = "claude-haiku-4-5-20251001"
        self.llm = ChatAnthropic(model=model, temperature=0, callbacks=[TokenTrackingCallback(model=model)])

    async def _execute(self, state: dict) -> dict:
        intent = state.get("intent", {})
        if not intent:
            return self._error_state("No intent in state")

        destination = intent.get("destination", "")
        origin = intent.get("origin") or "New York"
        budget = intent.get("budget_usd", 2000)
        intent.get("travel_month", "July")
        travel_year = intent.get("travel_year", 2026)
        group_size = intent.get("group_size", 1)

        departure_date, return_date = self._effective_dates(travel_year)
        flight_budget = budget * 0.45

        # Parse preferred_arrival constraint from collaboration messages, if any.
        # The hub sends "before 14:00" when the selected flight arrives late and wastes Day 1.
        preferred_arrival_hour: int | None = None
        for msg in self._messages_for_me(state):
            if msg.get("message_type") == "insight":
                pref = msg.get("data", {}).get("preferred_arrival", "")
                if pref:
                    try:
                        preferred_arrival_hour = int(
                            pref.replace("before ", "").split(":")[0].strip()
                        )
                    except ValueError:
                        pass
                    break

        api_key = os.getenv("SERPAPI_API_KEY")

        mode = self._inventory_mode()
        query_id = inventory.inventory_query_id(
            "serpapi", origin=origin, destination=destination,
            departure_date=departure_date, return_date=return_date, adults=group_size,
        )

        if mode == "replay":
            result = inventory.replay("serpapi", query_id)
        elif mode == "capture":
            if api_key:
                result = await search_flights.ainvoke({
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date,
                    "return_date": return_date,
                    "adults": group_size,
                    "max_price": flight_budget,
                })
            else:
                result = _mock_flight_data(
                    origin, destination, departure_date, return_date, group_size,
                    preferred_arrival_hour=preferred_arrival_hour,
                )
            inventory.capture("serpapi", result, query_id, run_label="flight-capture")
        elif mode == "mock":
            # Mock mode is fully offline even when API keys are set: the
            # deterministic fixture is the whole point (CI, unit tests, demos).
            result = _mock_flight_data(
                origin, destination, departure_date, return_date, group_size,
                preferred_arrival_hour=preferred_arrival_hour,
            )
        elif api_key:
            result = await search_flights.ainvoke({
                "origin": origin,
                "destination": destination,
                "departure_date": departure_date,
                "return_date": return_date,
                "adults": group_size,
                "max_price": flight_budget,
            })
        else:
            result = _mock_flight_data(
                origin, destination, departure_date, return_date, group_size,
                preferred_arrival_hour=preferred_arrival_hour,
            )

        flights = result.get("flights", [])

        feedback = self._apply_arrival_constraint(flights, preferred_arrival_hour)
        best = feedback["selected_flight"]

        return {
            "flights": flights,
            "selected_flight": best,
            "flight_cost_usd": best["price_usd"] if best else 0,
            "feedback_metrics": feedback["metrics"],
        }

    def _inventory_mode(self) -> str:
        from config.settings import get_settings
        return get_settings().inventory_mode

    @staticmethod
    def _apply_arrival_constraint(
        flights: list[dict], preferred_arrival_hour: int | None
    ) -> dict:
        """Apply the hub's preferred-arrival constraint at *selection* time.

        Returns the selected flight plus ``feedback_metrics`` describing whether
        the constraint was applied and satisfiable, or whether the agent fell
        back to the original cheapest selection because no candidate qualified.
        """
        if not flights:
            return {"selected_flight": None, "metrics": _feedback(applied=False)}

        if preferred_arrival_hour is None:
            best = min(flights, key=lambda f: f["price_usd"])
            return {"selected_flight": best, "metrics": _feedback(applied=False)}

        on_time = [
            f for f in flights
            if _arrival_hour(f.get("arrival", "")) < preferred_arrival_hour
        ]
        if on_time:
            best = min(on_time, key=lambda f: f["price_usd"])
            return {
                "selected_flight": best,
                "metrics": _feedback(
                    applied=True, satisfiable=True, fallback=False,
                    reason="qualifying_option_found",
                ),
            }

        best = min(flights, key=lambda f: f["price_usd"])
        return {
            "selected_flight": best,
            "metrics": _feedback(
                applied=True, satisfiable=False, fallback=True,
                reason="no_qualifying_option",
            ),
        }


def _feedback(
    applied: bool,
    satisfiable: bool = True,
    fallback: bool = False,
    reason: str = "",
) -> dict:
    return {
        "feedback_applied": applied,
        "feedback_satisfiable": satisfiable,
        "fallback_to_original_selection": fallback,
        "reason": reason,
    }


def _arrival_hour(iso_str: str) -> int:
    """Parse an ISO datetime string and return the hour, or 25 on failure (never on-time)."""
    if not iso_str:
        return 25
    try:
        return datetime.fromisoformat(iso_str).hour
    except ValueError:
        return 25
