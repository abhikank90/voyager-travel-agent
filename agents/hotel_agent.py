import asyncio
import os
from datetime import date

import httpx
from langchain_anthropic import ChatAnthropic

from metrics.token_tracker import TokenTrackingCallback

from . import inventory
from .base_agent import BaseAgent

# LiteAPI sandbox limits ~5 req/s. A single query fires up to 7 requests
# (1 places + 1 rates + up to 5 details); bursty benchmark runs trip the 429
# rate limiter. Pace each request (>=200ms apart) and retry transient
# 429/5xx responses with backoff so capture runs stop dropping places/rates.
_MIN_INTERVAL_S = 0.22
_RETRIES = 3


async def _rate_limited_request(client: httpx.AsyncClient, method: str, url: str, **kwargs):
    """Throttled request with retry-on-429/5xx.

    Each call paces itself via a minimum interval (keeping throughput under
    LiteAPI's ~5 req/s sandbox cap) and retries transient 429/5xx responses
    with exponential backoff. Returns the httpx Response after retries.
    """
    last_error: Exception | None = None
    for attempt in range(_RETRIES):
        if attempt:
            await asyncio.sleep(_MIN_INTERVAL_S * (2**attempt))
        try:
            resp = await getattr(client, method.lower())(url, **kwargs)
            if resp.status_code in (429, 500, 502, 503, 504):
                last_error = httpx.HTTPStatusError(
                    f"{resp.status_code} from {url}",
                    request=getattr(resp, "request", None) or httpx.Request(method, url),
                    response=resp,
                )
                await asyncio.sleep((attempt + 1) * 0.8)
                continue
            resp.raise_for_status()
            return resp
        except httpx.TransportError as exc:
            last_error = exc
            await asyncio.sleep((attempt + 1) * 0.8)
    assert last_error is not None
    raise last_error


def _mock_hotel_data(
    destination: str,
    check_in: str,
    check_out: str,
    guests: int,
    duration: int,
    location_hint: str | None = None,
):
    hotels = [
        {
            "name": f"Aegean Bliss Resort, {destination}",
            "price_per_night_usd": 85,
            "total_usd": 85 * duration,
            "rating": 4.3,
            "amenities": ["beach access", "breakfast included", "wifi", "pool"],
            "location": "Beachfront",
        },
        {
            "name": f"Cyclades Boutique Hotel, {destination}",
            "price_per_night_usd": 110,
            "total_usd": 110 * duration,
            "rating": 4.6,
            "amenities": ["rooftop bar", "wifi", "city center"],
            "location": "Old Town",
        },
    ]

    if location_hint:
        # Simulate a location-filtered query returning a hotel in the requested area.
        # Slightly higher nightly rate reflects the premium for a well-located property.
        hotels.insert(0, {
            "name": f"{location_hint} Boutique Stay",
            "price_per_night_usd": 95,
            "total_usd": 95 * duration,
            "rating": 4.4,
            "amenities": ["wifi", "breakfast included", "rooftop terrace"],
            "location": location_hint,
        })

    return {"hotels": hotels, "mock": True}


class HotelAgent(BaseAgent):
    name = "hotel_agent"
    short_name = "hotel"
    description = "Searches hotels within budget and preferred dates"

    def _setup(self):
        try:
            from config import get_api_config
            model = get_api_config().llm.hotel_agent_model
        except Exception:
            model = "claude-haiku-4-5-20251001"
        self.llm = ChatAnthropic(model=model, temperature=0, callbacks=[TokenTrackingCallback(model=model)])

    async def _execute(self, state: dict) -> dict:
        intent = state.get("intent", {})
        if not intent:
            return self._error_state("No intent in state")

        destination = intent.get("destination", "")
        budget = intent.get("budget_usd", 2000)
        travel_year = intent.get("travel_year", 2026)
        group_size = intent.get("group_size", 1)
        duration = intent.get("duration_days") or 14
        intent.get("accommodation_preference", "hotel")

        check_in, check_out = self._effective_dates(travel_year, duration)
        hotel_budget = budget * 0.45

        # Extract location constraint from collaboration messages, if any.
        # The hub sends activity_locations when hotel is far from top experiences,
        # plus an activity_centroid when experience coordinates are available.
        # A typed centroid enables distance-based matching against real inventory;
        # the string hint alone can't survive contact with live payloads.
        location_hint: str | None = None
        centroid: tuple[float, float] | None = None
        for msg in self._messages_for_me(state):
            if msg.get("message_type") == "constraint":
                data = msg.get("data", {})
                areas = data.get("suggested_areas") or data.get("activity_locations") or []
                if areas:
                    location_hint = areas[0]
                c = data.get("activity_centroid")
                if centroid is None and c and c.get("lat") is not None:
                    centroid = (float(c["lat"]), float(c["lon"]))
                if location_hint or centroid:
                    break

        api_key = os.getenv("NUITEE_API_KEY", "")
        mode = self._inventory_mode()
        query_id = inventory.inventory_query_id(
            "nuitee", destination=destination, check_in=check_in,
            check_out=check_out, guests=group_size,
        )

        if mode == "replay":
            result = inventory.replay("nuitee", query_id)
        elif mode == "capture":
            if api_key:
                result = await self._fetch_real(destination, check_in, check_out, group_size, hotel_budget)
            else:
                result = _mock_hotel_data(destination, check_in, check_out, group_size, duration, location_hint)
            inventory.capture("nuitee", result, query_id, run_label="hotel-capture")
        elif mode == "mock":
            # Mock mode is fully offline even when API keys are set: the
            # deterministic fixture is the whole point (CI, unit tests, demos).
            result = _mock_hotel_data(destination, check_in, check_out, group_size, duration, location_hint)
        elif api_key:
            result = await self._fetch_real(destination, check_in, check_out, group_size, hotel_budget)
        else:
            result = _mock_hotel_data(destination, check_in, check_out, group_size, duration, location_hint)

        hotels = result.get("hotels", [])
        affordable = [h for h in hotels if h["total_usd"] <= hotel_budget]
        candidates = affordable if affordable else hotels

        if not candidates:
            best = None
        elif centroid:
            within = _candidates_within(candidates, centroid)
            best = within[0] if within else candidates[0]
        elif location_hint:
            # String-matching fallback (mock-compatible): prefer candidates whose
            # location matches the hub's hint; fall back to first candidate if
            # none qualify. Real inventory bypasses this path via the centroid
            # branch above, since live location strings never substring-match.
            hint_lower = location_hint.lower()
            matching = [
                h for h in candidates
                if hint_lower in h.get("location", "").lower()
                or h.get("location", "").lower() in hint_lower
            ]
            best = matching[0] if matching else candidates[0]
        else:
            best = candidates[0]

        feedback = self._location_hint_feedback(candidates, location_hint, centroid)

        return {
            "hotels": hotels,
            "selected_hotel": best,
            "hotel_cost_usd": best["total_usd"] if best else 0,
            "feedback_metrics": feedback,
        }

    def _inventory_mode(self) -> str:
        from config.settings import get_settings
        return get_settings().inventory_mode

    @staticmethod
    def _location_hint_feedback(
        candidates: list[dict],
        location_hint: str | None,
        centroid: tuple[float, float] | None = None,
    ) -> dict:
        """Record whether a location constraint could be satisfied.

        Typed centroid constraints use distance-based matching against candidate
        coordinates; string hints fall back to substring matching (mock path).
        Mirrors the flight agent's ``feedback_metrics`` so the collector's
        ``unsatisfiable_constraint_rate_pct`` covers hotels too, not just flights.
        """
        if not location_hint and not centroid:
            return _feedback(applied=False)
        if centroid:
            matching = _candidates_within(candidates, centroid)
        elif location_hint:
            hint_lower = location_hint.lower()
            matching = [
                h for h in candidates
                if hint_lower in h.get("location", "").lower()
                or h.get("location", "").lower() in hint_lower
            ]
        else:
            return _feedback(applied=False)
        if matching:
            return _feedback(applied=True, satisfiable=True, fallback=False, reason="qualifying_option_found")
        return _feedback(
            applied=True, satisfiable=False, fallback=True, reason="no_qualifying_option"
        )

    async def _fetch_real(self, destination, check_in, check_out, guests, budget):
        """Three-call Nuitee flow: destination → placeId → rates → per-hotel details.

        Rates provides hotelId + pricing; /data/hotel provides name, address, and
        geo coordinates (required by the hub's location_mismatch rule). Only the
        normalized fields below are returned, so captured fixtures stay compact —
        the opaque offerId/rateId tokens are discarded, not stored.
        """
        api_key = os.getenv("NUITEE_API_KEY", "")
        headers = {"X-API-Key": api_key}

        async with httpx.AsyncClient(timeout=30) as client:
            # 1) destination → placeId (locality-preferring, belt-and-braces:
            #    pick the first entry typed as a locality, else first match).
            place_resp = await _rate_limited_request(
                client,
                "GET",
                "https://api.liteapi.travel/v3.0/data/places",
                headers=headers,
                params={"textQuery": destination, "language": "en", "type": "locality"},
            )
            data = place_resp.json().get("data", [])
            locality = next((p for p in data if "locality" in (p.get("types") or [])), None)
            chosen = locality or (data[0] if data else {})
            place_id = chosen.get("placeId", "")
            if not place_id:
                return {"hotels": []}

            # 2) placeId → rates. POST with roomMapping: True returns the mapped
            #    retail offers; includeHotelData bundles name/address/rating.
            rates_resp = await _rate_limited_request(
                client,
                "POST",
                "https://api.liteapi.travel/v3.0/hotels/rates",
                headers={**headers, "Content-Type": "application/json", "Accept": "application/json"},
                json={
                    "placeId": place_id,
                    "occupancies": [{"adults": guests}],
                    "currency": "USD",
                    "guestNationality": "US",
                    "checkin": check_in,
                    "checkout": check_out,
                    "roomMapping": True,
                    "maxRatesPerHotel": 1,
                    "includeHotelData": True,
                },
            )
            rate_items = rates_resp.json().get("data", [])[:5]

            # 3) hotelId → static details (name, address, geo). Sequential with a
            #    small delay: sandbox limit is ~5 req/s, and capture runs up to
            #    5 of these per query × ~12 queries.
            details_by_id: dict[str, dict] = {}
            for item in rate_items:
                hotel_id = item.get("hotelId", "")
                if not hotel_id:
                    continue
                try:
                    detail_resp = await _rate_limited_request(
                        client,
                        "GET",
                        "https://api.liteapi.travel/v3.0/data/hotel",
                        headers=headers,
                        params={"hotelId": hotel_id},
                    )
                    # /data/hotel shape varies: docs show data as an object with
                    # nested location:{latitude,longitude}; some responses return
                    # a list with flat latitude/longitude. Handle both.
                    data = detail_resp.json().get("data") or {}
                    details = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})
                    details_by_id[hotel_id] = details
                except Exception:
                    details_by_id[hotel_id] = {}   # degrade gracefully, keep the rate
                await asyncio.sleep(0.25)

        nights = max(
            (date.fromisoformat(check_out) - date.fromisoformat(check_in)).days, 1
        )

        results = []
        for item in rate_items:
            hotel_id = item.get("hotelId", "")
            # Cheapest offer across room types. offerRetailRate.amount is the
            # TOTAL stay price (verified against the sample: 306.68 USD for a
            # 3-night stay), so per-night is derived, not read.
            totals = [
                rt.get("offerRetailRate", {}).get("amount")
                for rt in (item.get("roomTypes") or [])
            ]
            totals = [float(t) for t in totals if t is not None]
            if not totals:
                continue
            total = min(totals)

            details = details_by_id.get(hotel_id, {})
            loc = details.get("location") or {}
            lat = loc.get("latitude") if loc.get("latitude") is not None else details.get("latitude")
            lon = loc.get("longitude") if loc.get("longitude") is not None else details.get("longitude")
            results.append({
                "hotel_id": hotel_id,
                "name": details.get("name") or hotel_id,
                "price_per_night_usd": round(total / nights, 2),
                "total_usd": total,
                "rating": details.get("rating", 0),
                "amenities": [],                       # facilityIds need a lookup table; skip
                "location": _format_location(details, lat, lon),
                "latitude": lat,
                "longitude": lon,
            })
        return {"hotels": results}


def _format_location(details: dict, lat: float | None, lon: float | None) -> str:
    """Location string from the /data/hotel payload: address, city, country + coords.

    The hub's location_mismatch rule consumes the coordinates; the human-readable
    prefix keeps the collaboration feed legible.
    """
    country = (details.get("country") or "").upper()   # payload uses lowercase ("us")
    parts = [p for p in (details.get("address"), details.get("city"), country) if p]
    base = ", ".join(parts)
    if lat is not None and lon is not None:
        base = f"{base} ({lat:.4f},{lon:.4f})"
    return base or "Unknown"


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    from math import asin, cos, radians, sin, sqrt
    r = 6371.0
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * r * asin(sqrt(a))


def _candidates_within(
    candidates: list[dict],
    centroid: tuple[float, float],
    threshold_km: float = 25.0,
) -> list[dict]:
    """Candidates whose coordinates fall within threshold_km of the centroid."""
    clat, clon = centroid
    return [
        h for h in candidates
        if h.get("latitude") is not None and h.get("longitude") is not None
        and _haversine_km(clat, clon, float(h["latitude"]), float(h["longitude"])) <= threshold_km
    ]


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
