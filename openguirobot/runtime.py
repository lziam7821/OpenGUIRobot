"""
OpenGUIRobot runtime — imported by generated pytest scripts.

This module must make ZERO LLM or vision model calls during replay.
All functions here are pure Python + DOM operations.

Explore-time path: _create_sandbox_session() creates a live driver session.
Replay-time path : session() / locate() / assert_visual() use rule-layer only.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Generator

from openguirobot.driver.base import DomTree, KeyCode
from openguirobot.skill.assertor import assert_element_exists
from openguirobot.skill.locator import ElementMatch, LocatorError, LocatorRuntime, locate as _locate_impl

if TYPE_CHECKING:
    from openguirobot.driver.base import Driver
    from openguirobot.vision.base import VisionModel


# ── Context variables (per-coroutine / per-thread state) ──────────────────────

_active_session: ContextVar["Session | None"] = ContextVar(
    "_active_session", default=None
)


# ── Session class ──────────────────────────────────────────────────────────────

class Session:
    """
    Thin wrapper over Driver, used inside generated test scripts.

    At explore time: driver is a real AndroidDriver/IOSDriver connected to Appium.
    At replay time : driver is provided by the pytest ``driver`` fixture.
    """

    def __init__(
        self,
        driver: "Driver",
        case_id: str,
        vision: "VisionModel | None" = None,
    ) -> None:
        self._driver = driver
        self._case_id = case_id
        self._vision = vision

    # ── UI actions ─────────────────────────────────────────────────────────────

    def tap(self, match: ElementMatch) -> None:
        from openguirobot.skill.locator import bbox_center
        cx, cy = bbox_center(match["bbox"])
        self._driver.tap(cx, cy)

    def swipe(
        self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300
    ) -> None:
        self._driver.swipe(x1, y1, x2, y2, duration_ms)

    def input_text(self, text: str) -> None:
        self._driver.input_text(text)

    def press_key(self, key: str) -> None:
        self._driver.press_key(KeyCode[key])

    def launch_app(self, package_or_bundle_id: str) -> None:
        self._driver.launch_app(package_or_bundle_id)

    def screenshot(self) -> bytes:
        return self._driver.screenshot()

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _get_runtime(self) -> LocatorRuntime:
        return LocatorRuntime(vision=self._vision, evidence=None, step=0)

    def _fresh_state(self) -> tuple[DomTree, bytes]:
        """Fetch current DOM and screenshot from the device."""
        dom  = self._driver.dump_dom()
        shot = self._driver.screenshot()
        return dom, shot


# ── Context manager ────────────────────────────────────────────────────────────

@contextmanager
def session(
    driver: "Driver",
    case_id: str,
    vision: "VisionModel | None" = None,
) -> Generator[Session, None, None]:
    """
    Context manager used in generated test scripts:

        with session(driver, case_id="...") as s:
            s.tap(locate("search bar"))
    """
    s = Session(driver, case_id, vision=vision)
    token = _active_session.set(s)
    try:
        yield s
    finally:
        _active_session.reset(token)


# ── Top-level functions (called from generated scripts) ────────────────────────

def locate(query: str) -> ElementMatch:
    """
    Find *query* on the current screen.

    At replay time (vision=None): uses rule layer only → zero LLM/vision cost.
    At explore time: may fall back to vision model if configured.
    """
    s = _active_session.get()
    if s is None:
        raise RuntimeError(
            "locate() called outside of a session() context. "
            "Generated scripts must use `with session(driver, ...) as s:`."
        )
    dom, shot = s._fresh_state()
    runtime = s._get_runtime()
    return _locate_impl(query, dom, shot, runtime)


def assert_visual(query: str) -> None:
    """
    Assert that *query* is visible on the current screen.
    Uses DOM rule layer (zero cost at replay time).
    Raises AssertionError on failure.
    """
    s = _active_session.get()
    if s is None:
        raise RuntimeError("assert_visual() called outside of a session() context.")
    dom, _ = s._fresh_state()
    result = assert_element_exists(query, dom)
    if not result["passed"]:
        raise AssertionError(
            f"assert_visual({query!r}) failed: {result['reasoning']}"
        )


# ── Explore-time bootstrap (called from sandbox script) ───────────────────────

def _create_sandbox_session(context: dict[str, Any]) -> Session:
    """
    Create a live Session from the context dict injected by the sandbox parent.
    Called from inside the sandboxed subprocess during exploration.
    """
    platform    = context.get("platform", "android")
    device_id   = context.get("device_id", "")
    appium_url  = context.get("appium_url", "http://localhost:4723")
    vision_cfg  = context.get("vision", None)   # reserved for future use

    if platform == "android":
        from openguirobot.driver.android import AndroidDriver
        driver: "Driver" = AndroidDriver(appium_url=appium_url)
    elif platform == "ios":
        from openguirobot.driver.ios import IOSDriver
        driver = IOSDriver(appium_url=appium_url)
    else:
        raise ValueError(f"Unsupported platform in sandbox context: {platform!r}")

    driver.attach(device_id)

    # Wire up vision model if provided in context
    vision: "VisionModel | None" = None
    if vision_cfg and vision_cfg.get("provider") == "qwen_vl_dashscope":
        from openguirobot.vision.qwen_vl_dashscope import QwenVLDashScope
        vision = QwenVLDashScope()
    elif vision_cfg and vision_cfg.get("provider") == "gpt4o":
        from openguirobot.vision.gpt4o import GPT4oVision
        vision = GPT4oVision()

    s = Session(driver, context.get("case_id", "unknown"), vision=vision)
    # Set as active session so locate() / assert_visual() work inside the sandbox
    _active_session.set(s)
    return s
