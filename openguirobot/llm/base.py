"""
LLM adapter protocol and shared data types.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, runtime_checkable


@dataclass
class Message:
    role:    Literal["system", "user", "assistant"]
    content: str | list[dict[str, Any]]   # str for text, list for multimodal

    def to_openai_dict(self) -> dict[str, Any]:
        return {"role": self.role, "content": self.content}

    def to_anthropic_dict(self) -> dict[str, Any]:
        # Anthropic SDK uses the same shape for non-system messages
        return {"role": self.role, "content": self.content}


@dataclass
class Completion:
    content:     str
    model:       str
    tokens_in:   int
    tokens_out:  int
    cost_usd:    float
    latency_ms:  int


@runtime_checkable
class LLMClient(Protocol):
    """Unified interface for all LLM providers."""

    def chat(self, messages: list[Message], **kwargs: Any) -> Completion:
        """Send a chat request and return the completion."""
        ...

    @property
    def cost_per_1k_input(self) -> float:
        """Cost in USD per 1 000 input tokens."""
        ...

    @property
    def cost_per_1k_output(self) -> float:
        """Cost in USD per 1 000 output tokens."""
        ...
