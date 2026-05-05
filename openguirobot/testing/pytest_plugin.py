"""
OpenGUIRobot pytest plugin — registers CLI options, fixtures, and test collection.

Register in pyproject.toml::

    [project.entry-points."pytest11"]
    openguirobot = "openguirobot.testing.pytest_plugin"

Or install directly with conftest.py::

    # tests/conftest.py
    pytest_plugins = ["openguirobot.testing.pytest_plugin"]

Options added:
  --ogr-mode      explore | replay  (default: replay)
  --ogr-device    device UDID or name
  --ogr-budget-usd  per-run budget cap in USD

Fixtures:
  ogr_driver   — yields a connected Driver (skips if OGR_DEVICE not set)
  ogr_case     — loads a CaseSpec from the case YAML matching the test node's case_id

Test collection:
  Automatically discovers tests/generated/**/*.py (matching test_*.py).
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Generator

import pytest


# ── Plugin hooks ───────────────────────────────────────────────────────────────

def pytest_addoption(parser: pytest.Parser) -> None:
    """Register OGR-specific CLI options."""
    group = parser.getgroup("openguirobot", "OpenGUIRobot automation options")
    group.addoption(
        "--ogr-mode",
        default="replay",
        choices=["explore", "replay"],
        help="OGR run mode: 'explore' (live LLM) or 'replay' (zero-token, default).",
    )
    group.addoption(
        "--ogr-device",
        default=None,
        help="Target device UDID or emulator name (overrides OGR_DEVICE env var).",
    )
    group.addoption(
        "--ogr-budget-usd",
        default=None,
        type=float,
        help="Per-run LLM cost budget in USD. Terminates explore if exceeded.",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "ogr_generated: mark test as an auto-generated OGR regression script",
    )


def pytest_collect_file(
    parent: pytest.Collector,
    file_path: Path,
) -> pytest.Module | None:
    """
    Auto-collect generated test files under tests/generated/.

    Only activates for .py files whose parent path contains 'generated' and
    whose name starts with 'test_'.  Returns None to let the default collector
    handle everything else.
    """
    if (
        file_path.suffix == ".py"
        and file_path.name.startswith("test_")
        and "generated" in file_path.parts
    ):
        return pytest.Module.from_parent(parent, path=file_path)
    return None


# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def ogr_driver(request: pytest.FixtureRequest) -> Generator[Any, None, None]:
    """
    Yield a connected Driver for the target device.

    Resolution order for device ID:
      1. --ogr-device CLI option
      2. OGR_DEVICE environment variable

    Resolution order for platform:
      1. OGR_PLATFORM environment variable (default: android)

    Skips the test if no device is configured.
    """
    device_id = (
        request.config.getoption("--ogr-device", default=None)
        or os.environ.get("OGR_DEVICE", "")
    )
    platform   = os.environ.get("OGR_PLATFORM", "android")
    appium_url = os.environ.get("OGR_APPIUM_URL", "http://localhost:4723")

    if not device_id:
        pytest.skip(
            "No device configured. Set --ogr-device or OGR_DEVICE to run this test."
        )

    from openguirobot.driver.base import Driver

    driver: Driver
    if platform == "android":
        from openguirobot.driver.android import AndroidDriver
        driver = AndroidDriver(appium_url=appium_url)
    elif platform == "ios":
        from openguirobot.driver.ios import IOSDriver
        driver = IOSDriver(appium_url=appium_url)
    else:
        pytest.fail(f"Unsupported OGR_PLATFORM: {platform!r}")

    driver.attach(device_id)
    yield driver
    driver.detach()


@pytest.fixture
def ogr_case(request: pytest.FixtureRequest) -> Any:
    """
    Load a CaseSpec from the cases directory.

    The case_id is resolved from (in order):
      1. ``ogr_case_id`` marker argument on the test
      2. The test module's ``OGR_CASE_ID`` module-level variable

    Skips the test if no case_id can be found.
    """
    # Try marker first
    marker = request.node.get_closest_marker("ogr_case_id")
    if marker and marker.args:
        case_id: str = marker.args[0]
    else:
        # Try module-level variable
        module = request.node.getparent(pytest.Module)
        case_id = getattr(module, "OGR_CASE_ID", None) if module else None  # type: ignore[assignment]

    if not case_id:
        pytest.skip("No OGR case_id found. Add @pytest.mark.ogr_case_id('...') to the test.")

    from openguirobot.cases.loader import load_case
    from openguirobot.config import load_config

    cfg = load_config()
    cases_dir = os.environ.get("OGR_CASES_DIR", cfg.cases_dir)
    try:
        return load_case(case_id, cases_dir)
    except FileNotFoundError:
        pytest.skip(f"Case definition not found: {case_id!r} in {cases_dir!r}")


@pytest.fixture
def ogr_budget(request: pytest.FixtureRequest) -> Any:
    """
    Return a CostBudget instance pre-configured from --ogr-budget-usd or case budget.

    Intended to be used alongside ``ogr_case``::

        def test_something(ogr_case, ogr_budget):
            ogr_budget.add(tokens_in=100, tokens_out=50, cost_usd=0.001)
    """
    from openguirobot.obs.cost import CostBudget

    budget_usd: float = (
        request.config.getoption("--ogr-budget-usd", default=None)
        or 0.0
    )
    return CostBudget(budget_usd=float(budget_usd))
