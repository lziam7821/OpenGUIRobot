"""Unit tests for llm/openai_adapter.py and llm/anthropic_adapter.py."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from openguirobot.llm.base import Completion, Message


# ── OpenAIAdapter ─────────────────────────────────────────────────────────────

def _make_openai_response(content="Hello", model="gpt-4o", tokens_in=100, tokens_out=50):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    resp.model = model
    resp.usage.prompt_tokens     = tokens_in
    resp.usage.completion_tokens = tokens_out
    return resp


class TestOpenAIAdapter:
    def test_chat_returns_completion(self):
        from openguirobot.llm.openai_adapter import OpenAIAdapter

        with patch("openai.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.chat.completions.create.return_value = _make_openai_response()

            adapter = OpenAIAdapter(model="gpt-4o", api_key="test-key")
            result = adapter.chat([Message(role="user", content="Hi")])

        assert isinstance(result, Completion)
        assert result.content == "Hello"
        assert result.model == "gpt-4o"
        assert result.tokens_in == 100
        assert result.tokens_out == 50

    def test_cost_calculation_gpt4o(self):
        from openguirobot.llm.openai_adapter import OpenAIAdapter

        with patch("openai.OpenAI") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.chat.completions.create.return_value = _make_openai_response(
                tokens_in=1000, tokens_out=1000
            )
            adapter = OpenAIAdapter(model="gpt-4o", api_key="test-key")
            result = adapter.chat([Message(role="user", content="Hi")])

        # gpt-4o: 0.005/1k in + 0.015/1k out = 0.005 + 0.015 = 0.02
        assert abs(result.cost_usd - 0.020) < 1e-6

    def test_cost_calculation_mini(self):
        from openguirobot.llm.openai_adapter import OpenAIAdapter

        with patch("openai.OpenAI"):
            adapter = OpenAIAdapter(model="gpt-4o-mini", api_key="test-key")
        assert adapter.cost_per_1k_input  == 0.00015
        assert adapter.cost_per_1k_output == 0.0006


# ── AnthropicAdapter ──────────────────────────────────────────────────────────

def _make_anthropic_response(content="World", model="claude-sonnet-4-5",
                              tokens_in=80, tokens_out=40):
    resp = MagicMock()
    resp.content = [MagicMock()]
    resp.content[0].text = content
    resp.model = model
    resp.usage.input_tokens  = tokens_in
    resp.usage.output_tokens = tokens_out
    return resp


class TestAnthropicAdapter:
    def test_chat_returns_completion(self):
        from openguirobot.llm.anthropic_adapter import AnthropicAdapter

        with patch("anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_anthropic_response()

            adapter = AnthropicAdapter(model="claude-sonnet-4-5", api_key="test-key")
            result = adapter.chat([Message(role="user", content="Hi")])

        assert isinstance(result, Completion)
        assert result.content == "World"
        assert result.tokens_in == 80
        assert result.tokens_out == 40

    def test_system_message_extracted(self):
        from openguirobot.llm.anthropic_adapter import AnthropicAdapter

        with patch("anthropic.Anthropic") as mock_cls:
            mock_client = MagicMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_anthropic_response()

            adapter = AnthropicAdapter(model="claude-sonnet-4-5", api_key="test-key")
            messages = [
                Message(role="system", content="You are a tester."),
                Message(role="user",   content="Tap the button"),
            ]
            adapter.chat(messages)
            call_kwargs = mock_client.messages.create.call_args[1]

        assert call_kwargs["system"] == "You are a tester."
        assert len(call_kwargs["messages"]) == 1
        assert call_kwargs["messages"][0]["role"] == "user"

    def test_cost_per_1k(self):
        from openguirobot.llm.anthropic_adapter import AnthropicAdapter

        with patch("anthropic.Anthropic"):
            adapter = AnthropicAdapter(model="claude-sonnet-4-5", api_key="test-key")
        assert adapter.cost_per_1k_input  == 0.003
        assert adapter.cost_per_1k_output == 0.015
