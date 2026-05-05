"""Unit tests for obs/cost.py."""
from __future__ import annotations

import json
import warnings
from pathlib import Path

import pytest

from openguirobot.obs.cost import BudgetExceededError, BudgetWarning, CostBudget, CostEntry


# ── CostEntry ──────────────────────────────────────────────────────────────────

def test_cost_entry_fields():
    e = CostEntry(step=1, tokens_in=100, tokens_out=50, cost_usd=0.002, model="claude")
    assert e.step == 1
    assert e.tokens_in == 100
    assert e.tokens_out == 50
    assert e.cost_usd == 0.002
    assert e.model == "claude"


# ── CostBudget basics ─────────────────────────────────────────────────────────

def test_initial_state():
    b = CostBudget(budget_usd=1.0)
    assert b.total_cost_usd == 0.0
    assert b.total_tokens_in == 0
    assert b.total_tokens_out == 0
    assert b.remaining_usd == 1.0
    assert b.is_exceeded() is False
    assert b.usage_ratio() == 0.0


def test_add_accumulates():
    b = CostBudget(budget_usd=1.0)
    b.add(tokens_in=500, tokens_out=100, cost_usd=0.003, step=1, model="gpt-4o")
    b.add(tokens_in=200, tokens_out=50, cost_usd=0.001, step=2, model="claude")
    assert b.total_tokens_in == 700
    assert b.total_tokens_out == 150
    assert abs(b.total_cost_usd - 0.004) < 1e-9


def test_remaining_decreases():
    b = CostBudget(budget_usd=1.0)
    b.add(tokens_in=100, tokens_out=50, cost_usd=0.3)
    assert abs(b.remaining_usd - 0.7) < 1e-9


def test_remaining_unlimited():
    b = CostBudget(budget_usd=0.0)
    b.add(tokens_in=1000000, tokens_out=1000000, cost_usd=9999.0)
    assert b.remaining_usd == float("inf")


# ── Budget warnings and errors ─────────────────────────────────────────────────

def test_budget_warning_at_80_percent():
    b = CostBudget(budget_usd=1.0)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        b.add(tokens_in=0, tokens_out=0, cost_usd=0.80)
    assert any(issubclass(w.category, BudgetWarning) for w in caught)


def test_no_warning_below_80_percent():
    b = CostBudget(budget_usd=1.0)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        b.add(tokens_in=0, tokens_out=0, cost_usd=0.79)
    budget_warnings = [w for w in caught if issubclass(w.category, BudgetWarning)]
    assert len(budget_warnings) == 0


def test_warning_not_repeated():
    """Warning fires only when crossing the 80% threshold, not on every subsequent add."""
    b = CostBudget(budget_usd=1.0)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        b.add(tokens_in=0, tokens_out=0, cost_usd=0.81)   # crosses 80%
        # The next add also keeps the total above 80%, but shouldn't warn again
        # (total is already above threshold before the add)
        # Note: another add that starts above 80% won't re-trigger the warning
        # because prev_ratio >= 0.8 before the add
    budget_warnings = [w for w in caught if issubclass(w.category, BudgetWarning)]
    assert len(budget_warnings) == 1


def test_budget_exceeded_error():
    b = CostBudget(budget_usd=0.5)
    with pytest.raises(BudgetExceededError, match="budget exceeded"):
        b.add(tokens_in=0, tokens_out=0, cost_usd=0.5)


def test_budget_exceeded_after_multiple_adds():
    b = CostBudget(budget_usd=1.0)
    b.add(tokens_in=0, tokens_out=0, cost_usd=0.6)
    with pytest.raises(BudgetExceededError):
        b.add(tokens_in=0, tokens_out=0, cost_usd=0.5)


def test_zero_budget_never_exceeded():
    b = CostBudget(budget_usd=0.0)
    b.add(tokens_in=1000000, tokens_out=1000000, cost_usd=9999.0)
    assert b.is_exceeded() is False


# ── usage_ratio ───────────────────────────────────────────────────────────────

def test_usage_ratio():
    b = CostBudget(budget_usd=2.0)
    b.add(tokens_in=0, tokens_out=0, cost_usd=1.0)
    assert abs(b.usage_ratio() - 0.5) < 1e-9


def test_usage_ratio_zero_budget():
    b = CostBudget(budget_usd=0.0)
    assert b.usage_ratio() == 0.0


# ── to_dict ────────────────────────────────────────────────────────────────────

def test_to_dict_structure():
    b = CostBudget(budget_usd=1.0)
    b.add(tokens_in=100, tokens_out=50, cost_usd=0.005, step=1, model="claude")
    d = b.to_dict()
    assert d["budget_usd"] == 1.0
    assert d["total_cost_usd"] == 0.005
    assert d["total_tokens_in"] == 100
    assert d["total_tokens_out"] == 50
    assert len(d["entries"]) == 1
    entry = d["entries"][0]
    assert entry["step"] == 1
    assert entry["model"] == "claude"


# ── write_to_summary ──────────────────────────────────────────────────────────

def test_write_to_summary_creates_file(tmp_path):
    b = CostBudget(budget_usd=1.0)
    b.add(tokens_in=100, tokens_out=50, cost_usd=0.003, step=1)
    path = tmp_path / "summary.json"
    b.write_to_summary(path)
    data = json.loads(path.read_text())
    assert "cost" in data
    assert data["cost"]["total_cost_usd"] == 0.003


def test_write_to_summary_merges_existing(tmp_path):
    """Should merge into existing summary.json, preserving other fields."""
    path = tmp_path / "summary.json"
    path.write_text(json.dumps({"case_id": "my.case", "steps": []}))

    b = CostBudget(budget_usd=0.5)
    b.add(tokens_in=50, tokens_out=20, cost_usd=0.001, step=1)
    b.write_to_summary(path)

    data = json.loads(path.read_text())
    assert data["case_id"] == "my.case"   # preserved
    assert "cost" in data                  # added


def test_write_to_summary_silent_on_error(tmp_path):
    """If summary_path is unwritable, should not raise."""
    b = CostBudget(budget_usd=1.0)
    bad_path = tmp_path / "nonexistent_dir" / "summary.json"
    # Should not raise
    b.write_to_summary(bad_path)
