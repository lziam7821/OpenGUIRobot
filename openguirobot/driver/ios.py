"""
L0 Driver — iOS implementation via Appium XCUITest / WebDriverAgent.
"""
from __future__ import annotations

from appium import webdriver
from appium.options import XCUITestOptions
from selenium.common.exceptions import WebDriverException

from openguirobot.driver.base import (
    ActionError,
    AttachError,
    DomTree,
    DriverError,
    KeyCode,
)

# iOS hardware button names for mobile:pressButton
_IOS_BUTTONS: dict[KeyCode, str] = {
    KeyCode.HOME:        "home",
    KeyCode.VOLUME_UP:   "volumeUp",
    KeyCode.VOLUME_DOWN: "volumeDown",
    KeyCode.POWER:       "power",
}


class IOSDriver:
    """Appium XCUITest driver for iOS devices and simulators."""

    def __init__(
        self,
        appium_url: str = "http://localhost:4723",
        wda_local_port: int = 8100,
        extra_capabilities: dict | None = None,
    ) -> None:
        self._appium_url = appium_url
        self._wda_local_port = wda_local_port
        self._extra_caps = extra_capabilities or {}
        self._session: webdriver.Remote | None = None

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def attach(self, device_id: str) -> None:
        options = XCUITestOptions()
        options.platform_name = "iOS"
        options.udid = device_id
        options.automation_name = "XCUITest"
        options.no_reset = True
        options.new_command_timeout = 300
        options.set_capability("wdaLocalPort", self._wda_local_port)
        options.set_capability("usePrebuiltWDA", False)
        for k, v in self._extra_caps.items():
            options.set_capability(k, v)
        try:
            self._session = webdriver.Remote(self._appium_url, options=options)
        except WebDriverException as exc:
            raise AttachError(
                f"Failed to attach to iOS device {device_id!r}: {exc}"
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
            self._s.execute_script("mobile: tap", {"x": x, "y": y})
        except WebDriverException as exc:
            raise ActionError(f"tap({x}, {y}) failed: {exc}") from exc

    def swipe(
        self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300
    ) -> None:
        try:
            self._s.execute_script(
                "mobile: dragFromToWithVelocity",
                {
                    "fromX": x1,
                    "fromY": y1,
                    "toX": x2,
                    "toY": y2,
                    "velocity": max(
                        100,
                        int(((abs(x2 - x1) + abs(y2 - y1)) / max(duration_ms, 1)) * 1000),
                    ),
                },
            )
        except WebDriverException:
            # Fallback: use basic swipe action
            try:
                self._s.execute_script(
                    "mobile: swipe",
                    {"direction": _swipe_direction(x1, y1, x2, y2)},
                )
            except WebDriverException as exc2:
                raise ActionError(f"swipe failed: {exc2}") from exc2

    def input_text(self, text: str) -> None:
        try:
            self._s.execute_script("mobile: typeText", {"text": text})
        except WebDriverException as exc:
            raise ActionError(f"input_text failed: {exc}") from exc

    def press_key(self, key: KeyCode) -> None:
        if key == KeyCode.BACK:
            # iOS has no hardware back key; swipe from left edge to simulate
            try:
                w, h = self.get_window_size()
                self.swipe(0, h // 2, w // 3, h // 2, duration_ms=200)
            except ActionError:
                pass
            return
        if key == KeyCode.ENTER:
            # Type return character
            try:
                self._s.execute_script("mobile: typeText", {"text": "\n"})
            except WebDriverException as exc:
                raise ActionError(f"press_key(ENTER) failed: {exc}") from exc
            return
        btn = _IOS_BUTTONS.get(key)
        if btn is None:
            raise ActionError(f"Unsupported key for iOS: {key!r}")
        try:
            self._s.execute_script("mobile: pressButton", {"name": btn})
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
        return DomTree.from_xml(xml_str, platform="ios")

    def get_window_size(self) -> tuple[int, int]:
        size = self._s.get_window_size()
        return int(size["width"]), int(size["height"])

    def launch_app(self, package_or_bundle_id: str) -> None:
        try:
            self._s.execute_script(
                "mobile: activateApp", {"bundleId": package_or_bundle_id}
            )
        except WebDriverException as exc:
            raise ActionError(
                f"launch_app({package_or_bundle_id!r}) failed: {exc}"
            ) from exc

    def kill_app(self, package_or_bundle_id: str) -> None:
        try:
            self._s.execute_script(
                "mobile: terminateApp", {"bundleId": package_or_bundle_id}
            )
        except WebDriverException as exc:
            raise ActionError(
                f"kill_app({package_or_bundle_id!r}) failed: {exc}"
            ) from exc

    def get_current_app(self) -> str:
        try:
            result = self._s.execute_script("mobile: activeAppInfo", {})
            if isinstance(result, dict):
                return str(result.get("bundleId", ""))
            return str(result)
        except WebDriverException as exc:
            raise ActionError(f"get_current_app() failed: {exc}") from exc

    # ── Context manager support ──────────────────────────────────────────────

    def __enter__(self) -> "IOSDriver":
        return self

    def __exit__(self, *_: object) -> None:
        self.detach()


def _swipe_direction(x1: int, y1: int, x2: int, y2: int) -> str:
    dx, dy = x2 - x1, y2 - y1
    if abs(dx) >= abs(dy):
        return "right" if dx > 0 else "left"
    return "down" if dy > 0 else "up"
