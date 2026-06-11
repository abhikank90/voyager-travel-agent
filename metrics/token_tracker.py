"""
Per-session LLM token accumulator using contextvars.

Safe for async/single-process use: each call to start_session() creates a fresh
TokenUsage object bound to the current async context. Agents call track_usage()
after every Anthropic API call. The parent coroutine reads get_current() at the end.

Two integration points:
  - Raw Anthropic SDK (CollaborationHub, OptionGenerator):
        from metrics.token_tracker import track_usage
        response = self.client.messages.create(...)
        track_usage(response.usage.input_tokens, response.usage.output_tokens)

  - LangChain ChatAnthropic (IntentParser, ExperienceAgent):
        from metrics.token_tracker import TokenTrackingCallback
        self.llm = ChatAnthropic(..., callbacks=[TokenTrackingCallback()])
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


_current: ContextVar[TokenUsage | None] = ContextVar("session_token_usage", default=None)


def start_session() -> TokenUsage:
    """Reset the accumulator for a new session. Call once per run."""
    usage = TokenUsage()
    _current.set(usage)
    return usage


def track_usage(input_tokens: int, output_tokens: int) -> None:
    """Add tokens from one raw Anthropic API call to the running total."""
    usage = _current.get()
    if usage is not None:
        usage.input_tokens += input_tokens
        usage.output_tokens += output_tokens


def get_current() -> TokenUsage | None:
    """Return the current session's accumulator (None if no session started)."""
    return _current.get()


def compute_cost(input_tokens: int, output_tokens: int, pricing) -> float:
    """Return estimated USD cost given token counts and an LLMConfig pricing object."""
    return round(
        input_tokens / 1_000_000 * pricing.input_cost_per_mtok
        + output_tokens / 1_000_000 * pricing.output_cost_per_mtok,
        6,
    )


class TokenTrackingCallback(BaseCallbackHandler):
    """LangChain callback that feeds ChatAnthropic usage into the session accumulator.

    ChatGeneration stores usage on its .message (AIMessage), not on the generation
    object itself. Two paths are tried for cross-version compatibility:
      1. msg.usage_metadata  — langchain-core >= 0.2 standard field
      2. msg.response_metadata["usage"]  — Anthropic provider-specific fallback
    """

    def on_llm_end(self, response: LLMResult, **kwargs) -> None:
        for generations in response.generations:
            for gen in generations:
                msg = getattr(gen, "message", None)
                if msg is None:
                    continue

                # Path 1: standard usage_metadata (langchain-core >= 0.2)
                usage_meta = getattr(msg, "usage_metadata", None)
                if usage_meta:
                    track_usage(
                        input_tokens=usage_meta.get("input_tokens", 0),
                        output_tokens=usage_meta.get("output_tokens", 0),
                    )
                    continue

                # Path 2: provider response_metadata (Anthropic SDK shape)
                resp_meta = getattr(msg, "response_metadata", None) or {}
                usage = resp_meta.get("usage", {})
                if usage:
                    track_usage(
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                    )
