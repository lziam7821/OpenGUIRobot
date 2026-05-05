"""
Vision adapter — Qwen-VL-Max via DashScope cloud API.
"""
from __future__ import annotations

import base64
import json
import os
import re

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from openguirobot.vision.base import BBox

_DASHSCOPE_URL = (
    "https://dashscope.aliyuncs.com/api/v1/services/aigc/"
    "multimodal-generation/generation"
)

_GROUND_PROMPT_TEMPLATE = (
    "请找出图中'{target}'的位置，以JSON格式返回其边界框坐标 "
    '{"x1":int,"y1":int,"x2":int,"y2":int}，坐标为像素值。'
    "只返回JSON，不要其他内容。"
)


class QwenVLDashScope:
    """Qwen-VL-Max grounding via DashScope multimodal API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "qwen-vl-max",
        timeout_s: float = 30.0,
    ) -> None:
        self._api_key = api_key or os.environ.get("DASHSCOPE_API_KEY", "")
        self._model = model
        self._timeout = timeout_s

    def ground(self, image: bytes, target: str) -> BBox | None:
        return self._ground_with_retry(image, target)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        reraise=True,
    )
    def _ground_with_retry(self, image: bytes, target: str) -> BBox | None:
        b64 = base64.b64encode(image).decode()
        data_url = f"data:image/png;base64,{b64}"
        prompt = _GROUND_PROMPT_TEMPLATE.replace("{target}", target)

        payload = {
            "model": self._model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"image": data_url},
                            {"text": prompt},
                        ],
                    }
                ]
            },
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type":  "application/json",
        }
        try:
            resp = httpx.post(
                _DASHSCOPE_URL,
                json=payload,
                headers=headers,
                timeout=self._timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise RuntimeError(f"DashScope HTTP error: {exc}") from exc

        body = resp.json()
        try:
            text = body["output"]["choices"][0]["message"]["content"][0]["text"]
        except (KeyError, IndexError, TypeError):
            return None

        return _parse_bbox(text)


def _parse_bbox(text: str) -> BBox | None:
    """Extract the first JSON object containing x1/y1/x2/y2 from model output."""
    match = re.search(r"\{[^}]+\}", text)
    if not match:
        return None
    try:
        obj = json.loads(match.group())
        return (int(obj["x1"]), int(obj["y1"]), int(obj["x2"]), int(obj["y2"]))
    except (json.JSONDecodeError, KeyError, ValueError):
        return None
