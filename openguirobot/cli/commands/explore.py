"""
`ogr explore` — Code-as-Action exploration command.

Full pipeline:
  load_case → attach driver → plan → for each step: codegen → AST guard →
  sandbox execute → capture evidence → solidify → replay-ready pytest file
"""
from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table

from openguirobot.action.ast_guard import ASTGuardError
from openguirobot.action.codegen import Codegen, CodegenError, PlanGenerationError
from openguirobot.action.compiler import Compiler
from openguirobot.action.sandbox import Sandbox, SandboxConfig
from openguirobot.cases.loader import load_case
from openguirobot.config import load_config
from openguirobot.obs.evidence import EvidenceWriter

console = Console()


class ExploreError(RuntimeError):
    """Raised when the exploration pipeline encounters an unrecoverable error."""


class BudgetExceededError(ExploreError):
    """Raised when the accumulated LLM cost exceeds case.budget_usd."""


# ── CLI command ────────────────────────────────────────────────────────────────

@click.command()
@click.argument("case_id")
@click.option("--device",     required=True,  help="Device UDID or name (e.g. emulator-5554).")
@click.option("--llm",        default=None,   help="LLM provider:model (e.g. anthropic:claude-sonnet-4-5).")
@click.option("--budget-usd", default=None,   type=float, help="Override per-case LLM budget.")
@click.option("--timeout-s",  default=None,   type=int,   help="Override total timeout in seconds.")
@click.option("--platform",   default=None,   type=click.Choice(["android", "ios"]),
              help="Force platform (default: first platform in case YAML).")
@click.option("--tier",       default=None,   type=int,   help="Sandbox tier (0=AST only, 1=OS sandbox).")
@click.option("--cases-dir",  default=None,   help="Override cases directory.")
def explore(
    case_id: str,
    device: str,
    llm: str | None,
    budget_usd: float | None,
    timeout_s: int | None,
    platform: str | None,
    tier: int | None,
    cases_dir: str | None,
) -> None:
    """Run Code-as-Action exploration for a test case and solidify the result."""
    cfg = load_config()

    # ── Load case ──────────────────────────────────────────────────────────────
    try:
        case = load_case(case_id, cases_dir or cfg.cases_dir)
    except FileNotFoundError as exc:
        console.print(f"[red]Case not found:[/red] {exc}")
        sys.exit(1)

    if budget_usd is not None:
        case = case.model_copy(update={"budget_usd": budget_usd})
    if timeout_s is not None:
        case = case.model_copy(update={"timeout_s": timeout_s})

    plat = platform or case.platforms[0].value
    console.print(f"\n[bold cyan]ogr explore[/bold cyan] {case.case_id} | device={device} | platform={plat}")
    console.print(f"  budget=${case.budget_usd:.2f}  timeout={case.timeout_s}s\n")

    # ── Build LLM client ───────────────────────────────────────────────────────
    llm_client = _build_llm(llm, cfg)

    # ── Build vision model ─────────────────────────────────────────────────────
    vision = _build_vision(cfg)

    # ── Attach driver ──────────────────────────────────────────────────────────
    driver = _build_driver(plat, cfg.appium.url)
    console.print(f"[dim]Attaching to {plat} device {device!r}…[/dim]")
    try:
        driver.attach(device)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]Failed to attach driver:[/red] {exc}")
        sys.exit(1)

    evidence  = EvidenceWriter(case.case_id, base_dir=cfg.evidence_dir)
    codegen   = Codegen(llm=llm_client, evidence=evidence)
    compiler  = Compiler(output_dir=cfg.generated_dir)
    sandbox_cfg = SandboxConfig(
        tier=tier if tier is not None else cfg.sandbox.tier,
        step_timeout_s=cfg.sandbox.step_timeout_s,
        total_timeout_s=case.timeout_s,
        memory_limit_mb=cfg.sandbox.memory_limit_mb,
    )
    sandbox = Sandbox(config=sandbox_cfg)

    context: dict[str, Any] = {
        "appium_url": cfg.appium.url,
        "device_id":  device,
        "platform":   plat,
        "case_id":    case.case_id,
        "vision": {
            "provider": cfg.vision.default_provider,
        },
    }

    start_time   = time.monotonic()
    total_cost   = 0.0
    step_results = []
    codegen_results = []

    try:
        # ── Initial state ──────────────────────────────────────────────────────
        console.print("[dim]Capturing initial screen state…[/dim]")
        initial_shot = driver.screenshot()
        initial_dom  = driver.dump_dom()
        evidence.write_screenshot(0, "before", initial_shot)
        evidence.write_dom(0, initial_dom.raw_xml)

        # ── Plan ───────────────────────────────────────────────────────────────
        console.print("[dim]Generating test plan…[/dim]")
        try:
            plan = codegen.plan(case, plat, initial_shot, initial_dom)
        except PlanGenerationError as exc:
            console.print(f"[red]Plan generation failed:[/red] {exc}")
            sys.exit(1)

        _print_plan(plan)

        # ── Step loop ──────────────────────────────────────────────────────────
        prev_result = "ok (initial state)"
        for step in plan.steps:
            elapsed = time.monotonic() - start_time
            if elapsed >= case.timeout_s:
                console.print(f"[red]Timeout exceeded ({case.timeout_s}s)[/red]")
                sys.exit(1)
            if total_cost >= case.budget_usd:
                console.print(
                    f"[red]Budget exceeded (${total_cost:.4f} ≥ ${case.budget_usd:.2f})[/red]"
                )
                sys.exit(1)

            console.print(
                f"\n[bold]Step {step.index}/{plan.total_steps}:[/bold] {step.intent}"
            )

            # Capture before state
            before_shot = driver.screenshot()
            dom         = driver.dump_dom()
            evidence.write_screenshot(step.index, "before", before_shot)
            evidence.write_dom(step.index, dom.raw_xml)

            # Codegen
            console.print("  [dim]Generating code…[/dim]")
            try:
                result = codegen.gen_step(
                    step, case, plat, dom, prev_result, step.index, plan.total_steps
                )
            except CodegenError as exc:
                console.print(f"  [red]Codegen failed:[/red] {exc}")
                sys.exit(1)

            console.print(f"  [cyan]Code:[/cyan] {result.code}")

            # AST guard (pre-flight check logged inline — sandbox also validates)
            try:
                from openguirobot.action.ast_guard import ASTGuard
                ASTGuard.validate(result.code)
            except ASTGuardError as exc:
                console.print(f"  [red]AST guard violation:[/red] {exc}")
                _record_step(step_results, step.index, step.intent, result.code,
                             "ast_guard_error", str(exc))
                sys.exit(1)

            # Sandbox execution
            console.print("  [dim]Executing in sandbox…[/dim]")
            sandbox_result = sandbox.run_step(result.code, context)

            if not sandbox_result.ok:
                err = sandbox_result.stderr or sandbox_result.stdout or "unknown error"
                console.print(f"  [red]Execution failed:[/red] {err[:300]}")
                evidence.write_screenshot(step.index, "after", driver.screenshot())
                _record_step(step_results, step.index, step.intent, result.code,
                             "failed", err[:300])
                sys.exit(1)

            # Capture after state
            after_shot = driver.screenshot()
            evidence.write_screenshot(step.index, "after", after_shot)

            _record_step(step_results, step.index, step.intent, result.code, "ok", "")
            codegen_results.append(result)
            prev_result = f"ok (step {step.index} completed)"
            console.print(f"  [green]✓[/green] {result.expected_observation}")

        # ── Assertions ─────────────────────────────────────────────────────────
        if case.assertions:
            console.print("\n[bold]Running assertions…[/bold]")
            from openguirobot.skill.assertor import run_assertions
            final_dom  = driver.dump_dom()
            final_shot = driver.screenshot()
            a_results  = run_assertions(case.assertions, final_dom, final_shot)
            for spec, ar in zip(case.assertions, a_results):
                icon = "[green]✓[/green]" if ar["passed"] else "[yellow]⚠[/yellow]"
                console.print(f"  {icon} [{spec.kind.value}] {spec.desc}")

        # ── Solidify ───────────────────────────────────────────────────────────
        console.print("\n[bold]Solidifying to pytest script…[/bold]")
        out_path = compiler.solidify(case, codegen_results, plan)
        console.print(f"  [green]Written:[/green] {out_path}")

    finally:
        total_time = time.monotonic() - start_time
        evidence.write_summary(step_results, total_time, total_cost)
        try:
            driver.detach()
        except Exception:  # noqa: BLE001
            pass

    console.print(
        f"\n[bold green]Exploration complete[/bold green] in {total_time:.1f}s "
        f"| cost=${total_cost:.4f} | evidence: {evidence.run_dir}"
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _build_llm(llm_flag: str | None, cfg: Any) -> Any:
    """Parse --llm flag and instantiate the appropriate adapter."""
    provider_model = llm_flag or cfg.llm.default_provider
    parts = provider_model.split(":", 1)
    provider = parts[0]
    model    = parts[1] if len(parts) > 1 else None

    if provider == "openai":
        from openguirobot.llm.openai_adapter import OpenAIAdapter
        return OpenAIAdapter(model=model or "gpt-4o")
    if provider == "anthropic":
        from openguirobot.llm.anthropic_adapter import AnthropicAdapter
        return AnthropicAdapter(model=model or "claude-sonnet-4-5")
    console.print(f"[red]Unknown LLM provider: {provider!r}[/red]")
    sys.exit(1)


def _build_vision(cfg: Any) -> Any:
    provider = cfg.vision.default_provider
    if provider == "qwen_vl_dashscope":
        from openguirobot.vision.qwen_vl_dashscope import QwenVLDashScope
        return QwenVLDashScope()
    if provider == "gpt4o":
        from openguirobot.vision.gpt4o import GPT4oVision
        return GPT4oVision()
    return None


def _build_driver(platform: str, appium_url: str) -> Any:
    if platform == "android":
        from openguirobot.driver.android import AndroidDriver
        return AndroidDriver(appium_url=appium_url)
    if platform == "ios":
        from openguirobot.driver.ios import IOSDriver
        return IOSDriver(appium_url=appium_url)
    console.print(f"[red]Unsupported platform: {platform!r}[/red]")
    sys.exit(1)


def _print_plan(plan: Any) -> None:
    table = Table(title="Generated Plan", show_header=True, header_style="bold")
    table.add_column("#",      width=4, justify="right")
    table.add_column("Intent", style="cyan")
    table.add_column("Rollback hint", style="dim")
    for s in plan.steps:
        table.add_row(str(s.index), s.intent, s.rollback_hint)
    console.print(table)


def _record_step(
    step_results: list[dict],
    index: int,
    intent: str,
    code: str,
    status: str,
    error: str,
) -> None:
    step_results.append({
        "index":  index,
        "intent": intent,
        "code":   code,
        "status": status,
        "error":  error,
    })
