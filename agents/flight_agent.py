import os
from datetime import datetime

import httpx
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool

from metrics.token_tracker import TokenTrackingCallback

from .base_agent import BaseAgent

IATA_MAP = {
    "greece": "ATH",
    "athens": "ATH",
    "thessaloniki": "SKG",
    "santorini": "JTR",
    "mykonos": "JMK",
    "crete": "HER",
    "new york": "JFK",
    "los angeles": "LAX",
    "london": "LHR",
    "paris": "CDG",
}


def _resolve_iata(city: str) -> str:
    return IATA_MAP.get(city.lower().strip(), city.upper()[:3])


@tool
async def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    return_date: str | None,
    adults: int = 1,
    max_price: float | None = None,
) -> dict:
    """Search for flights using Amadeus API. Returns list of flight options with prices."""
    api_key = os.getenv("AMADEUS_API_KEY")
    api_secret = os.getenv("AMADEUS_API_SECRET")

    if not api_key or not api_secret:
        return _mock_flight_data(origin, destination, departure_date, return_date, adults)

    async with httpx.AsyncClient() as client:
        # Get OAuth token
        token_resp = await client.post(
            "https://test.api.amadeus.com/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": api_key,
                "client_secret": api_secret,
            },
        )
        token = token_resp.json()["access_token"]

        params = {
            "originLocationCode": _resolve_iata(origin),
            "destinationLocationCode": _resolve_iata(destination),
            "departureDate": departure_date,
            "adults": adults,
            "currencyCode": "USD",
            "max": 5,
        }
        if return_date:
            params["returnDate"] = return_date
        if max_price:
            params["maxPrice"] = int(max_price)

        resp = await client.get(
            "https://test.api.amadeus.com/v2/shopping/flight-offers",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
        )
        data = resp.json()
        offers = data.get("data", [])

        results = []
        for offer in offers[:3]:
            price = float(offer["price"]["total"])
            segments = offer["itineraries"][0]["segments"]
            results.append({
                "price_usd": price,
                "airline": segments[0]["carrierCode"],
                "departure": segments[0]["departure"]["at"],
                "arrival": segments[-1]["arrival"]["at"],
                "stops": len(segments) - 1,
                "duration": offer["itineraries"][0]["duration"],
            })
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

        departure_date = f"{travel_year}-07-01"
        return_date = f"{travel_year}-07-14"
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

        api_key = os.getenv("AMADEUS_API_KEY")
        api_secret = os.getenv("AMADEUS_API_SECRET")

        if api_key and api_secret:
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

        if not flights:
            best = None
        elif preferred_arrival_hour is not None:
            # Prefer cheapest flight that satisfies the timing constraint;
            # fall back to cheapest overall if none qualify.
            on_time = [
                f for f in flights
                if _arrival_hour(f.get("arrival", "")) < preferred_arrival_hour
            ]
            best = min(on_time, key=lambda f: f["price_usd"]) if on_time else min(flights, key=lambda f: f["price_usd"])
        else:
            best = min(flights, key=lambda f: f["price_usd"])

        return {
            "flights": flights,
            "selected_flight": best,
            "flight_cost_usd": best["price_usd"] if best else 0,
        }


def _arrival_hour(iso_str: str) -> int:
    """Parse an ISO datetime string and return the hour, or 25 on failure (never on-time)."""
    if not iso_str:
        return 25
    try:
        return datetime.fromisoformat(iso_str).hour
    except ValueError:
        return 25
