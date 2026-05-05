"""Unit tests for vision/qwen_vl_dashscope.py and vision/gpt4o.py."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

# Minimal 1×1 PNG bytes for testing
FAKE_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ── QwenVLDashScope ────────────────────────────────────────────────────────────

class TestQwenVLDashScope:
    def _make_adapter(self):
        from openguirobot.vision.qwen_vl_dashscope import QwenVLDashScope
        return QwenVLDashScope(api_key="test-key", timeout_s=5)

    def _mock_response(self, text: str):
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "output": {
                "choices": [
                    {"message": {"content": [{"text": text}]}}
                ]
            }
        }
        resp.raise_for_status = MagicMock()
        return resp

    def test_ground_returns_bbox(self):
        adapter = self._make_adapter()
        bbox_json = json.dumps({"x1": 10, "y1": 20, "x2": 100, "y2": 80})
        with patch("httpx.post", return_value=self._mock_response(bbox_json)):
            result = adapter.ground(FAKE_PNG, "search button")
        assert result == (10, 20, 100, 80)

    def test_ground_returns_none_on_bad_json(self):
        adapter = self._make_adapter()
        with patch("httpx.post", return_value=self._mock_response("No JSON here")):
            result = adapter.ground(FAKE_PNG, "button")
        assert result is None

    def test_ground_returns_none_on_http_error(self):
        import httpx
        adapter = self._make_adapter()
        with patch("httpx.post", side_effect=httpx.HTTPError("connection error")):
            with pytest.raises(RuntimeError, match="DashScope HTTP error"):
                adapter._ground_with_retry(FAKE_PNG, "button")

    def test_ground_returns_none_on_missing_key(self):
        adapter = self._make_adapter()
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"output": {}}  # missing choices
        resp.raise_for_status = MagicMock()
        with patch("httpx.post", return_value=resp):
            result = adapter.ground(FAKE_PNG, "button")
        assert result is None


# ── GPT4oVision ───────────────────────────────────────────────────────────────

class TestGPT4oVision:
    def _make_adapter(self):
        from openguirobot.vision.gpt4o import GPT4oVision
        with patch("openai.OpenAI"):
            adapter = GPT4oVision(api_key="test-key")
        adapter._client = MagicMock()
        return adapter

    def _mock_completion(self, text: str):
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = text
        return resp

    def test_ground_returns_bbox(self):
        adapter = self._make_adapter()
        bbox_text = '{"x1":5,"y1":10,"x2":60,"y2":90}'
        adapter._client.chat.completions.create.return_value = self._mock_completion(bbox_text)
        result = adapter.ground(FAKE_PNG, "add to cart button")
        assert result == (5, 10, 60, 90)

    def test_ground_returns_none_on_bad_json(self):
        adapter = self._make_adapter()
        adapter._client.chat.completions.create.return_value = self._mock_completion("not json")
        result = adapter.ground(FAKE_PNG, "button")
        assert result is None

    def test_ground_returns_none_on_empty_response(self):
        adapter = self._make_adapter()
        adapter._client.chat.completions.create.return_value = self._mock_completion("")
        result = adapter.ground(FAKE_PNG, "button")
        assert result is None
