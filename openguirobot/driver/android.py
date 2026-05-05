"""
L0 Driver — Android implementation via Appium UiAutomator2.
"""
from __future__ import annotations

import time

from appium import webdriver
from appium.options import UiAutomator2Options
from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import WebDriverException

from openguirobot.driver.base import (
    ActionError,
    AttachError,
    DomTree,
    DriverError,
    DriverTimeoutError,
    KeyCode,
)

# Android keycode mapping (KeyCode → Android key integer)
_KEYCODES: dict[KeyCode, int] = {
    KeyCode.HOME:        3,
    KeyCode.BACK:        4,
    KeyCode.ENTER:       66,
    KeyCode.TAB:         61,
    KeyCode.DELETE:      67,
    KeyCode.VOLUME_UP:   24,
    KeyCode.VOLUME_DOWN: 25,
    KeyCode.POWER:       26,
}


class AndroidDriver:
    """Appium UiAutomator2 driver for Android devices and emulators."""

    def __init__(
        self,
        appium_url: str = "http://localhost:4723",
        extra_capabilities: dict | None = None,
    ) -> None:
        self._appium_url = appium_url
        self._extra_caps = extra_capabilities or {}
        self._session: webdriver.Remote | None = None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def attach(self, device_id: str) -> None:
        options = UiAutomator2Options()
        options.platform_name = "Android"
        options.udid = device_id
        options.automation_name = "UiAutomator2"
        options.no_reset = True
        options.new_command_timeout = 300
        for k, v in self._extra_caps.items():
            options.set_capability(k, v)
        try:
            self._session = webdriver.Remote(self._appium_url, options=options)
        except WebDriverException as exc:
            raise AttachError(
                f"Failed to attach to Android device {device_id!r}: {exc}"
            ) from exc

    def detach(self) -> None:
        if self._session is not None:
            try:
                self._session.quit()
            except Exception:  # noqa: BLE001
                pass
            self._session = None

    # ── Internal helpers ─────────────────────────────────────────────────────

    @property
    def _s(self) -> webdriver.Remote:
        if self._session is None:
            raise DriverError("Driver is not attached. Call attach() first.")
        return self._session

    # ── Core actions ─────────────────────────────────────────────────────────

    def tap(self, x: int, y: int) -> None:
        try:
            self._s.execute_script("mobile: clickGesture", {"x": x, "y": y})
        except WebDriverException as exc:
            raise ActionError(f"tap({x}, {y}) failed: {exc}") from exc

    def swipe(
        self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300
    ) -> None:
        try:
            self._s.execute_script(
                "mobile: swipeGesture",
                {
                    "left": min(x1, x2),
                    "top": min(y1, y2),
                    "width": abs(x2 - x1) or 1,
                    "height": abs(y2 - y1) or 1,
                    "direction": _swipe_direction(x1, y1, x2, y2),
                    "percent": 1.0,
                    "speed": max(1, int(abs(x2 - x1 + y2 - y1) / (duration_ms / 1000))),
                },
            )
        except WebDriverException as exc:
            raise ActionError(f"swipe failed: {exc}") from exc

    def input_text(self, text: str) -> None:
        try:
            self._s.execute_script("mobile: type", {"text": text})
        except WebDriverException as exc:
            raise ActionError(f"input_text failed: {exc}") from exc

    def press_key(self, key: KeyCode) -> None:
        code = _KEYCODES.get(key)
        if code is None:
            raise ActionError(f"Unsupported key: {key!r}")
        try:
            self._s.press_keycode(code)
        except WebDriverException as exc:
            raise ActionError(f"press_key({key!r}) failed: {exc}") from exc

    def screenshot(self) -> bytes:
        try:
            return self._s.get_screenshot_as_png()
        except WebDriverException as exc:
            raise ActionError(f"screenshot() failed: {exc}") from exc

    def dump_dom(self) -> DomTree:
        try:
            xml_str: str = self._s.page_source
        except WebDriverException as exc:
            raise ActionError(f"dump_dom() failed: {exc}") from exc
        return DomTree.from_xml(xml_str, platform="android")

    def get_window_size(self) -> tuple[int, int]:
        size = self._s.get_window_size()
        return int(size["width"]), int(size["height"])

    def launch_app(self, package_or_bundle_id: str) -> None:
        try:
            self._s.execute_script(
                "mobile: activateApp", {"appId": package_or_bundle_id}
            )
        except WebDriverException as exc:
            raise ActionError(f"launch_app({package_or_bundle_id!r}) failed: {exc}") from exc

    def kill_app(self, package_or_bundle_id: str) -> None:
        try:
            self._s.execute_script(
                "mobile: terminateApp", {"appId": package_or_bundle_id}
            )
        except WebDriverException as exc:
            raise ActionError(f"kill_app({package_or_bundle_id!r}) failed: {exc}") from exc

    def get_current_app(self) -> str:
        try:
            result = self._s.execute_script("mobile: activePackage", {})
            return str(result)
        except WebDriverException as exc:
            raise ActionError(f"get_current_app() failed: {exc}") from exc

    # ── Context manager support ──────────────────────────────────────────────

    def __enter__(self) -> "AndroidDriver":
        return self

    def __exit__(self, *_: object) -> None:
        self.detach()


def _swipe_direction(x1: int, y1: int, x2: int, y2: int) -> str:
    """Determine primary swipe direction for mobile:swipeGesture."""
    dx, dy = x2 - x1, y2 - y1
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"
