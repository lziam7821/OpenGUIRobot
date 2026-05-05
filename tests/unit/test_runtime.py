"""Unit tests for runtime.py."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from openguirobot.driver.base import DomTree
from openguirobot.runtime import Session, assert_visual, locate, session


SIMPLE_XML = """
<hierarchy>
  <android.widget.FrameLayout bounds="[0,0][1080,2400]" resource-id="" text="">
    <android.widget.TextView text="购物车" resource-id="id/cart" bounds="[0,100][540,200]"/>
  </android.widget.FrameLayout>
</hierarchy>
"""


def _make_driver(dom_xml=SIMPLE_XML):
    driver = MagicMock()
    driver.dump_dom.return_value = DomTree.from_xml(dom_xml, platform="android")
    driver.screenshot.return_value = b"\x89PNG"
    return driver


# ── session() context manager ──────────────────────────────────────────────────

def test_session_sets_active():
    from openguirobot.runtime import _active_session
    driver = _make_driver()
    assert _active_session.get() is None
    with session(driver, case_id="test") as s:
        assert _active_session.get() is s
    assert _active_session.get() is None


def test_session_yields_session_object():
    driver = _make_driver()
    with session(driver, case_id="my_case") as s:
        assert isinstance(s, Session)


# ── locate() ──────────────────────────────────────────────────────────────────

def test_locate_inside_session():
    driver = _make_driver()
    with session(driver, case_id="test"):
        match = locate("购物车")
    assert match["locator_kind"] == "rule"
    assert match["bbox"] == (0, 100, 540, 200)


def test_locate_outside_session_raises():
    from openguirobot.runtime import _active_session
    _active_session.set(None)
    with pytest.raises(RuntimeError, match="outside of a session"):
        locate("anything")


def test_locate_calls_driver_dump_dom():
    driver = _make_driver()
    with session(driver, case_id="test"):
        locate("购物车")
    driver.dump_dom.assert_called()


# ── assert_visual() ───────────────────────────────────────────────────────────

def test_assert_visual_passes_when_found():
    driver = _make_driver()
    with session(driver, case_id="test"):
        assert_visual("购物车")   # should not raise


def test_assert_visual_fails_when_not_found():
    driver = _make_driver()
    with session(driver, case_id="test"):
        with pytest.raises(AssertionError, match="assert_visual"):
            assert_visual("nonexistent element xyz")


def test_assert_visual_outside_session_raises():
    from openguirobot.runtime import _active_session
    _active_session.set(None)
    with pytest.raises(RuntimeError, match="outside of a session"):
        assert_visual("something")


# ── Session.tap() ─────────────────────────────────────────────────────────────

def test_session_tap_calls_driver():
    driver = _make_driver()
    with session(driver, case_id="test") as s:
        match = locate("购物车")
        s.tap(match)
    # Center of (0,100,540,200) = (270, 150)
    driver.tap.assert_called_once_with(270, 150)


# ── Session.press_key() ───────────────────────────────────────────────────────

def test_session_press_key_back():
    from openguirobot.driver.base import KeyCode
    driver = _make_driver()
    with session(driver, case_id="test") as s:
        s.press_key("BACK")
    driver.press_key.assert_called_once_with(KeyCode.BACK)


# ── Session.input_text() ──────────────────────────────────────────────────────

def test_session_input_text():
    driver = _make_driver()
    with session(driver, case_id="test") as s:
        s.input_text("hello")
    driver.input_text.assert_called_once_with("hello")
