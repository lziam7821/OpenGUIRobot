"""
L2 Action — Compiler / Solidifier.

Takes a completed exploration (Plan + per-step CodegenResults) and writes a
formatted, self-contained pytest file to ``tests/generated/``.

The output file:
  - Is formatted with black (line-length=100)
  - Imports only from openguirobot.runtime (zero LLM calls at replay time)
  - Has a header with case_id, generation timestamp, and intent hash
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import black
from jinja2 import Environment, PackageLoader, select_autoescape

if TYPE_CHECKING:
    from openguirobot.action.codegen import CodegenResult, Plan
    from openguirobot.cases.loader import TestCase


_jinja_env = Environment(
    loader=PackageLoader("openguirobot", "action/templates"),
    autoescape=select_autoescape([]),
    keep_trailing_newline=True,
)


class Compiler:
    """Solidifies an exploration result into a runnable pytest file."""

    def __init__(self, output_dir: Path | str = Path("tests/generated")) -> None:
        self._output_dir = Path(output_dir)

    def solidify(
        self,
        case: "TestCase",
        codegen_results: list["CodegenResult"],
        plan: "Plan",
    ) -> Path:
        """
        Render solidify.py.j2 → black-format → write to tests/generated/.

        Returns the path of the written file.
        """
        generated_at = datetime.now(tz=timezone.utc).isoformat()
        intent_hash  = hashlib.sha256(case.intent.encode()).hexdigest()[:12]

        # Pair each PlanStep.intent with its CodegenResult.code
        steps = [
            {
                "intent": plan.steps[i].intent if i < len(plan.steps) else f"Step {i + 1}",
                "code":   codegen_results[i].code,
            }
            for i in range(len(codegen_results))
        ]

        template = _jinja_env.get_template("solidify.py.j2")
        raw = template.render(
            case=case,
            steps=steps,
            generated_at=generated_at,
            intent_hash=intent_hash,
        )

        # Format with black; keep raw output if black fails (shouldn't happen)
        try:
            formatted = black.format_str(raw, mode=black.Mode(line_length=100))
        except black.InvalidInput:
            formatted = raw

        # Determine output path: tests/generated/<group>/<name>.py
        out_path = self._output_dir / case.group / f"{case.name}.py"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(formatted, encoding="utf-8")
        return out_path
