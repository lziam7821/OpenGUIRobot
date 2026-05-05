"""
LLM adapter — OpenAI (GPT-4o, GPT-4o-mini, …).
"""
from __future__ import annotations

import os
import time
from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from openguirobot.llm.base import Completion, LLMClient, Message

# Cost per 1 000 tokens (input, output) in USD — update as pricing changes
_COST_TABLE: dict[str, tuple[float, float]] = {
    "gpt-4o":           (0.005,  0.015),
    "gpt-4o-mini":      (0.00015, 0.0006),
    "gpt-4-turbo":      (0.01,   0.03),
    "gpt-3.5-turbo":    (0.0005, 0.0015),
}
_DEFAULT_COST = (0.005, 0.015)   # fallback


class OpenAIAdapter:
    """OpenAI chat completion adapter with tenacity retry."""

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        import openai  # lazy import keeps startup fast when OpenAI is not used

        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model = model
        self._client = openai.OpenAI(api_key=key, base_url=base_url)
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
        import openai

        t0 = time.monotonic()
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[m.to_openai_dict() for m in messages],
                **kwargs,
            )
        except openai.OpenAIError as exc:
            raise RuntimeError(f"OpenAI API error: {exc}") from exc

        latency_ms = int((time.monotonic() - t0) * 1000)
        usage = resp.usage
        tokens_in  = usage.prompt_tokens     if usage else 0
        tokens_out = usage.completion_tokens if usage else 0
        cost = (tokens_in / 1000 * self._cost_in) + (tokens_out / 1000 * self._cost_out)
        content = resp.choices[0].message.content or ""
        return Completion(
            content=content,
            model=resp.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=round(cost, 8),
            latency_ms=latency_ms,
        )
