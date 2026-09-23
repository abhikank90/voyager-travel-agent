import logging
import time
from abc import ABC, abstractmethod
from datetime import date

from langsmith import traceable

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all Voyager travel agents."""

    name: str = "base_agent"
    description: str = ""

    def __init__(self, config: dict | None = None):
        self.config = config or {}
        self._setup()

    def _setup(self):
        """Override to add agent-specific setup."""
        pass

    @traceable(name="agent_run")
    async def run(self, state: dict) -> dict:
        start = time.perf_counter()
        try:
            result = await self._execute(state)
            logger.info(
                "agent=%s status=ok duration=%.2fs",
                self.name,
                time.perf_counter() - start,
            )
            return result
        except Exception as exc:
            logger.error("agent=%s error=%s", self.name, exc, exc_info=True)
            raise

    @abstractmethod
    async def _execute(self, state: dict) -> dict:
        """Core agent logic — must return a dict of state updates."""
        ...

    def _messages_for_me(self, state: dict) -> list[dict]:
        """Return collaboration messages targeting this agent from prior rounds.

        Matches both the full agent name and the short hub-convention name
        (e.g. "hotel_agent" and "hotel") so research agents can read what
        the CollaborationHub addressed to them without knowing hub internals.
        """
        current_round = state.get("collaboration_round", 1)
        my_ids = {self.name}
        short = getattr(self, "short_name", None)
        if short:
            my_ids.add(short)
        # round < current_round intentionally includes messages from all prior
        # rounds (not just round - 1). Constraints are idempotent — applying
        # the same location hint or timing preference twice changes nothing —
        # so accumulating them is harmless and avoids needing per-round bookkeeping.
        return [
            m for m in state.get("agent_messages", [])
            if m.get("to_agent") in my_ids | {"all"}
            and m.get("round", 0) < current_round
        ]

    def _error_state(self, message: str) -> dict:
        return {"errors": {self.name: message}}

    def _effective_dates(self, travel_year: int, duration_days: int = 13) -> tuple[str, str]:
        """Date window used for inventory queries, per inventory mode.

        - capture: today + 90d / +duration_days (the API is consulted ~3 months out).
        - replay:  derived from the fixtures' capture date (manifest.json), NOT the
                   calendar — so replaying today, next week, or next month recomputes
                   the SAME query ids and finds the SAME fixtures, reproducing the
                   live dataset exactly.
        - mock:    static intent-derived dates for benchmark comparability.
        """
        from datetime import timedelta
        mode = self._inventory_mode()
        if mode == "capture":
            start = date.today() + timedelta(days=90)
        elif mode == "replay":
            start = self._get_fixture_capture_date() + timedelta(days=90)
        else:
            return f"{travel_year}-07-01", f"{travel_year}-07-14"
        return start.isoformat(), (start + timedelta(days=duration_days)).isoformat()

    def _get_fixture_capture_date(self) -> date:
        """Capture date (local) anchored on the replay manifest's first fixture.

        Replay anchors its query window to when the fixtures were captured rather
        than to `today`, so reruns across days stay identical (date-stable replay).
        The manifest is keyed in insertion order, so its first entry is the
        reference capture run; we take that fixture's local capture date so the
        derived +90d window reproduces the exact query ids used at capture time.
        Falls back to today if the manifest is empty.
        """
        from datetime import datetime

        from agents.inventory import load_manifest
        manifest = load_manifest()
        fixtures = manifest.get("fixtures") or {}
        for meta in fixtures.values():
            ts = meta.get("captured_at")
            if ts:
                try:
                    return datetime.fromisoformat(ts).astimezone().date()
                except (TypeError, ValueError):
                    continue
        return date.today()
