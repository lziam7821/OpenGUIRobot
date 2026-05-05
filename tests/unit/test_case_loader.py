"""Unit tests for cases/loader.py."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from openguirobot.cases.loader import TestCase, list_cases, load_case


@pytest.fixture
def cases_dir(tmp_path):
    return tmp_path


def _write_case(directory: Path, subpath: str, data: dict) -> Path:
    path = directory / subpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data), encoding="utf-8")
    return path


VALID_DATA = {
    "case_id":   "e_commerce.add_to_cart",
    "title":     "Add to cart",
    "intent":    "Tap add to cart button",
    "platforms": ["android"],
    "priority":  "p1",
    "budget_usd": 1.5,
    "timeout_s":  300,
}


# ── load_case ──────────────────────────────────────────────────────────────────

def test_load_case_nested_path(cases_dir):
    _write_case(cases_dir, "e_commerce/add_to_cart.case.yaml", VALID_DATA)
    case = load_case("e_commerce.add_to_cart", cases_dir)
    assert case.case_id == "e_commerce.add_to_cart"
    assert case.title == "Add to cart"


def test_load_case_flat_path(cases_dir):
    _write_case(cases_dir, "mytest.case.yaml", {**VALID_DATA, "case_id": "mytest"})
    case = load_case("mytest", cases_dir)
    assert case.case_id == "mytest"


def test_load_case_not_found(cases_dir):
    with pytest.raises(FileNotFoundError, match="not found"):
        load_case("does.not.exist", cases_dir)


def test_load_case_invalid_yaml(cases_dir):
    path = cases_dir / "bad.case.yaml"
    path.write_text("case_id: missing_required_fields\n", encoding="utf-8")
    with pytest.raises(ValidationError):
        load_case("bad", cases_dir)


# ── TestCase properties ────────────────────────────────────────────────────────

def test_snake_name():
    case = TestCase(**VALID_DATA)
    assert case.snake_name == "e_commerce_add_to_cart"


def test_group():
    case = TestCase(**VALID_DATA)
    assert case.group == "e_commerce"


def test_name():
    case = TestCase(**VALID_DATA)
    assert case.name == "add_to_cart"


def test_group_single_part():
    data = {**VALID_DATA, "case_id": "single"}
    case = TestCase(**data)
    assert case.group == "default"


# ── list_cases ─────────────────────────────────────────────────────────────────

def test_list_cases(cases_dir):
    _write_case(cases_dir, "grp/a.case.yaml", {**VALID_DATA, "case_id": "grp.a"})
    _write_case(cases_dir, "grp/b.case.yaml", {**VALID_DATA, "case_id": "grp.b"})
    _write_case(cases_dir, "other/c.case.yaml", {**VALID_DATA, "case_id": "other.c"})
    results = list_cases(cases_dir)
    assert len(results) == 3
    ids = {c.case_id for c in results}
    assert ids == {"grp.a", "grp.b", "other.c"}


def test_list_cases_empty(cases_dir):
    assert list_cases(cases_dir) == []


def test_list_cases_skips_invalid(cases_dir):
    """Malformed files are silently skipped."""
    _write_case(cases_dir, "valid/a.case.yaml", {**VALID_DATA, "case_id": "valid.a"})
    bad = cases_dir / "bad.case.yaml"
    bad.write_text("not: valid: yaml: [[[", encoding="utf-8")
    results = list_cases(cases_dir)
    # Should get at least the valid one; bad file silently skipped
    assert any(c.case_id == "valid.a" for c in results)
