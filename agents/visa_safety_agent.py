import os
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.tools import DuckDuckGoSearchRun

from .base_agent import BaseAgent


VISA_PROMPT = """You are a travel safety and visa expert. Based on current information, provide:
1. Visa requirements for US citizens traveling to {destination}
2. Current safety level (1=very safe, 5=avoid travel)
3. Key safety tips
4. Emergency contact numbers (police, ambulance, US embassy)
5. Health requirements (vaccinations, travel insurance recommendations)

Web search results for context:
{search_results}

Return structured JSON with keys: visa_required, visa_type, visa_on_arrival, safety_level, safety_summary, tips, emergency_contacts, health_requirements."""

SYSTEM_MSG = "You are a travel safety expert. Return only valid JSON."


class VisaSafetyAgent(BaseAgent):
    name = "visa_safety_agent"
    description = "Checks visa requirements and safety advisories for the destination"

    def _setup(self):
        self.llm = ChatAnthropic(model="claude-haiku-4-5-20251001", temperature=0)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_MSG),
            ("human", VISA_PROMPT),
        ])
        try:
            self.search = DuckDuckGoSearchRun()
        except Exception:
            self.search = None

    async def _execute(self, state: dict) -> dict:
        intent = state.get("intent", {})
        destination = intent.get("destination", "")

        search_results = ""
        if self.search:
            try:
                search_results = self.search.run(
                    f"US citizen visa requirements safety {destination} 2026"
                )
            except Exception:
                search_results = "Search unavailable — using training data."

        chain = self.prompt | self.llm
        response = await chain.ainvoke({
            "destination": destination,
            "search_results": search_results or "No search results available.",
        })

        import re, json
        try:
            text = response.content
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            visa_safety = json.loads(json_match.group()) if json_match else {}
        except Exception:
            visa_safety = self._fallback(destination)

        return {"visa_safety": visa_safety}

    def _fallback(self, destination: str) -> dict:
        greece_data = {
            "visa_required": False,
            "visa_type": "Schengen — 90 days visa-free for US citizens",
            "visa_on_arrival": False,
            "safety_level": 1,
            "safety_summary": "Greece is very safe for tourists. Standard precautions apply.",
            "tips": ["Keep copies of passport", "Use licensed taxis", "Be cautious of pickpockets in tourist areas"],
            "emergency_contacts": {"police": "100", "ambulance": "166", "us_embassy": "+30-210-721-2951"},
            "health_requirements": ["No mandatory vaccinations", "Travel insurance strongly recommended", "EHIC/travel health insurance advised"],
        }
        return greece_data if "greece" in destination.lower() else {
            "visa_required": True,
            "safety_level": 2,
            "safety_summary": f"Check current advisories for {destination}.",
            "tips": [],
            "emergency_contacts": {},
            "health_requirements": ["Travel insurance recommended"],
        }
