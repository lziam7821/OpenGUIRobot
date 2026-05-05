"""
Vision adapter — GPT-4o vision via OpenAI API.
"""
from __future__ import annotations

import base64
import json
import os
import re

from tenacity import retry, stop_after_attempt, wait_exponential

from openguirobot.vision.base import BBox

_GROUND_PROMPT_TEMPLATE = (
    "Locate '{target}' in this screenshot. "
    'Return ONLY a JSON object {"x1":int,"y1":int,"x2":int,"y2":int} '
    "with pixel coordinates of the bounding box. No other text."
)


class GPT4oVision:
    """GPT-4o vision grounding via OpenAI chat completions."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "gpt-4o",
    ) -> None:
        import openai  # lazy import

        key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model = model
        self._client = openai.OpenAI(api_key=key)

    def ground(self, image: bytes, target: str) -> BBox | None:
        return self._ground_with_retry(image, target)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        reraise=True,
    )
    def _ground_with_retry(self, image: bytes, target: str) -> BBox | None:
        import openai

        b64 = base64.b64encode(image).decode()
        data_url = f"data:image/png;base64,{b64}"
        prompt = _GROUND_PROMPT_TEMPLATE.replace("{target}", target)

        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": data_url}},
                            {"type": "text",      "text": prompt},
                        ],
                    }
                ],
                max_tokens=128,
            )
        except openai.OpenAIError as exc:
            raise RuntimeError(f"GPT-4o vision error: {exc}") from exc

        text = resp.choices[0].message.content or ""
        return _parse_bbox(text)


def _parse_bbox(text: str) -> BBox | None:
    match = re.search(r"\{[^}]+\}", text)
    if not match:
        return None
    try:
        obj = json.loads(match.group())
        return (int(obj["x1"]), int(obj["y1"]), int(obj["x2"]), int(obj["y2"]))
    except (json.JSONDecodeError, KeyError, ValueError):
        return None
