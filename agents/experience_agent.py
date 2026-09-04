import json
from pathlib import Path

import httpx
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

from metrics.token_tracker import TokenTrackingCallback

from .base_agent import BaseAgent

DESTINATIONS_DB = Path(__file__).parent.parent / "data" / "knowledge_base" / "destinations.json"

# Free OpenWeather geocoding endpoint — no API key required. Used to attach
# real coordinates to each experience from its human-readable `location` string
# ("Oia, Santorini"), so the hub can emit a non-null activity_centroid and the
# hotel agent can do distance-based matching against real inventory instead of
# substring matching that cannot succeed against real hotel addresses.
GEOCODE_URL = "http://api.openweathermap.org/geo/1.0/direct"

EXPERIENCE_PROMPT = """You are a travel experiences expert. Given the destination and traveller interests,
suggest the top 5 experiences including beaches, food, culture, and activities.

Destination: {destination}
Interests: {interests}
Budget for activities (USD): {activity_budget}
Duration: {duration_days} days
{location_focus}
Provide a JSON list of experiences with: name, description, cost_usd, category, best_time_of_day,
and location (the specific neighborhood, area, or part of {destination} where this takes place —
e.g. "Oia, Santorini" or "Plaka district" or "Chaweng Beach").
Return ONLY valid JSON array."""


class ExperienceAgent(BaseAgent):
    name = "experience_agent"
    short_name = "experience"
    description = "Recommends experiences and activities using RAG over destination knowledge base"

    def _setup(self):
        try:
            from config import get_api_config
            model = get_api_config().llm.experience_agent_model
        except Exception:
            model = "claude-sonnet-4-6"
        self.llm = ChatAnthropic(model=model, temperature=0.3, callbacks=[TokenTrackingCallback(model=model)])
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a travel experiences expert. Return only valid JSON."),
            ("human", EXPERIENCE_PROMPT),
        ])
        self._load_knowledge_base()

    def _load_knowledge_base(self):
        self.knowledge_base = {}
        if DESTINATIONS_DB.exists():
            with open(DESTINATIONS_DB) as f:
                data = json.load(f)
                for dest in data.get("destinations", []):
                    self.knowledge_base[dest["name"].lower()] = dest

    def _get_destination_context(self, destination: str) -> dict | None:
        dest_lower = destination.lower()
        for key, val in self.knowledge_base.items():
            if key in dest_lower or dest_lower in key:
                return val
        return None

    async def _execute(self, state: dict) -> dict:
        intent = state.get("intent", {})
        if not intent:
            return self._error_state("No intent in state")

        destination = intent.get("destination", "")
        interests = intent.get("interests", [])
        budget = intent.get("budget_usd", 2000)
        duration = intent.get("duration_days", 14)
        activity_budget = budget * 0.10

        context = self._get_destination_context(destination)
        if context:
            if not interests:
                interests = context.get("popular_interests", [])

        # Build location/weather guidance from collaboration messages, if any.
        location_focus_parts: list[str] = []
        for msg in self._messages_for_me(state):
            data = msg.get("data", {})
            # Weather constraint: schedule around heat or rain
            if msg.get("message_type") == "constraint" and data.get("suggested_activity_times"):
                times = data["suggested_activity_times"]
                location_focus_parts.append(
                    f"Weather advisory: prefer {' or '.join(times)} activities; "
                    "include indoor alternatives to avoid midday heat or rain."
                )
        location_focus = " ".join(location_focus_parts)

        chain = self.prompt | self.llm
        response = await chain.ainvoke({
            "destination": destination,
            "interests": ", ".join(interests) if interests else "beaches, local food, culture",
            "activity_budget": round(activity_budget),
            "duration_days": duration,
            "location_focus": location_focus,
        })

        try:
            import re
            text = response.content
            json_match = re.search(r'\[.*\]', text, re.DOTALL)
            experiences = json.loads(json_match.group()) if json_match else []
        except Exception:
            experiences = []
        if not experiences:
            experiences = self._fallback_experiences(destination, interests)

        # Attach real coordinates to each experience from its `location` string
        # so the hub can emit a non-null activity_centroid (typed constraint) and
        # the hotel agent can distance-match against real inventory.
        #
        # Live modes ONLY (capture/replay): in mock mode we stay fully offline
        # and deterministic — geocoding would leak real-world coordinates (and
        # garbage like "City Center" → Newport News, VA) into the centroid,
        # switching mock hotel selection from the always-satisfiable string hint
        # path to distance matching, which mock hotels can't satisfy.
        if self._inventory_mode() in ("capture", "replay"):
            await self._geocode_experiences(experiences)

        if context:
            beaches = context.get("top_beaches", [])
            restaurants = context.get("top_restaurants", [])
        else:
            beaches = []
            restaurants = []

        return {
            "experiences": experiences,
            "top_beaches": beaches,
            "top_restaurants": restaurants,
            "destination_context": context,
        }

    def _inventory_mode(self) -> str:
        from config.settings import get_settings
        return get_settings().inventory_mode

    async def _geocode_experiences(self, experiences: list[dict]) -> None:
        """Mutate each experience to add ``latitude``/``longitude``.

        Uses the free OpenWeather `/geo/1.0/direct` endpoint keyed on the
        experience's human-readable location string. If a spot can't resolve,
        it degrades gracefully to (no coords) rather than failing the agent.
        """
        import asyncio
        import os

        api_key = os.getenv("OPENWEATHER_API_KEY", "")
        if not experiences or not api_key:
            return
        async with httpx.AsyncClient(timeout=10) as client:
            for exp in experiences:
                query = (exp.get("location") or "").strip()
                if not query:
                    continue
                try:
                    resp = await client.get(
                        GEOCODE_URL,
                        params={"q": query, "limit": 1, "appid": api_key},
                    )
                    geo = resp.json()
                    if isinstance(geo, list) and geo:
                        exp["latitude"] = geo[0]["lat"]
                        exp["longitude"] = geo[0]["lon"]
                except Exception:
                    continue
                await asyncio.sleep(0.05)  # stay well under geocode rate limits

    def _fallback_experiences(self, destination: str, interests: list) -> list:
        return [
            {
                "name": f"Beach Day at {destination}",
                "description": "Relax on beautiful beaches",
                "cost_usd": 0, "category": "beach",
                "best_time_of_day": "morning", "location": "South Beach Area",
            },
            {
                "name": "Local Food Tour",
                "description": "Sample authentic local cuisine",
                "cost_usd": 50, "category": "food",
                "best_time_of_day": "evening", "location": "Old Town",
            },
            {
                "name": "Historical Sites Visit",
                "description": "Explore ancient ruins and monuments",
                "cost_usd": 25, "category": "culture",
                "best_time_of_day": "morning", "location": "City Center",
            },
        ]
