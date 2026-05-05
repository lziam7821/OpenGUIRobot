"""Unit tests for skill/assertor.py."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from openguirobot.driver.base import DomTree
from openguirobot.skill.assertor import assert_element_exists, assert_ocr_text, run_assertions


SIMPLE_XML = """
<hierarchy>
  <android.widget.FrameLayout bounds="[0,0][1080,2400]" resource-id="" text="">
    <android.widget.TextView text="购物车" resource-id="id/cart" bounds="[0,100][540,200]"/>
    <android.widget.Button  text="加入购物车" resource-id="id/add" bounds="[0,300][540,400]"/>
  </android.widget.FrameLayout>
</hierarchy>
"""

FAKE_PNG = b"\x89PNG"


@pytest.fixture
def dom():
    return DomTree.from_xml(SIMPLE_XML, platform="android")


# ── assert_element_exists ──────────────────────────────────────────────────────

def test_element_exists_found_by_text(dom):
    result = assert_element_exists("购物车", dom)
    assert result["passed"] is True
    assert result["confidence"] == 1.0


def test_element_exists_found_by_resource_id(dom):
    result = assert_element_exists("id/add", dom)
    assert result["passed"] is True


def test_element_exists_not_found(dom):
    result = assert_element_exists("nonexistent xyz", dom)
    assert result["passed"] is False
    assert result["confidence"] == 1.0
    assert "nonexistent xyz" in result["reasoning"]


# ── assert_ocr_text ───────────────────────────────────────────────────────────

def _mock_ocr_result(texts: list[str]):
    """Build a fake RapidOCR result: list of (bbox, text, confidence)."""
    return [(None, t, 0.95) for t in texts], None


def test_ocr_text_found():
    mock_img = MagicMock()
    with patch("openguirobot.skill.assertor._get_ocr") as mock_get, \
         patch("PIL.Image.open", return_value=mock_img), \
         patch("numpy.array", return_value=MagicMock()):
        mock_engine = MagicMock()
        mock_engine.return_value = _mock_ocr_result(["购物车", "无线耳机"])
        mock_get.return_value = mock_engine
        result = assert_ocr_text("无线耳机", FAKE_PNG)
    assert result["passed"] is True


def test_ocr_text_not_found():
    mock_img = MagicMock()
    with patch("openguirobot.skill.assertor._get_ocr") as mock_get, \
         patch("PIL.Image.open", return_value=mock_img), \
         patch("numpy.array", return_value=MagicMock()):
        mock_engine = MagicMock()
        mock_engine.return_value = _mock_ocr_result(["Some other text"])
        mock_get.return_value = mock_engine
        result = assert_ocr_text("无线耳机", FAKE_PNG)
    assert result["passed"] is False


def test_ocr_text_empty_result():
    mock_img = MagicMock()
    with patch("openguirobot.skill.assertor._get_ocr") as mock_get, \
         patch("PIL.Image.open", return_value=mock_img), \
         patch("numpy.array", return_value=MagicMock()):
        mock_engine = MagicMock()
        mock_engine.return_value = (None, None)
        mock_get.return_value = mock_engine
        result = assert_ocr_text("anything", FAKE_PNG)
    assert result["passed"] is False
    assert "no results" in result["reasoning"]


# ── run_assertions ─────────────────────────────────────────────────────────────

def test_run_assertions_dispatches(dom):
    from openguirobot.cases.loader import AssertionKind, AssertionSpec
    specs = [
        AssertionSpec(kind=AssertionKind.element_exists, desc="cart", target="购物车"),
    ]
    results = run_assertions(specs, dom, FAKE_PNG)
    assert len(results) == 1
    assert results[0]["passed"] is True


def test_run_assertions_visual_skipped(dom):
    from openguirobot.cases.loader import AssertionKind, AssertionSpec
    specs = [AssertionSpec(kind=AssertionKind.visual, desc="some visual check")]
    results = run_assertions(specs, dom, FAKE_PNG)
    assert len(results) == 1
    assert "not implemented" in results[0]["reasoning"]
