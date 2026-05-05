"""Unit tests for skill/locator.py."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from openguirobot.driver.base import DomTree
from openguirobot.skill.locator import (
    ElementMatch,
    LocatorError,
    LocatorRuntime,
    bbox_center,
    locate,
)

SIMPLE_XML = """
<hierarchy>
  <android.view.View bounds="[0,0][1080,2400]" resource-id="" text="">
    <android.widget.EditText text="Search" resource-id="com.app:id/search"
        content-desc="search bar" bounds="[10,100][500,200]"/>
    <android.widget.Button text="加入购物车" resource-id="com.app:id/add_cart"
        content-desc="" bounds="[0,400][540,500]"/>
  </android.view.View>
</hierarchy>
"""


@pytest.fixture
def dom():
    return DomTree.from_xml(SIMPLE_XML, platform="android")


@pytest.fixture
def screenshot():
    return b"\x89PNG\r\n"  # minimal fake PNG bytes


# ── bbox_center ────────────────────────────────────────────────────────────────

def test_bbox_center():
    assert bbox_center((10, 20, 110, 70)) == (60, 45)
    assert bbox_center((0, 0, 100, 100)) == (50, 50)


# ── Rule layer ─────────────────────────────────────────────────────────────────

def test_locate_by_resource_id(dom, screenshot):
    runtime = LocatorRuntime(vision=None, evidence=None, step=0)
    match = locate("com.app:id/search", dom, screenshot, runtime)
    assert match["locator_kind"] == "rule"
    assert match["confidence"] == 1.0
    assert match["bbox"] == (10, 100, 500, 200)


def test_locate_by_content_desc(dom, screenshot):
    runtime = LocatorRuntime(vision=None, evidence=None, step=0)
    match = locate("search bar", dom, screenshot, runtime)
    assert match["locator_kind"] == "rule"


def test_locate_by_exact_text(dom, screenshot):
    runtime = LocatorRuntime(vision=None, evidence=None, step=0)
    match = locate("Search", dom, screenshot, runtime)
    assert match["locator_kind"] == "rule"


def test_locate_by_substring_text(dom, screenshot):
    runtime = LocatorRuntime(vision=None, evidence=None, step=0)
    match = locate("购物车", dom, screenshot, runtime)
    assert match["locator_kind"] == "rule"


def test_locate_rule_priority_resource_id_over_text(dom, screenshot):
    """resource_id match should win over text match."""
    runtime = LocatorRuntime(vision=None, evidence=None, step=0)
    match = locate("com.app:id/search", dom, screenshot, runtime)
    assert match["locator_kind"] == "rule"
    assert match["bbox"][0] == 10   # search box x1


# ── Vision layer ───────────────────────────────────────────────────────────────

def test_locate_falls_back_to_vision(dom, screenshot):
    mock_vision = MagicMock()
    mock_vision.ground.return_value = (50, 200, 200, 300)
    runtime = LocatorRuntime(vision=mock_vision, evidence=None, step=1)
    match = locate("nonexistent element", dom, screenshot, runtime)
    assert match["locator_kind"] == "vision"
    assert match["bbox"] == (50, 200, 200, 300)
    mock_vision.ground.assert_called_once_with(screenshot, "nonexistent element")


def test_locate_raises_when_vision_returns_none(dom, screenshot):
    mock_vision = MagicMock()
    mock_vision.ground.return_value = None
    runtime = LocatorRuntime(vision=mock_vision, evidence=None, step=1)
    with pytest.raises(LocatorError, match="nonexistent"):
        locate("nonexistent element xyz", dom, screenshot, runtime)


def test_locate_raises_without_vision(dom, screenshot):
    runtime = LocatorRuntime(vision=None, evidence=None, step=0)
    with pytest.raises(LocatorError, match="vision model not configured"):
        locate("this does not exist at all xyz123", dom, screenshot, runtime)


# ── Short query ────────────────────────────────────────────────────────────────

def test_short_query_no_substring_match(dom, screenshot):
    """Queries shorter than 3 chars should NOT trigger substring matching."""
    runtime = LocatorRuntime(vision=None, evidence=None, step=0)
    # "Se" is a substring of "Search" but len < 3, so no substring match
    with pytest.raises(LocatorError):
        locate("Se", dom, screenshot, runtime)
