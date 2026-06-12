"""
Per-session LLM token accumulator using contextvars.

Safe for async/single-process use: each call to start_session() creates a fresh
TokenUsage object bound to the current async context. Agents call track_usage()
after every Anthropic API call. The parent coroutine reads get_current() at the end.

Two integration points:
  - Raw Anthropic SDK (CollaborationHub, OptionGenerator):
        from metrics.token_tracker import track_usage
        response = self.client.messages.create(...)
        track_usage(response.usage.input_tokens, response.usage.output_tokens, model=MODEL)

  - LangChain ChatAnthropic (IntentParser, ExperienceAgent, etc.):
        from metrics.token_tracker import TokenTrackingCallback
        self.llm = ChatAnthropic(..., callbacks=[TokenTrackingCallback(model=MODEL)])

Pricing: MODEL_PRICING maps exact Anthropic model IDs to (input, output) rates in USD
per million tokens. Unknown models log a warning and fall back to Sonnet rates.

Session cost is computed via compute_session_cost(), which sums per-model costs using
the exact rate for each model. Haiku tokens are never priced at Sonnet rates.

Sanity check: 1M in + 1M out on Haiku ($6) plus 1M in + 1M out on Sonnet ($18) = $24.00.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass, field

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

_logger = logging.getLogger(__name__)

# (input_cost_per_mtok, output_cost_per_mtok) in USD — verify at anthropic.com/pricing
MODEL_PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-sonnet-4-5-20250929": (3.00, 15.00),
    "claude-sonnet-4-6": (3.00, 15.00),
}
_SONNET_RATES: tuple[float, float] = (3.00, 15.00)


def _pricing_for(model: str) -> tuple[float, float]:
    """Return (input_rate, output_rate) per MTok. Warns and falls back for unknown models."""
    if model in MODEL_PRICING:
        return MODEL_PRICING[model]
    for key, rates in MODEL_PRICING.items():
        if key in model or model in key:
            return rates
    _logger.warning(
        "Unknown model %r — pricing unknown, using Sonnet fallback ($3/$15 per MTok). "
        "Add this model to metrics.token_tracker.MODEL_PRICING.",
        model,
    )
    return _SONNET_RATES


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    models_used: dict = field(default_factory=dict)  # model_id → call_count
    per_model: dict = field(default_factory=dict)    # model_id → {"input": int, "output": int}

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "models_used": dict(self.models_used),
            "per_model": {m: dict(v) for m, v in self.per_model.items()},
        }


_current: ContextVar[TokenUsage | None] = ContextVar("session_token_usage", default=None)


def start_session() -> TokenUsage:
    """Reset the accumulator for a new session. Call once per run."""
    usage = TokenUsage()
    _current.set(usage)
    return usage


def track_usage(input_tokens: int, output_tokens: int, model: str = "") -> None:
    """Add tokens from one LLM call to the running session total."""
    usage = _current.get()
    if usage is not None:
        usage.input_tokens += input_tokens
        usage.output_tokens += output_tokens
        if model:
            usage.models_used[model] = usage.models_used.get(model, 0) + 1
            pm = usage.per_model.setdefault(model, {"input": 0, "output": 0})
            pm["input"] += input_tokens
            pm["output"] += output_tokens


def get_current() -> TokenUsage | None:
    """Return the current session's accumulator (None if no session started)."""
    return _current.get()


def compute_cost(input_tokens: int, output_tokens: int, model: str = "") -> float:
    """Return estimated USD cost given token counts and a model ID string."""
    in_rate, out_rate = _pricing_for(model) if model else _SONNET_RATES
    return round(
        input_tokens / 1_000_000 * in_rate + output_tokens / 1_000_000 * out_rate,
        6,
    )


def compute_session_cost(usage: TokenUsage) -> float:
    """Compute session cost using per-model pricing for accuracy.

    When per_model breakdown is present each model's tokens are priced at their
    own rate, so Haiku tokens are never charged at Sonnet rates. Any tokens that
    were tracked without a model string land only in the session totals, not in
    per_model — those are the unattributed remainder. The remainder is priced at
    Sonnet fallback rates and a warning is logged so the gap is never silent.
    Falls back to Sonnet rates on the full totals when per_model is empty.
    """
    if not usage.per_model:
        return compute_cost(usage.input_tokens, usage.output_tokens)

    attributed_input = sum(m["input"] for m in usage.per_model.values())
    attributed_output = sum(m["output"] for m in usage.per_model.values())
    model_cost = sum(
        compute_cost(m["input"], m["output"], model)
        for model, m in usage.per_model.items()
    )

    remainder_input = usage.input_tokens - attributed_input
    remainder_output = usage.output_tokens - attributed_output
    if remainder_input > 0 or remainder_output > 0:
        _logger.warning(
            "compute_session_cost: %d input and %d output tokens have no model attribution "
            "— priced at Sonnet fallback rates. Pass model= to track_usage() to fix this.",
            remainder_input,
            remainder_output,
        )
        remainder_cost = compute_cost(remainder_input, remainder_output)
        return round(model_cost + remainder_cost, 6)

    return round(model_cost, 6)


class TokenTrackingCallback(BaseCallbackHandler):
    """LangChain callback that feeds ChatAnthropic usage into the session accumulator.

    ChatGeneration stores usage on its .message (AIMessage), not on the generation
    object itself. Two paths are tried for cross-version compatibility:
      1. msg.usage_metadata  — langchain-core >= 0.2 standard field
      2. msg.response_metadata["usage"]  — Anthropic provider-specific fallback
    """

    def __init__(self, model: str = ""):
        super().__init__()
        self.model = model

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
                        model=self.model,
                    )
                    continue

                # Path 2: provider response_metadata (Anthropic SDK shape)
                resp_meta = getattr(msg, "response_metadata", None) or {}
                usage = resp_meta.get("usage", {})
                if usage:
                    track_usage(
                        input_tokens=usage.get("input_tokens", 0),
                        output_tokens=usage.get("output_tokens", 0),
                        model=self.model,
                    )
