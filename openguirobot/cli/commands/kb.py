"""
`ogr kb` — Knowledge Base management commands.

Sub-commands:
  ogr kb lint          Lint all KB Markdown files under docs/kb/
  ogr kb lint --strict Also error on missing optional fields (confidence, last_verified)
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def kb() -> None:
    """Knowledge Base management."""


@kb.command("lint")
@click.option(
    "--kb-dir",
    default=None,
    help="KB root directory (default: docs/kb/ relative to cwd).",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Also error on missing optional fields (confidence, last_verified).",
)
def kb_lint(kb_dir: str | None, strict: bool) -> None:
    """Lint all KB Markdown files for valid front matter and line-count limits."""
    from openguirobot.memory.kb import lint_kb

    kb_root = Path(kb_dir) if kb_dir else Path.cwd() / "docs" / "kb"

    console.print(
        f"\n[bold cyan]ogr kb lint[/bold cyan] "
        f"{'(strict) ' if strict else ''}"
        f"→ [dim]{kb_root}[/dim]\n"
    )

    report = lint_kb(kb_root, strict=strict)

    if report.files_checked == 0:
        console.print(f"[yellow]No Markdown files found under {kb_root}[/yellow]")
        return

    if not report.violations:
        console.print(
            f"[green]✓ All {report.files_checked} file(s) passed.[/green]"
        )
        return

    # ── Print violations table ─────────────────────────────────────────────────
    table = Table(show_header=True, header_style="bold", expand=True)
    table.add_column("File",     style="dim",    ratio=4)
    table.add_column("Line",     justify="right", width=6)
    table.add_column("Severity", width=8)
    table.add_column("Message",  ratio=6)

    errors = 0
    warnings = 0
    for v in report.violations:
        if v.severity == "error":
            errors += 1
            sev_style = "[red]error[/red]"
        else:
            warnings += 1
            sev_style = "[yellow]warn[/yellow]"

        table.add_row(
            str(v.file.relative_to(Path.cwd()) if v.file.is_relative_to(Path.cwd()) else v.file),
            str(v.line) if v.line is not None else "-",
            sev_style,
            v.message,
        )

    console.print(table)
    console.print(
        f"\n[dim]Checked {report.files_checked} file(s)[/dim] — "
        f"[red]{errors} error(s)[/red]  [yellow]{warnings} warning(s)[/yellow]"
    )

    if report.has_errors:
        sys.exit(1)
