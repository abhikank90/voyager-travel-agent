import os

import httpx

from . import inventory
from .base_agent import BaseAgent

CLIMATE_FALLBACK: dict[str, dict[str, dict]] = {
    "greece": {
        "january": {
            "avg_temp_c": 13, "avg_temp_f": 55, "precipitation_mm": 55,
            "sunshine_hours": 4, "sea_temp_c": 16,
            "summary": "Mild winter, occasional rain. Good for sightseeing, fewer crowds.",
        },
        "february": {
            "avg_temp_c": 13, "avg_temp_f": 55, "precipitation_mm": 48,
            "sunshine_hours": 5, "sea_temp_c": 15,
            "summary": "Cool and sometimes rainy. Off-peak season.",
        },
        "march": {
            "avg_temp_c": 15, "avg_temp_f": 59, "precipitation_mm": 40,
            "sunshine_hours": 6, "sea_temp_c": 15,
            "summary": "Early spring, warming up. Wildflowers beginning.",
        },
        "april": {
            "avg_temp_c": 19, "avg_temp_f": 66, "precipitation_mm": 25,
            "sunshine_hours": 8, "sea_temp_c": 17,
            "summary": "Warm spring. Excellent for hiking and sightseeing.",
        },
        "may": {
            "avg_temp_c": 24, "avg_temp_f": 75, "precipitation_mm": 15,
            "sunshine_hours": 9, "sea_temp_c": 20,
            "summary": "Warm and sunny. Pre-peak season, good value.",
        },
        "june": {
            "avg_temp_c": 29, "avg_temp_f": 84, "precipitation_mm": 8,
            "sunshine_hours": 11, "sea_temp_c": 23,
            "summary": "Hot and sunny. Sea warm enough for swimming.",
        },
        "july": {
            "avg_temp_c": 33, "avg_temp_f": 91, "precipitation_mm": 5,
            "sunshine_hours": 12, "sea_temp_c": 26,
            "summary": (
                "Hot and dry, perfect for beaches. Minimal rain."
                " Meltemi winds possible on islands."
            ),
        },
        "august": {
            "avg_temp_c": 33, "avg_temp_f": 91, "precipitation_mm": 6,
            "sunshine_hours": 11, "sea_temp_c": 27,
            "summary": "Peak summer. Very hot, very sunny, crowded. Best sea temperatures.",
        },
        "september": {
            "avg_temp_c": 28, "avg_temp_f": 82, "precipitation_mm": 15,
            "sunshine_hours": 9, "sea_temp_c": 25,
            "summary": "Warm, less crowded. Excellent for swimming and hiking.",
        },
        "october": {
            "avg_temp_c": 22, "avg_temp_f": 72, "precipitation_mm": 35,
            "sunshine_hours": 7, "sea_temp_c": 22,
            "summary": "Pleasant autumn. Some rain possible.",
        },
        "november": {
            "avg_temp_c": 17, "avg_temp_f": 63, "precipitation_mm": 55,
            "sunshine_hours": 5, "sea_temp_c": 19,
            "summary": "Cooler with more rain. Off-peak season.",
        },
        "december": {
            "avg_temp_c": 14, "avg_temp_f": 57, "precipitation_mm": 60,
            "sunshine_hours": 4, "sea_temp_c": 17,
            "summary": "Cool and rainy. Christmas atmosphere in cities.",
        },
    },
    "default": {
        "july": {
            "avg_temp_c": 25, "avg_temp_f": 77, "precipitation_mm": 30,
            "sunshine_hours": 8,
            "summary": "Warm summer weather expected.",
        },
    },
}


class WeatherAgent(BaseAgent):
    name = "weather_agent"
    description = "Retrieves historical climate data and forecasts for trip dates"

    async def _execute(self, state: dict) -> dict:
        intent = state.get("intent", {})
        if not intent:
            return self._error_state("No intent in state")

        destination = intent.get("destination", "")
        travel_month = (intent.get("travel_month") or "July").lower()

        mode = self._inventory_mode()
        query_id = inventory.inventory_query_id(
            "openweather", destination=destination, month=travel_month
        )
        api_key = os.getenv("OPENWEATHER_API_KEY", "")

        if mode == "replay":
            weather = inventory.replay("openweather", query_id)
        elif mode == "capture":
            if api_key:
                weather = await self._fetch_forecast(destination, api_key)
            else:
                weather = self._historical_climate(destination, travel_month)
            inventory.capture("openweather", weather, query_id, run_label="weather-capture")
        elif mode == "mock":
            # Mock mode is fully offline even when API keys are set: the
            # deterministic fixture is the whole point (CI, unit tests, demos).
            weather = self._historical_climate(destination, travel_month)
        elif api_key:
            weather = await self._fetch_forecast(destination, api_key)
        else:
            weather = self._historical_climate(destination, travel_month)

        return {"weather": weather, "travel_month": travel_month}

    def _inventory_mode(self) -> str:
        from config.settings import get_settings
        return get_settings().inventory_mode

    async def _fetch_forecast(self, destination: str, api_key: str) -> dict:
        async with httpx.AsyncClient() as client:
            try:
                geo_resp = await client.get(
                    "http://api.openweathermap.org/geo/1.0/direct",
                    params={"q": destination, "limit": 1, "appid": api_key},
                )
                geo = geo_resp.json()
                # TODO: pass travel_month through these live-path fallbacks so
                # they match the mock path instead of hardcoding July.
                if not isinstance(geo, list) or not geo:
                    return self._historical_climate(destination, "july")
                lat, lon = geo[0]["lat"], geo[0]["lon"]

                weather_resp = await client.get(
                    "https://api.openweathermap.org/data/3.0/onecall",
                    params={
                        "lat": lat,
                        "lon": lon,
                        "exclude": "minutely,hourly,alerts",
                        "units": "metric",
                        "appid": api_key,
                    },
                )
                data = weather_resp.json()
                daily = data.get("daily") or []
                if not daily:
                    return self._historical_climate(destination, "july")
                avg_temp = sum(d["temp"]["day"] for d in daily[:7]) / max(len(daily[:7]), 1)
                return {
                    "avg_temp_c": round(avg_temp, 1),
                    "avg_temp_f": round(avg_temp * 9 / 5 + 32, 1),
                    "summary": daily[0].get("summary", ""),
                    "source": "openweather_current_8day",   # live 8-day forecast
                }
            except Exception:
                return self._historical_climate(destination, "july")

    def _historical_climate(self, destination: str, month: str) -> dict:
        dest_key = destination.lower().split(",")[0].strip()
        for key, months in CLIMATE_FALLBACK.items():
            if key in dest_key or dest_key in key:
                return {**months.get(month, months.get("july", {})), "source": "historical_average"}
        default = CLIMATE_FALLBACK["default"].get(month, {})
        return {**default, "source": "historical_average"}
