"""
Shared pytest fixtures for OpenGUIRobot tests.

The ``driver`` fixture is used by generated regression scripts (replay mode).
Device is configured via OGR_DEVICE and OGR_PLATFORM environment variables,
which are set by `ogr replay` before invoking pytest.
"""
from __future__ import annotations

import os

import pytest

from openguirobot.driver.base import Driver

# Load the OGR pytest plugin so its fixtures (ogr_budget, ogr_driver, …)
# are available in all tests without requiring a package installation.
pytest_plugins = ["openguirobot.testing.pytest_plugin"]


@pytest.fixture
def driver() -> "Driver":  # type: ignore[type-arg]
    """
    Provide a connected Driver instance for replay.

    Reads:
      OGR_DEVICE   — device UDID or emulator name
      OGR_PLATFORM — "android" (default) or "ios"
      OGR_APPIUM_URL — Appium server URL (default: http://localhost:4723)
    """
    device_id  = os.environ.get("OGR_DEVICE", "")
    platform   = os.environ.get("OGR_PLATFORM", "android")
    appium_url = os.environ.get("OGR_APPIUM_URL", "http://localhost:4723")

    if not device_id:
        pytest.skip("OGR_DEVICE environment variable not set — skipping replay test")

    if platform == "android":
        from openguirobot.driver.android import AndroidDriver
        d: Driver = AndroidDriver(appium_url=appium_url)
    elif platform == "ios":
        from openguirobot.driver.ios import IOSDriver
        d = IOSDriver(appium_url=appium_url)
    else:
        pytest.fail(f"Unsupported OGR_PLATFORM: {platform!r}")

    d.attach(device_id)
    yield d  # type: ignore[misc]
    d.detach()
