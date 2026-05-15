"""
CollaborationHubAgent - Coordinates multi-agent collaboration.

Analyzes findings from all research agents, identifies conflicts and synergies,
and sends targeted messages to agents for refinement in subsequent rounds.
"""

from typing import Any
from anthropic import Anthropic
from config import get_api_config
from agents.base_agent import BaseAgent
from graph.state import TravelState, CollaborationMessage


class CollaborationHubAgent(BaseAgent):
    """Facilitates collaboration between research agents."""

    name = "collaboration_hub"
    description = "Coordinates agent collaboration and identifies synergies"

    def _setup(self):
        config = get_api_config()
        self.client = Anthropic(api_key=config.llm.api_key)
        self.model = config.llm.collaboration_hub_model

    async def _execute(self, state: TravelState) -> dict:
        round_num = state.get("collaboration_round", 1)

        if round_num == 1:
            return await self._analyze_round_1(state)
        elif round_num == 2:
            return await self._analyze_round_2(state)
        else:
            return {"collaboration_round": round_num}

    async def _analyze_round_1(self, state: TravelState) -> dict:
        """Analyze initial research findings and identify issues."""

        # Extract all agent findings
        analysis_prompt = self._build_analysis_prompt(state, round=1)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=2000,
            temperature=0.3,
            messages=[{
                "role": "user",
                "content": analysis_prompt
            }]
        )

        analysis_text = response.content[0].text

        # Generate collaboration messages based on analysis
        messages = self._generate_collaboration_messages(state, analysis_text, round=1)
        conflicts = self._identify_conflicts(state)
        synergies = self._identify_synergies(state)

        return {
            "agent_messages": messages,
            "conflicts": conflicts,
            "synergies": synergies,
            "collaboration_round": 1,
            "shared_discoveries": self._extract_shared_insights(state)
        }

    async def _analyze_round_2(self, state: TravelState) -> dict:
        """Check if conflicts are resolved, prepare for final round."""

        previous_conflicts = state.get("conflicts", [])
        current_conflicts = self._identify_conflicts(state)

        resolved = len(current_conflicts) < len(previous_conflicts)

        messages = []
        if not resolved and len(current_conflicts) > 0:
            # Need another round of refinement
            messages = self._generate_collaboration_messages(state, "", round=2)

        return {
            "agent_messages": messages,
            "conflicts": current_conflicts,
            "collaboration_round": 2,
            "shared_discoveries": self._extract_shared_insights(state)
        }

    def _build_analysis_prompt(self, state: TravelState, round: int) -> str:
        """Build prompt for Claude to analyze agent findings."""

        intent = state.get("intent", {})
        flights = state.get("flights", [])
        hotels = state.get("hotels", [])
        experiences = state.get("experiences", [])
        weather = state.get("weather", {})
        visa_safety = state.get("visa_safety", {})

        return f"""You are coordinating a multi-agent travel planning system. Analyze the findings from all agents and identify:
1. **Conflicts** - Issues where agent findings don't align well (e.g., hotel far from activities, flight times waste days)
2. **Synergies** - Opportunities to enhance the trip (e.g., hotel near best beaches, weather perfect for outdoor activities)
3. **Optimization opportunities** - Ways agents could collaborate better

**User Intent:**
- Destination: {intent.get('destination')}
- Budget: ${intent.get('budget_usd')}
- Interests: {intent.get('interests', [])}
- Travel dates: {intent.get('travel_month')}

**Flight Agent Findings:**
{self._format_flights(flights[:3])}

**Hotel Agent Findings:**
{self._format_hotels(hotels[:5])}

**Experience Agent Findings:**
{self._format_experiences(experiences[:5])}

**Weather Agent Findings:**
{self._format_weather(weather)}

**Visa/Safety Agent Findings:**
{self._format_visa_safety(visa_safety)}

Provide a concise analysis highlighting:
- Top 3 conflicts or misalignments
- Top 3 synergies or opportunities
- Recommendations for agent refinements in round {round + 1}
"""

    def _format_flights(self, flights: list) -> str:
        if not flights:
            return "No flights found yet"
        result = []
        for f in flights:
            result.append(f"- {f.get('airline', 'Unknown')} ${f.get('price', 0)} ({f.get('duration', 'N/A')})")
        return "\n".join(result)

    def _format_hotels(self, hotels: list) -> str:
        if not hotels:
            return "No hotels found yet"
        result = []
        for h in hotels:
            result.append(f"- {h.get('name', 'Unknown')} ${h.get('price_per_night', 0)}/night in {h.get('location', 'Unknown')}")
        return "\n".join(result)

    def _format_experiences(self, experiences: list) -> str:
        if not experiences:
            return "No experiences found yet"
        result = []
        for e in experiences:
            result.append(f"- {e.get('name', 'Unknown')} - {e.get('description', '')[:50]}...")
        return "\n".join(result)

    def _format_weather(self, weather: dict) -> str:
        if not weather:
            return "No weather data yet"
        return f"Avg temp: {weather.get('avg_temp_c', 'N/A')}°C, Conditions: {weather.get('conditions', 'N/A')}"

    def _format_visa_safety(self, visa_safety: dict) -> str:
        if not visa_safety:
            return "No visa/safety data yet"
        return f"Visa required: {visa_safety.get('visa_required', 'Unknown')}, Safety level: {visa_safety.get('safety_level', 'Unknown')}"

    def _generate_collaboration_messages(
        self,
        state: TravelState,
        analysis: str,
        round: int
    ) -> list[CollaborationMessage]:
        """Generate messages to send to specific agents based on analysis."""

        messages: list[CollaborationMessage] = []

        # Check hotel-experience alignment
        if self._check_hotel_experience_mismatch(state):
            messages.append({
                "from_agent": "collaboration_hub",
                "to_agent": "hotel",
                "message_type": "constraint",
                "content": "Top experiences are located far from selected hotels. Consider hotels closer to activity hubs.",
                "data": {
                    "activity_locations": self._get_experience_locations(state),
                    "current_hotel_location": state.get("selected_hotel", {}).get("location", "")
                },
                "round": round
            })
            messages.append({
                "from_agent": "collaboration_hub",
                "to_agent": "experience",
                "message_type": "question",
                "content": "Can you find activities near the selected hotel area?",
                "data": {
                    "hotel_location": state.get("selected_hotel", {}).get("location", ""),
                    "radius_km": 10
                },
                "round": round
            })

        # Check flight timing issues
        if self._check_flight_timing_issue(state):
            messages.append({
                "from_agent": "collaboration_hub",
                "to_agent": "flight",
                "message_type": "insight",
                "content": "Current flight arrival/departure times may waste partial days. Look for better-timed options.",
                "data": {
                    "preferred_arrival": "before 14:00",
                    "preferred_departure": "after 18:00"
                },
                "round": round
            })

        # Check weather-activity alignment
        if self._check_weather_activity_mismatch(state):
            messages.append({
                "from_agent": "collaboration_hub",
                "to_agent": "experience",
                "message_type": "constraint",
                "content": "Weather shows high temperatures or rain. Prioritize indoor or evening activities.",
                "data": {
                    "weather_concerns": state.get("weather", {}).get("warnings", []),
                    "suggested_activity_times": ["morning", "evening"]
                },
                "round": round
            })

        # Budget pressure
        flights = state.get("flights", [])
        hotels = state.get("hotels", [])
        if flights and hotels:
            cheapest_flight = min(flights, key=lambda f: f.get("price", 999999))
            current_flight = state.get("selected_flight", flights[0])
            if current_flight.get("price", 0) > cheapest_flight.get("price", 0) * 1.2:
                messages.append({
                    "from_agent": "collaboration_hub",
                    "to_agent": "flight",
                    "message_type": "proposal",
                    "content": f"Consider cheaper flight option to free up budget for experiences.",
                    "data": {
                        "alternative_flight": cheapest_flight
                    },
                    "round": round
                })

        return messages

    def _check_hotel_experience_mismatch(self, state: TravelState) -> bool:
        """Check if hotel location is far from main activities."""
        # Simplified check - in production, use geocoding
        hotel = state.get("selected_hotel", {})
        experiences = state.get("experiences", [])

        if not hotel or not experiences:
            return False

        hotel_location = hotel.get("location", "").lower()
        experience_locations = [e.get("location", "").lower() for e in experiences[:3]]

        # Simple heuristic: if hotel location doesn't match any top experience locations
        matches = any(loc in hotel_location or hotel_location in loc for loc in experience_locations)
        return not matches

    def _check_flight_timing_issue(self, state: TravelState) -> bool:
        """Check if flight times waste partial days."""
        flight = state.get("selected_flight", {})
        if not flight:
            return False

        arrival_time = flight.get("arrival_time", "")
        departure_time = flight.get("departure_time", "")

        # Simple check: late arrivals (after 8pm) or early departures (before 10am) waste days
        if arrival_time and ":" in arrival_time:
            hour = int(arrival_time.split(":")[0])
            if hour >= 20:  # 8pm or later
                return True

        if departure_time and ":" in departure_time:
            hour = int(departure_time.split(":")[0])
            if hour < 10:  # before 10am
                return True

        return False

    def _check_weather_activity_mismatch(self, state: TravelState) -> bool:
        """Check if activities don't match weather conditions."""
        weather = state.get("weather", {})
        experiences = state.get("experiences", [])

        if not weather or not experiences:
            return False

        avg_temp = weather.get("avg_temp_c", 25)
        conditions = weather.get("conditions", "").lower()

        # Check for extreme heat or rain
        if avg_temp > 35 or "rain" in conditions or "storm" in conditions:
            # Check if experiences are mostly outdoor
            outdoor_count = sum(1 for e in experiences[:5] if "beach" in e.get("name", "").lower() or "outdoor" in e.get("description", "").lower())
            return outdoor_count > 3

        return False

    def _get_experience_locations(self, state: TravelState) -> list[str]:
        """Extract unique locations from top experiences."""
        experiences = state.get("experiences", [])
        locations = [e.get("location", "") for e in experiences[:5]]
        return list(set(filter(None, locations)))

    def _identify_conflicts(self, state: TravelState) -> list[dict]:
        """Identify specific conflicts between agent findings."""
        conflicts = []

        if self._check_hotel_experience_mismatch(state):
            conflicts.append({
                "type": "location_mismatch",
                "agents": ["hotel", "experience"],
                "description": "Hotel location is far from main activities",
                "severity": "medium"
            })

        if self._check_flight_timing_issue(state):
            conflicts.append({
                "type": "timing_inefficiency",
                "agents": ["flight"],
                "description": "Flight times waste partial travel days",
                "severity": "low"
            })

        if self._check_weather_activity_mismatch(state):
            conflicts.append({
                "type": "weather_activity_mismatch",
                "agents": ["weather", "experience"],
                "description": "Activities not optimized for weather conditions",
                "severity": "medium"
            })

        return conflicts

    def _identify_synergies(self, state: TravelState) -> list[dict]:
        """Identify positive synergies between agent findings."""
        synergies = []

        # Hotel near beach + beach experiences
        hotel = state.get("selected_hotel", {})
        experiences = state.get("experiences", [])

        if "beach" in hotel.get("name", "").lower() or "beach" in hotel.get("description", "").lower():
            beach_experiences = [e for e in experiences if "beach" in e.get("name", "").lower()]
            if len(beach_experiences) >= 2:
                synergies.append({
                    "type": "location_synergy",
                    "agents": ["hotel", "experience"],
                    "description": "Beachfront hotel aligns with beach-focused activities",
                    "benefit": "Reduced travel time, enhanced experience"
                })

        # Good weather + outdoor activities
        weather = state.get("weather", {})
        if weather.get("avg_temp_c", 0) > 20 and weather.get("avg_temp_c", 0) < 32:
            outdoor_experiences = [e for e in experiences if "outdoor" in e.get("description", "").lower() or "beach" in e.get("name", "").lower()]
            if len(outdoor_experiences) >= 3:
                synergies.append({
                    "type": "weather_activity_synergy",
                    "agents": ["weather", "experience"],
                    "description": "Perfect weather for outdoor activities",
                    "benefit": "Optimal conditions for planned experiences"
                })

        return synergies

    def _extract_shared_insights(self, state: TravelState) -> dict[str, Any]:
        """Extract cross-cutting insights for all agents to see."""
        return {
            "destination_vibe": self._infer_destination_vibe(state),
            "budget_pressure": self._calculate_budget_pressure(state),
            "weather_outlook": state.get("weather", {}).get("conditions", "Unknown"),
            "safety_level": state.get("visa_safety", {}).get("safety_level", "Unknown"),
            "top_priorities": state.get("intent", {}).get("interests", [])
        }

    def _infer_destination_vibe(self, state: TravelState) -> str:
        """Infer the overall vibe of the destination."""
        experiences = state.get("experiences", [])
        if not experiences:
            return "Unknown"

        # Simple keyword analysis
        descriptions = " ".join([e.get("description", "") for e in experiences]).lower()

        if "beach" in descriptions and "relax" in descriptions:
            return "Beach & Relaxation"
        elif "adventure" in descriptions or "hiking" in descriptions:
            return "Adventure & Exploration"
        elif "food" in descriptions and "culture" in descriptions:
            return "Culinary & Cultural"
        else:
            return "Mixed"

    def _calculate_budget_pressure(self, state: TravelState) -> str:
        """Calculate how tight the budget is."""
        intent = state.get("intent", {})
        budget = intent.get("budget_usd", 0)

        flight_cost = state.get("flight_cost_usd", 0)
        hotel_cost = state.get("hotel_cost_usd", 0)

        if budget == 0:
            return "Unknown"

        spent_ratio = (flight_cost + hotel_cost) / budget

        if spent_ratio > 0.85:
            return "High - Very tight budget"
        elif spent_ratio > 0.70:
            return "Medium - Moderate budget"
        else:
            return "Low - Comfortable budget"
