"""
`ogr cases` — test case management sub-commands.
"""
from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from openguirobot.cases.loader import list_cases, load_case
from openguirobot.config import load_config

console = Console()


@click.group()
def cases() -> None:
    """Manage test cases."""


@cases.command("list")
@click.option("--cases-dir", default=None, help="Override cases directory.")
def cases_list(cases_dir: str | None) -> None:
    """List all registered test cases."""
    cfg = load_config()
    directory = cases_dir or cfg.cases_dir
    all_cases = list_cases(directory)
    if not all_cases:
        console.print(f"[yellow]No cases found in {directory}[/yellow]")
        return
    table = Table(title=f"Test Cases ({directory})", show_header=True, header_style="bold cyan")
    table.add_column("case_id",   style="bold")
    table.add_column("title")
    table.add_column("platforms")
    table.add_column("priority", justify="center")
    table.add_column("budget", justify="right")
    for c in sorted(all_cases, key=lambda x: x.case_id):
        table.add_row(
            c.case_id,
            c.title,
            ", ".join(p.value for p in c.platforms),
            c.priority,
            f"${c.budget_usd:.2f}",
        )
    console.print(table)


@cases.command("show")
@click.argument("case_id")
@click.option("--cases-dir", default=None, help="Override cases directory.")
def cases_show(case_id: str, cases_dir: str | None) -> None:
    """Show full details of a single test case."""
    cfg = load_config()
    directory = cases_dir or cfg.cases_dir
    try:
        c = load_case(case_id, directory)
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc

    lines = [
        f"[bold]case_id:[/bold]    {c.case_id}",
        f"[bold]title:[/bold]      {c.title}",
        f"[bold]platforms:[/bold]  {', '.join(p.value for p in c.platforms)}",
        f"[bold]priority:[/bold]   {c.priority}",
        f"[bold]budget:[/bold]     ${c.budget_usd:.2f} USD",
        f"[bold]timeout:[/bold]    {c.timeout_s}s",
        "",
        "[bold]intent:[/bold]",
        f"  {c.intent}",
    ]
    if c.env:
        lines += ["", "[bold]env:[/bold]"]
        for k, v in c.env.items():
            lines.append(f"  {k}: {v}")
    if c.assertions:
        lines += ["", "[bold]assertions:[/bold]"]
        for a in c.assertions:
            lines.append(f"  [{a.kind.value}] {a.desc}" + (f" → {a.target}" if a.target else ""))

    console.print(Panel("\n".join(lines), title=f"Case: {c.case_id}", border_style="cyan"))
