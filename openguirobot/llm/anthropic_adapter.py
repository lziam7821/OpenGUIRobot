"""
LLM adapter — Anthropic (Claude Sonnet, Haiku, Opus, …).
"""
from __future__ import annotations

import os
import time
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from openguirobot.llm.base import Completion, Message

# Cost per 1 000 tokens (input, output) in USD
_COST_TABLE: dict[str, tuple[float, float]] = {
    "claude-opus-4-5":      (0.015,  0.075),
    "claude-sonnet-4-5":    (0.003,  0.015),
    "claude-haiku-4-5":     (0.00025, 0.00125),
    "claude-3-5-sonnet-20241022": (0.003, 0.015),
    "claude-3-5-haiku-20241022":  (0.0008, 0.004),
}
_DEFAULT_COST = (0.003, 0.015)


class AnthropicAdapter:
    """Anthropic Claude chat adapter with tenacity retry."""

    def __init__(
        self,
        model: str = "claude-sonnet-4-5",
        api_key: str | None = None,
        max_tokens: int = 4096,
    ) -> None:
        import anthropic  # lazy import

        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self._model = model
        self._client = anthropic.Anthropic(api_key=key)
        self._max_tokens = max_tokens
        costs = _COST_TABLE.get(model, _DEFAULT_COST)
        self._cost_in, self._cost_out = costs

    @property
    def cost_per_1k_input(self) -> float:
        return self._cost_in

    @property
    def cost_per_1k_output(self) -> float:
        return self._cost_out

    def chat(self, messages: list[Message], **kwargs: Any) -> Completion:
        return self._chat_with_retry(messages, **kwargs)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        reraise=True,
    )
    def _chat_with_retry(self, messages: list[Message], **kwargs: Any) -> Completion:
        import anthropic

        # Anthropic separates system messages from the messages list
        system_parts = [m.content for m in messages if m.role == "system"]
        user_msgs    = [m.to_anthropic_dict() for m in messages if m.role != "system"]
        system_text  = "\n\n".join(str(p) for p in system_parts) if system_parts else anthropic.NOT_GIVEN

        t0 = time.monotonic()
        try:
            resp = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system_text,
                messages=user_msgs,
                **kwargs,
            )
        except anthropic.APIError as exc:
            raise RuntimeError(f"Anthropic API error: {exc}") from exc

        latency_ms = int((time.monotonic() - t0) * 1000)
        tokens_in  = resp.usage.input_tokens
        tokens_out = resp.usage.output_tokens
        cost = (tokens_in / 1000 * self._cost_in) + (tokens_out / 1000 * self._cost_out)
        content = resp.content[0].text if resp.content else ""
        return Completion(
            content=content,
            model=resp.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=round(cost, 8),
            latency_ms=latency_ms,
        )
