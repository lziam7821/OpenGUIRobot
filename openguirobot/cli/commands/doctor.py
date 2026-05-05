"""
`ogr doctor` — environment self-check command.

Verifies that all required external dependencies are present and reachable.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import click
import httpx
from rich.console import Console
from rich.table import Table

from openguirobot.config import load_config

console = Console()

# ── Individual checks ──────────────────────────────────────────────────────────

CheckResult = tuple[str, bool, str]   # (name, passed, message)


def _check_python() -> CheckResult:
    v = sys.version_info
    ok = v >= (3, 11)
    return (
        "Python ≥ 3.11",
        ok,
        f"Python {v.major}.{v.minor}.{v.micro}" if ok else f"Python {v.major}.{v.minor} — upgrade required",
    )


def _check_binary(name: str, args: list[str], label: str) -> CheckResult:
    if shutil.which(name) is None:
        return label, False, f"`{name}` not found on PATH"
    try:
        out = subprocess.check_output(args, stderr=subprocess.STDOUT, timeout=5).decode().strip()
        first_line = out.splitlines()[0] if out else "(no output)"
        return label, True, first_line
    except Exception as exc:  # noqa: BLE001
        return label, False, str(exc)


def _check_appium(url: str) -> CheckResult:
    label = f"Appium server ({url})"
    try:
        resp = httpx.get(f"{url}/status", timeout=3)
        if resp.status_code == 200:
            return label, True, "reachable"
        return label, False, f"HTTP {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        return label, False, f"not reachable — {exc}"


def _check_sandbox() -> CheckResult:
    if sys.platform == "linux":
        ok = shutil.which("bwrap") is not None
        return "Sandbox (bwrap)", ok, "found" if ok else "`bwrap` not found — install bubblewrap"
    if sys.platform == "darwin":
        ok = shutil.which("sandbox-exec") is not None
        return "Sandbox (sandbox-exec)", ok, "found" if ok else "`sandbox-exec` not found"
    return "Sandbox", False, f"Unsupported platform: {sys.platform}"


def _check_env_var(name: str, label: str, required: bool = True) -> CheckResult:
    val = os.environ.get(name)
    if val:
        masked = val[:4] + "****" + val[-2:] if len(val) > 6 else "****"
        return label, True, f"set ({masked})"
    msg = f"{name} not set"
    return label, not required, msg + (" (optional)" if not required else " — required")


def _check_config() -> CheckResult:
    path = Path.home() / ".openguirobot" / "config.yaml"
    if not path.exists():
        return "Config file", True, "not found — using defaults"
    try:
        load_config(path)
        return "Config file", True, str(path)
    except Exception as exc:  # noqa: BLE001
        return "Config file", False, f"invalid YAML — {exc}"


# ── Command ────────────────────────────────────────────────────────────────────

@click.command()
@click.option("--appium-url", default=None, help="Override Appium server URL for the check.")
def doctor(appium_url: str | None) -> None:
    """Check that all required tools and credentials are available."""
    cfg = load_config()
    url = appium_url or cfg.appium.url

    checks: list[CheckResult] = [
        _check_python(),
        _check_binary("adb", ["adb", "version"], "adb (Android Debug Bridge)"),
        _check_appium(url),
        _check_sandbox(),
        _check_env_var("ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY", required=False),
        _check_env_var("OPENAI_API_KEY",    "OPENAI_API_KEY",    required=False),
        _check_env_var("DASHSCOPE_API_KEY", "DASHSCOPE_API_KEY", required=False),
        _check_config(),
    ]

    # Optional iOS checks
    if sys.platform == "darwin":
        checks.insert(3, _check_binary("xcrun", ["xcrun", "--version"], "xcrun (iOS toolchain)"))

    table = Table(title="ogr doctor", show_header=True, header_style="bold cyan")
    table.add_column("Check",   style="dim",  width=36)
    table.add_column("Status",  justify="center", width=8)
    table.add_column("Detail")

    all_required_ok = True
    for name, passed, detail in checks:
        icon = "[green]✓[/green]" if passed else "[red]✗[/red]"
        table.add_row(name, icon, detail)
        # Determine if this is a required check that failed
        if not passed and "optional" not in detail.lower() and "defaults" not in detail.lower():
            all_required_ok = False

    console.print(table)

    if all_required_ok:
        console.print("\n[green]All required checks passed.[/green] You're ready to run ogr!")
    else:
        console.print("\n[red]Some required checks failed.[/red] Fix the issues above before running ogr.")
        sys.exit(1)
