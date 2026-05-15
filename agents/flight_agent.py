import os
import httpx
from typing import Optional
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage

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
    return_date: Optional[str],
    adults: int = 1,
    max_price: Optional[float] = None,
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


def _mock_flight_data(origin, destination, departure_date, return_date, adults):
    """Fallback mock data for local dev without API keys."""
    return {
        "flights": [
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
        ],
        "mock": True,
    }


class FlightAgent(BaseAgent):
    name = "flight_agent"
    description = "Searches flights and returns best options within budget"

    def _setup(self):
        self.llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)

    async def _execute(self, state: dict) -> dict:
        intent = state.get("intent", {})
        if not intent:
            return self._error_state("No intent in state")

        destination = intent.get("destination", "")
        origin = intent.get("origin") or "New York"  # Handle None value
        budget = intent.get("budget_usd", 2000)
        travel_month = intent.get("travel_month", "July")
        travel_year = intent.get("travel_year", 2026)
        group_size = intent.get("group_size", 1)

        departure_date = f"{travel_year}-07-01"
        return_date = f"{travel_year}-07-14"
        flight_budget = budget * 0.45

        result = await search_flights.ainvoke({
            "origin": origin,
            "destination": destination,
            "departure_date": departure_date,
            "return_date": return_date,
            "adults": group_size,
            "max_price": flight_budget,
        })

        flights = result.get("flights", [])
        best = min(flights, key=lambda f: f["price_usd"]) if flights else None

        return {
            "flights": flights,
            "selected_flight": best,
            "flight_cost_usd": best["price_usd"] if best else 0,
        }
