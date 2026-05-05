"""
`ogr replay` — run a solidified pytest script (zero LLM tokens).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import click
from rich.console import Console

from openguirobot.cases.loader import load_case
from openguirobot.config import load_config

console = Console()


@click.command()
@click.argument("case_id")
@click.option("--device",    required=True, help="Device UDID or name.")
@click.option("--platform",  default=None,  type=click.Choice(["android", "ios"]),
              help="Force platform (default: first in case YAML).")
@click.option("--cases-dir", default=None,  help="Override cases directory.")
@click.option("--pytest-args", default="",  help="Extra arguments forwarded to pytest.")
def replay(
    case_id: str,
    device: str,
    platform: str | None,
    cases_dir: str | None,
    pytest_args: str,
) -> None:
    """Run a solidified test script via pytest (0 LLM tokens)."""
    import pytest

    cfg = load_config()

    # ── Locate case ────────────────────────────────────────────────────────────
    try:
        case = load_case(case_id, cases_dir or cfg.cases_dir)
    except FileNotFoundError as exc:
        console.print(f"[red]Case not found:[/red] {exc}")
        sys.exit(1)

    plat = platform or case.platforms[0].value

    # ── Find generated script ──────────────────────────────────────────────────
    script_path = Path(cfg.generated_dir) / case.group / f"{case.name}.py"
    if not script_path.exists():
        console.print(
            f"[red]Generated script not found:[/red] {script_path}\n"
            f"Run [cyan]ogr explore {case_id} --device {device}[/cyan] first."
        )
        sys.exit(1)

    console.print(
        f"\n[bold cyan]ogr replay[/bold cyan] {case.case_id} | "
        f"device={device} | platform={plat}"
    )
    console.print(f"  script: {script_path}\n")

    # ── Set env vars for the driver fixture ───────────────────────────────────
    os.environ["OGR_DEVICE"]   = device
    os.environ["OGR_PLATFORM"] = plat

    # ── Invoke pytest ──────────────────────────────────────────────────────────
    args = [str(script_path), "-v", "--tb=short"]
    if pytest_args:
        args.extend(pytest_args.split())

    exit_code = pytest.main(args)
    sys.exit(exit_code)
