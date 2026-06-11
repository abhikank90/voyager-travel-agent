import os
import json
from pathlib import Path
from typing import Optional

from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

from .base_agent import BaseAgent
from metrics.token_tracker import TokenTrackingCallback


DESTINATIONS_DB = Path(__file__).parent.parent / "data" / "knowledge_base" / "destinations.json"

EXPERIENCE_PROMPT = """You are a travel experiences expert. Given the destination and traveller interests,
suggest the top 5 experiences including beaches, food, culture, and activities.

Destination: {destination}
Interests: {interests}
Budget for activities (USD): {activity_budget}
Duration: {duration_days} days

Provide a JSON list of experiences with: name, description, cost_usd, category, best_time_of_day.
Return ONLY valid JSON array."""


class ExperienceAgent(BaseAgent):
    name = "experience_agent"
    description = "Recommends experiences and activities using RAG over destination knowledge base"

    def _setup(self):
        self.llm = ChatAnthropic(model="claude-sonnet-4-6", temperature=0.3, callbacks=[TokenTrackingCallback()])
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

    def _get_destination_context(self, destination: str) -> Optional[dict]:
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

        chain = self.prompt | self.llm
        response = await chain.ainvoke({
            "destination": destination,
            "interests": ", ".join(interests) if interests else "beaches, local food, culture",
            "activity_budget": round(activity_budget),
            "duration_days": duration,
        })

        try:
            import re
            text = response.content
            json_match = re.search(r'\[.*\]', text, re.DOTALL)
            experiences = json.loads(json_match.group()) if json_match else []
        except Exception:
            experiences = self._fallback_experiences(destination, interests)

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

    def _fallback_experiences(self, destination: str, interests: list) -> list:
        return [
            {"name": f"Beach Day at {destination}", "description": "Relax on beautiful beaches", "cost_usd": 0, "category": "beach", "best_time_of_day": "morning"},
            {"name": "Local Food Tour", "description": "Sample authentic local cuisine", "cost_usd": 50, "category": "food", "best_time_of_day": "evening"},
            {"name": "Historical Sites Visit", "description": "Explore ancient ruins and monuments", "cost_usd": 25, "category": "culture", "best_time_of_day": "morning"},
        ]
