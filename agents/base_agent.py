from abc import ABC, abstractmethod
from typing import Any, Optional
import logging
import time

from langsmith import traceable

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Base class for all Voyager travel agents."""

    name: str = "base_agent"
    description: str = ""

    def __init__(self, config: Optional[dict] = None):
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
        return [
            m for m in state.get("agent_messages", [])
            if m.get("to_agent") in my_ids | {"all"}
            and m.get("round", 0) < current_round
        ]

    def _error_state(self, message: str) -> dict:
        return {"errors": {self.name: message}}
