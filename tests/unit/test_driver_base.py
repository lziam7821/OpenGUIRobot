"""Unit tests for driver/base.py — DomNode, DomTree, _parse_bounds."""
from __future__ import annotations

import pytest

from openguirobot.driver.base import DomNode, DomTree, _parse_bounds


# ── _parse_bounds ──────────────────────────────────────────────────────────────

def test_parse_bounds_bracket_format():
    assert _parse_bounds("[10,20][100,200]") == (10, 20, 100, 200)


def test_parse_bounds_four_numbers():
    assert _parse_bounds("(5,6,50,60)") == (5, 6, 50, 60)


def test_parse_bounds_empty():
    assert _parse_bounds("") == (0, 0, 0, 0)


# ── DomNode ────────────────────────────────────────────────────────────────────

def _make_node(text="", resource_id="", content_desc="", children=None):
    return DomNode(
        node_id="1",
        class_name="android.widget.TextView",
        text=text,
        resource_id=resource_id,
        content_desc=content_desc,
        bounds=(0, 0, 100, 50),
        children=children or [],
    )


def test_node_center():
    node = _make_node()
    node.bounds = (10, 20, 110, 70)
    assert node.center == (60, 45)


# ── DomTree.from_xml ───────────────────────────────────────────────────────────

SAMPLE_XML = """
<hierarchy>
  <android.widget.FrameLayout bounds="[0,0][1080,2400]" resource-id="" text="">
    <android.widget.TextView text="Search" resource-id="com.app:id/search_box"
        content-desc="search input" bounds="[0,100][540,200]"/>
    <android.widget.Button text="Add to Cart" resource-id="com.app:id/add_btn"
        content-desc="" bounds="[0,400][540,500]"/>
  </android.widget.FrameLayout>
</hierarchy>
"""


@pytest.fixture
def dom():
    return DomTree.from_xml(SAMPLE_XML, platform="android")


def test_from_xml_creates_dom(dom):
    assert dom.platform == "android"
    assert dom.root is not None


def test_find_by_text_exact(dom):
    results = dom.find_by_text("Search", exact=True)
    assert len(results) == 1
    assert results[0].text == "Search"


def test_find_by_text_substring(dom):
    results = dom.find_by_text("Cart", exact=False)
    assert len(results) == 1


def test_find_by_text_not_found(dom):
    assert dom.find_by_text("NonExistent") == []


def test_find_by_resource_id(dom):
    results = dom.find_by_resource_id("com.app:id/search_box")
    assert len(results) == 1


def test_find_by_resource_id_not_found(dom):
    assert dom.find_by_resource_id("com.app:id/does_not_exist") == []


def test_find_by_content_desc(dom):
    results = dom.find_by_content_desc("search input")
    assert len(results) == 1


def test_find_by_class(dom):
    results = dom.find_by_class("android.widget.TextView")
    assert len(results) == 1


def test_all_nodes_count(dom):
    # hierarchy root + frame layout + 2 children = 3 nodes (root is hierarchy wrapper)
    nodes = dom.all_nodes()
    assert len(nodes) >= 3


def test_find_by_text_case_sensitive(dom):
    # exact=True is case-sensitive
    assert dom.find_by_text("search") == []
    assert dom.find_by_text("Search") != []
