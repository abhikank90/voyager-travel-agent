import json
import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from graph.travel_graph import (
    collaborative_travel_graph,
    run_collaborative_travel_query,
    run_travel_query,
    travel_graph,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ────────────────────────────────────────────
# Security Configuration
# ────────────────────────────────────────────

# Rate Limiter
limiter = Limiter(key_func=get_remote_address, default_limits=["100/hour"])

# API Key Authentication
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Load API key from environment (set in .env)
VOYAGER_API_KEY = os.getenv("VOYAGER_API_KEY")

async def verify_api_key(api_key: str = Depends(api_key_header)):
    """
    Verify API key for protected endpoints.
    If VOYAGER_API_KEY is not set in .env, authentication is disabled (development mode).
    """
    # Development mode - no API key required
    if not VOYAGER_API_KEY:
        logger.warning("⚠️  VOYAGER_API_KEY not set - API authentication DISABLED (dev mode)")
        return True

    # Production mode - API key required
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Include 'X-API-Key' header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if api_key != VOYAGER_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    if VOYAGER_API_KEY:
        logger.info("🔒 Voyager Travel Agent API starting up (AUTH ENABLED)")
    else:
        logger.warning("⚠️  Voyager Travel Agent API starting up (AUTH DISABLED - dev mode)")
    yield
    logger.info("Voyager Travel Agent API shutting down")


app = FastAPI(
    title="Voyager Travel Agent API",
    description="Multi-agent AI travel planning powered by LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Configuration - Restrict to specific origins
# Override with ALLOWED_ORIGINS environment variable for production
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # ✅ Restricted to specific origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # ✅ Only necessary methods
    allow_headers=["Content-Type", "X-API-Key"],  # ✅ Only necessary headers
)


class TravelRequest(BaseModel):
    query: str
    user_id: str = "anonymous"


class TravelResponse(BaseModel):
    session_id: str
    status: str
    itinerary: dict | None = None
    budget_breakdown: dict | None = None
    errors: dict | None = None


class CollaborativeTravelRequest(BaseModel):
    query: str
    user_id: str = "anonymous"
    session_id: str | None = None


class CollaborativeTravelResponse(BaseModel):
    session_id: str
    status: str
    trip_options: list[dict] = []
    collaboration_messages: list[dict] = []
    conflicts: list[dict] = []
    synergies: list[dict] = []
    errors: dict | None = None


class OptionSelectionRequest(BaseModel):
    session_id: str
    option_id: int  # 0, 1, or 2
    user_id: str = "anonymous"


class RefinementRequest(BaseModel):
    session_id: str
    refinement_query: str  # e.g., "use hotel from option 3"
    selected_option_id: int  # Which option to start from
    user_id: str = "anonymous"


@app.get("/health")
async def health():
    return {"status": "ok", "service": "voyager-travel-agent"}


@app.post("/api/travel/plan", response_model=TravelResponse)
@limiter.limit("10/minute")  # ✅ Rate limit: 10 requests per minute
async def plan_trip(
    request: Request,
    travel_request: TravelRequest,
    authenticated: bool = Depends(verify_api_key)
):
    """Legacy endpoint - generates single itinerary. (Protected)"""
    session_id = str(uuid.uuid4())
    try:
        final_state = await run_travel_query(travel_request.query, travel_request.user_id)
        return TravelResponse(
            session_id=session_id,
            status=final_state.get("status", "complete"),
            itinerary=final_state.get("itinerary"),
            budget_breakdown=final_state.get("budget_breakdown"),
            errors=final_state.get("errors"),
        )
    except Exception as e:
        logger.error("plan_trip error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/travel/collaborative", response_model=CollaborativeTravelResponse)
@limiter.limit("10/minute")  # ✅ Rate limit: 10 requests per minute
async def plan_collaborative_trip(
    request: Request,
    travel_request: CollaborativeTravelRequest,
    authenticated: bool = Depends(verify_api_key)
):
    """New collaborative endpoint - generates 3 trip options. (Protected)"""
    session_id = travel_request.session_id or str(uuid.uuid4())
    try:
        final_state = await run_collaborative_travel_query(
            travel_request.query,
            travel_request.user_id,
            session_id,
            record_metrics=False,
        )
        return CollaborativeTravelResponse(
            session_id=session_id,
            status=final_state.get("status", "complete"),
            trip_options=final_state.get("trip_options", []),
            collaboration_messages=final_state.get("agent_messages", []),
            conflicts=final_state.get("conflicts", []),
            synergies=final_state.get("synergies", []),
            errors=final_state.get("errors"),
        )
    except Exception as e:
        logger.error("plan_collaborative_trip error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


# In-memory session storage (use Redis in production)
_session_store: dict[str, dict] = {}


@app.post("/api/travel/select-option")
@limiter.limit("30/minute")  # ✅ Rate limit: 30 requests per minute (lighter operation)
async def select_option(
    request: Request,
    selection_request: OptionSelectionRequest,
    authenticated: bool = Depends(verify_api_key)
):
    """User selects one of the 3 options. (Protected)"""
    if selection_request.session_id not in _session_store:
        raise HTTPException(status_code=404, detail="Session not found")

    session_data = _session_store[selection_request.session_id]
    trip_options = session_data.get("trip_options", [])

    if selection_request.option_id < 0 or selection_request.option_id >= len(trip_options):
        raise HTTPException(status_code=400, detail="Invalid option_id")

    selected_option = trip_options[selection_request.option_id]

    # Update session
    _session_store[selection_request.session_id]["selected_option_id"] = selection_request.option_id

    return {
        "session_id": selection_request.session_id,
        "selected_option": selected_option,
        "message": f"Selected option {selection_request.option_id}: {selected_option.get('title')}"
    }


@app.post("/api/travel/refine")
@limiter.limit("20/minute")  # ✅ Rate limit: 20 requests per minute
async def refine_option(
    request: Request,
    refinement_request: RefinementRequest,
    authenticated: bool = Depends(verify_api_key)
):
    """Refine a selected option based on user feedback. (Protected)"""
    # This would use an additional LLM call to parse the refinement request
    # and modify the selected option accordingly

    if refinement_request.session_id not in _session_store:
        raise HTTPException(status_code=404, detail="Session not found")

    session_data = _session_store[refinement_request.session_id]
    trip_options = session_data.get("trip_options", [])

    if refinement_request.selected_option_id < 0 or refinement_request.selected_option_id >= len(trip_options):
        raise HTTPException(status_code=400, detail="Invalid selected_option_id")

    base_option = trip_options[refinement_request.selected_option_id]

    # TODO: Implement refinement logic using Claude to parse the request
    # For now, return a placeholder
    refined_option = base_option.copy()
    refined_option["title"] = f"{base_option['title']} (Refined)"
    refined_option["description"] = f"Refined based on: {refinement_request.refinement_query}"

    # Store refinement in history
    if "refinement_history" not in _session_store[refinement_request.session_id]:
        _session_store[refinement_request.session_id]["refinement_history"] = []

    _session_store[refinement_request.session_id]["refinement_history"].append({
        "base_option_id": refinement_request.selected_option_id,
        "query": refinement_request.refinement_query,
        "timestamp": str(uuid.uuid4())  # Would be datetime in production
    })

    return {
        "session_id": refinement_request.session_id,
        "refined_option": refined_option,
        "refinement_count": len(_session_store[refinement_request.session_id]["refinement_history"])
    }


@app.websocket("/ws/travel/{session_id}")
async def travel_websocket(websocket: WebSocket, session_id: str, token: str = None):
    """
    WebSocket endpoint for streaming agent progress events to the frontend.
    Each agent emits a JSON event as it completes.
    Authentication: Pass API key as 'token' query parameter (e.g., ws://...?token=your-key)
    """
    # Verify API key (if required)
    if VOYAGER_API_KEY:
        if not token or token != VOYAGER_API_KEY:
            await websocket.close(code=1008, reason="Invalid or missing API key")
            logger.warning("WS session %s rejected - invalid API key", session_id)
            return

    await websocket.accept()
    logger.info("WS session %s connected", session_id)

    try:
        data = await websocket.receive_text()
        payload = json.loads(data)
        query = payload.get("query", "")
        user_id = payload.get("user_id", "anonymous")

        if not query:
            await websocket.send_json({"type": "error", "message": "No query provided"})
            return

        await websocket.send_json({"type": "status", "agent": "system", "message": "Starting travel planning..."})

        # Stream node-by-node updates
        initial_state = {
            "user_query": query,
            "user_id": user_id,
            "budget_retry_count": 0,
            "errors": {},
        }

        NODE_LABELS = {
            "personalisation": "Loading your travel profile...",
            "intent_parser": "Understanding your travel needs...",
            "research_fan_out": "Researching flights, hotels, experiences, weather, and visa info...",
            "research_round_1": "Round 1: Researching flights, hotels, experiences, weather, and visa info...",
            "collaboration_hub_1": "Analyzing findings and identifying opportunities...",
            "research_round_2": "Round 2: Refining recommendations based on insights...",
            "collaboration_hub_2": "Final coordination check...",
            "research_round_3": "Round 3: Final optimizations...",
            "budget_guardrail": "Validating budget constraints...",
            "retry_research": "Adjusting for budget constraints...",
            "itinerary_builder": "Building your perfect itinerary...",
            "option_generator": "Creating 3 personalized trip options for you...",
        }

        final_state = None
        async for event in travel_graph.astream(initial_state, stream_mode="updates"):
            for node_name, node_output in event.items():
                label = NODE_LABELS.get(node_name, node_name)
                await websocket.send_json({
                    "type": "agent_update",
                    "agent": node_name,
                    "message": label,
                    "data": _safe_serialize(node_output),
                })
                final_state = node_output

        await websocket.send_json({
            "type": "complete",
            "message": "Your trip is planned!",
            "data": _safe_serialize(final_state or {}),
        })

    except WebSocketDisconnect:
        logger.info("WS session %s disconnected", session_id)
    except Exception as e:
        logger.error("WS error session=%s: %s", session_id, e, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


@app.websocket("/ws/travel/collaborative/{session_id}")
async def collaborative_travel_websocket(websocket: WebSocket, session_id: str, token: str = None):
    """
    WebSocket endpoint for collaborative multi-agent planning.
    Streams real-time updates including agent collaboration messages.
    Authentication: Pass API key as 'token' query parameter (e.g., ws://...?token=your-key)
    """
    # Verify API key (if required)
    if VOYAGER_API_KEY:
        if not token or token != VOYAGER_API_KEY:
            await websocket.close(code=1008, reason="Invalid or missing API key")
            logger.warning("Collaborative WS session %s rejected - invalid API key", session_id)
            return

    await websocket.accept()
    logger.info("Collaborative WS session %s connected", session_id)

    try:
        data = await websocket.receive_text()
        payload = json.loads(data)
        query = payload.get("query", "")
        user_id = payload.get("user_id", "anonymous")

        if not query:
            await websocket.send_json({"type": "error", "message": "No query provided"})
            return

        await websocket.send_json({
            "type": "status",
            "agent": "system",
            "message": "Starting collaborative travel planning..."
        })

        # Stream node-by-node updates
        initial_state = {
            "user_query": query,
            "user_id": user_id,
            "session_id": session_id,
            "collaboration_round": 0,
            "budget_retry_count": 0,
            "agent_messages": [],
            "conflicts": [],
            "synergies": [],
            "errors": {},
            "refinement_history": [],
        }

        NODE_LABELS = {
            "personalisation": "Loading your travel profile...",
            "intent_parser": "Understanding your travel needs...",
            "research_round_1": "Round 1: All agents researching in parallel...",
            "collaboration_hub_1": "🤝 Agents collaborating and sharing insights...",
            "research_round_2": "Round 2: Refining based on team feedback...",
            "collaboration_hub_2": "🤝 Final team coordination...",
            "research_round_3": "Round 3: Final optimizations...",
            "budget_guardrail": "✓ Validating budget...",
            "option_generator": "🎯 Creating 3 personalized options for you...",
        }

        final_state = None
        async for event in collaborative_travel_graph.astream(initial_state, stream_mode="updates"):
            for node_name, node_output in event.items():
                label = NODE_LABELS.get(node_name, node_name)

                # Special handling for collaboration messages
                if node_name == "collaboration_hub_1" or node_name == "collaboration_hub_2":
                    messages = node_output.get("agent_messages", [])
                    if messages:
                        await websocket.send_json({
                            "type": "collaboration",
                            "agent": node_name,
                            "message": "Agents are discussing...",
                            "collaboration_messages": _safe_serialize(messages),
                        })

                await websocket.send_json({
                    "type": "agent_update",
                    "agent": node_name,
                    "message": label,
                    "data": _safe_serialize(node_output),
                })
                final_state = node_output

        # Store session data for option selection and refinement
        if final_state:
            _session_store[session_id] = final_state

        trip_options = final_state.get("trip_options", []) if final_state else []

        await websocket.send_json({
            "type": "options_ready",
            "message": f"🎉 {len(trip_options)} trip options ready for you!",
            "trip_options": _safe_serialize(trip_options),
            "session_id": session_id,
        })

    except WebSocketDisconnect:
        logger.info("Collaborative WS session %s disconnected", session_id)
    except Exception as e:
        logger.error("Collaborative WS error session=%s: %s", session_id, e, exc_info=True)
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass


def _safe_serialize(obj):
    try:
        return json.loads(json.dumps(obj, default=str))
    except Exception:
        return {}


# Serve built frontend in production
FRONTEND_BUILD = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(FRONTEND_BUILD):
    app.mount("/", StaticFiles(directory=FRONTEND_BUILD, html=True), name="frontend")
