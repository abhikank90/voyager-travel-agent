import os
import httpx
from langchain_anthropic import ChatAnthropic

from .base_agent import BaseAgent


def _mock_hotel_data(destination: str, check_in: str, check_out: str, guests: int):
    return {
        "hotels": [
            {
                "name": f"Aegean Bliss Resort, {destination}",
                "price_per_night_usd": 85,
                "total_usd": 85 * 14,
                "rating": 4.3,
                "amenities": ["beach access", "breakfast included", "wifi", "pool"],
                "location": "Beachfront",
            },
            {
                "name": f"Cyclades Boutique Hotel, {destination}",
                "price_per_night_usd": 110,
                "total_usd": 110 * 14,
                "rating": 4.6,
                "amenities": ["rooftop bar", "wifi", "city center"],
                "location": "Old Town",
            },
        ],
        "mock": True,
    }


class HotelAgent(BaseAgent):
    name = "hotel_agent"
    description = "Searches hotels within budget and preferred dates"

    def _setup(self):
        self.llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)

    async def _execute(self, state: dict) -> dict:
        intent = state.get("intent", {})
        if not intent:
            return self._error_state("No intent in state")

        destination = intent.get("destination", "")
        budget = intent.get("budget_usd", 2000)
        travel_year = intent.get("travel_year", 2026)
        group_size = intent.get("group_size", 1)
        duration = intent.get("duration_days") or 14  # Handle None value
        accommodation_pref = intent.get("accommodation_preference", "hotel")

        check_in = f"{travel_year}-07-01"
        check_out = f"{travel_year}-07-{1 + duration:02d}"
        hotel_budget = budget * 0.45

        api_key = os.getenv("BOOKING_API_KEY", "")
        if api_key:
            result = await self._fetch_real(destination, check_in, check_out, group_size, hotel_budget)
        else:
            result = _mock_hotel_data(destination, check_in, check_out, group_size)

        hotels = result.get("hotels", [])
        affordable = [h for h in hotels if h["total_usd"] <= hotel_budget]
        best = affordable[0] if affordable else (hotels[0] if hotels else None)

        return {
            "hotels": hotels,
            "selected_hotel": best,
            "hotel_cost_usd": best["total_usd"] if best else 0,
        }

    async def _fetch_real(self, destination, check_in, check_out, guests, budget):
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://booking-com.p.rapidapi.com/v1/hotels/search",
                headers={
                    "X-RapidAPI-Key": os.getenv("BOOKING_API_KEY", ""),
                    "X-RapidAPI-Host": "booking-com.p.rapidapi.com",
                },
                params={
                    "dest_type": "city",
                    "dest_id": destination,
                    "checkin_date": check_in,
                    "checkout_date": check_out,
                    "adults_number": guests,
                    "room_number": 1,
                    "order_by": "price",
                    "filter_by_currency": "USD",
                },
            )
        data = resp.json()
        hotels = []
        for h in data.get("result", [])[:5]:
            hotels.append({
                "name": h.get("hotel_name", "Unknown"),
                "price_per_night_usd": h.get("min_total_price", 0),
                "total_usd": h.get("min_total_price", 0),
                "rating": h.get("review_score", 0),
                "amenities": [],
                "location": h.get("address", ""),
            })
        return {"hotels": hotels}
