import os
import httpx

from .base_agent import BaseAgent


CLIMATE_FALLBACK = {
    "greece": {
        "july": {"avg_temp_c": 33, "avg_temp_f": 91, "precipitation_mm": 5, "sunshine_hours": 12, "sea_temp_c": 26, "summary": "Hot and dry, perfect for beaches. Minimal rain. Meltemi winds possible on islands."},
        "august": {"avg_temp_c": 33, "avg_temp_f": 91, "precipitation_mm": 6, "sunshine_hours": 11, "sea_temp_c": 27, "summary": "Peak summer. Very hot, very sunny, crowded. Best sea temperatures."},
    },
    "default": {
        "july": {"avg_temp_c": 25, "avg_temp_f": 77, "precipitation_mm": 30, "sunshine_hours": 8, "summary": "Warm summer weather expected."},
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
        travel_year = intent.get("travel_year", 2026)

        api_key = os.getenv("OPENWEATHER_API_KEY", "")
        if api_key:
            weather = await self._fetch_forecast(destination, api_key)
        else:
            weather = self._historical_climate(destination, travel_month)

        return {"weather": weather, "travel_month": travel_month}

    async def _fetch_forecast(self, destination: str, api_key: str) -> dict:
        async with httpx.AsyncClient() as client:
            try:
                geo_resp = await client.get(
                    "http://api.openweathermap.org/geo/1.0/direct",
                    params={"q": destination, "limit": 1, "appid": api_key},
                )
                geo = geo_resp.json()
                if not geo:
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
                daily = data.get("daily", [])
                avg_temp = sum(d["temp"]["day"] for d in daily[:7]) / max(len(daily[:7]), 1)
                return {
                    "avg_temp_c": round(avg_temp, 1),
                    "avg_temp_f": round(avg_temp * 9 / 5 + 32, 1),
                    "summary": data.get("daily", [{}])[0].get("summary", ""),
                    "source": "openweather",
                }
            except Exception as e:
                return self._historical_climate(destination, "july")

    def _historical_climate(self, destination: str, month: str) -> dict:
        dest_key = destination.lower().split(",")[0].strip()
        for key, months in CLIMATE_FALLBACK.items():
            if key in dest_key or dest_key in key:
                return {**months.get(month, months.get("july", {})), "source": "historical_average"}
        default = CLIMATE_FALLBACK["default"].get(month, {})
        return {**default, "source": "historical_average"}
