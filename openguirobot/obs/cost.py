"""
Cost & Budget tracker — accumulates token usage and USD cost across LLM calls
during a single explore/heal run.

Usage::

    budget = CostBudget(budget_usd=1.5, evidence_dir=Path("evidence/my_case/run1"))
    budget.add(tokens_in=1000, tokens_out=200, cost_usd=0.006)

    # After each LLM call:
    if budget.is_exceeded():
        raise BudgetExceededError(...)

    # At run end, optionally write a summary:
    budget.write_to_summary(summary_path)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class BudgetWarning(UserWarning):
    """Issued when accumulated cost reaches ≥80% of the budget."""


class BudgetExceededError(RuntimeError):
    """Raised when accumulated cost reaches ≥100% of the budget."""


@dataclass
class CostEntry:
    """Record of a single LLM call's token usage and cost."""
    step:       int
    tokens_in:  int
    tokens_out: int
    cost_usd:   float
    model:      str = ""


@dataclass
class CostBudget:
    """
    Tracks cumulative LLM cost for one explore/heal run.

    Args:
        budget_usd:   Maximum allowed spend for this run (0 = unlimited).
        evidence_dir: Directory where summary.json will be updated.
                      Pass None to skip file I/O.
    """
    budget_usd:   float
    evidence_dir: Path | None = None
    _entries:     list[CostEntry] = field(default_factory=list, repr=False)

    # ── Accumulation ──────────────────────────────────────────────────────────

    def add(
        self,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        step: int = 0,
        model: str = "",
    ) -> None:
        """
        Record one LLM call's usage.

        Emits BudgetWarning when spend first crosses 80%.
        Raises BudgetExceededError when spend reaches or exceeds 100%.
        """
        import warnings

        prev_ratio = self._ratio(self.total_cost_usd)
        self._entries.append(CostEntry(
            step=step,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost_usd,
            model=model,
        ))
        curr_ratio = self._ratio(self.total_cost_usd)

        # Warn once when crossing 80%
        if prev_ratio < 0.8 <= curr_ratio and self.budget_usd > 0:
            warnings.warn(
                f"LLM cost ${self.total_cost_usd:.4f} has reached "
                f"{curr_ratio * 100:.0f}% of budget (${self.budget_usd:.2f})",
                BudgetWarning,
                stacklevel=2,
            )

        if self.is_exceeded():
            raise BudgetExceededError(
                f"LLM budget exceeded: ${self.total_cost_usd:.4f} "
                f">= ${self.budget_usd:.2f}"
            )

    # ── Queries ───────────────────────────────────────────────────────────────

    @property
    def total_cost_usd(self) -> float:
        return sum(e.cost_usd for e in self._entries)

    @property
    def total_tokens_in(self) -> int:
        return sum(e.tokens_in for e in self._entries)

    @property
    def total_tokens_out(self) -> int:
        return sum(e.tokens_out for e in self._entries)

    @property
    def remaining_usd(self) -> float:
        if self.budget_usd <= 0:
            return float("inf")
        return max(0.0, self.budget_usd - self.total_cost_usd)

    def is_exceeded(self) -> bool:
        """Return True when accumulated cost ≥ budget (0 = unlimited, never exceeded)."""
        if self.budget_usd <= 0:
            return False
        return self.total_cost_usd >= self.budget_usd

    def usage_ratio(self) -> float:
        """Return fraction of budget used (0.0–∞).  Always 0.0 if budget=0."""
        return self._ratio(self.total_cost_usd)

    def _ratio(self, cost: float) -> float:
        if self.budget_usd <= 0:
            return 0.0
        return cost / self.budget_usd

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "budget_usd":       round(self.budget_usd, 6),
            "total_cost_usd":   round(self.total_cost_usd, 6),
            "total_tokens_in":  self.total_tokens_in,
            "total_tokens_out": self.total_tokens_out,
            "usage_ratio":      round(self.usage_ratio(), 4),
            "entries": [
                {
                    "step":       e.step,
                    "tokens_in":  e.tokens_in,
                    "tokens_out": e.tokens_out,
                    "cost_usd":   round(e.cost_usd, 8),
                    "model":      e.model,
                }
                for e in self._entries
            ],
        }

    def write_to_summary(self, summary_path: Path) -> None:
        """
        Merge cost data into an existing summary.json (or create it).

        Reads the existing file (if any), injects a "cost" key, and rewrites.
        """
        try:
            existing: dict[str, Any] = {}
            if summary_path.exists():
                existing = json.loads(summary_path.read_text(encoding="utf-8"))
            existing["cost"] = self.to_dict()
            summary_path.write_text(
                json.dumps(existing, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:  # noqa: BLE001
            pass   # Never crash the main flow due to evidence I/O
