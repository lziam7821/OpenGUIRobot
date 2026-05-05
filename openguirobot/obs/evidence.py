"""
Evidence Writer — persists per-run artifacts: screenshots, DOM, LLM call logs, summary.

Directory layout:
    evidence/<case_id>/<run_id>/
        step-001-before.png
        step-001-after.png
        step-001-dom.xml
        step-001-llm.jsonl     # one JSON object per line
        summary.json
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal


class EvidenceWriter:
    def __init__(
        self,
        case_id: str,
        run_id: str | None = None,
        base_dir: Path | str = Path("evidence"),
    ) -> None:
        ts = run_id or datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.run_dir = Path(base_dir) / case_id / ts
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._case_id = case_id
        self._run_id = ts

    @property
    def run_id(self) -> str:
        return self._run_id

    # ── Per-step writers ──────────────────────────────────────────────────────

    def write_screenshot(
        self, step: int, phase: Literal["before", "after"], data: bytes
    ) -> Path:
        path = self.run_dir / f"step-{step:03d}-{phase}.png"
        path.write_bytes(data)
        return path

    def write_dom(self, step: int, dom_xml: str) -> Path:
        path = self.run_dir / f"step-{step:03d}-dom.xml"
        path.write_text(dom_xml, encoding="utf-8")
        return path

    def write_llm_call(self, step: int, record: dict[str, Any]) -> None:
        """Append one LLM call record to the step's .jsonl file."""
        path = self.run_dir / f"step-{step:03d}-llm.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ── Summary ───────────────────────────────────────────────────────────────

    def write_summary(
        self,
        step_results: list[dict[str, Any]],
        total_time_s: float,
        total_cost_usd: float,
    ) -> Path:
        summary = {
            "case_id":        self._case_id,
            "run_id":         self._run_id,
            "total_time_s":   round(total_time_s, 3),
            "total_cost_usd": round(total_cost_usd, 6),
            "step_count":     len(step_results),
            "steps":          step_results,
        }
        path = self.run_dir / "summary.json"
        path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        return path
