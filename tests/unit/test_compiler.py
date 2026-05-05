"""Unit tests for action/compiler.py."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from openguirobot.action.codegen import CodegenResult, Plan
from openguirobot.action.compiler import Compiler
from openguirobot.cases.loader import TestCase

PLAN_DATA = {
    "steps": [
        {"index": 1, "intent": "Launch app",   "rollback_hint": "Close app"},
        {"index": 2, "intent": "Tap search",   "rollback_hint": "Press back"},
    ],
    "total_steps": 2,
}

STEPS = [
    CodegenResult(code="s.launch_app('com.example')", expected_observation="App opens", rollback_hint="Close"),
    CodegenResult(code="s.tap(locate('搜索框'))",     expected_observation="Keyboard",  rollback_hint="Back"),
]


@pytest.fixture
def case():
    return TestCase(
        case_id="e_commerce.add_to_cart",
        title="Add to cart",
        intent="Launch and add",
        platforms=["android"],
    )


@pytest.fixture
def plan():
    return Plan.model_validate(PLAN_DATA)


@pytest.fixture
def compiler(tmp_path):
    return Compiler(output_dir=tmp_path)


def test_solidify_creates_file(compiler, case, plan, tmp_path):
    out = compiler.solidify(case, STEPS, plan)
    assert out.exists()
    assert out.suffix == ".py"


def test_solidify_correct_path(compiler, case, plan, tmp_path):
    out = compiler.solidify(case, STEPS, plan)
    # e_commerce.add_to_cart → tests/generated/e_commerce/add_to_cart.py
    assert out.parent.name == "e_commerce"
    assert out.name == "add_to_cart.py"


def test_solidify_valid_python(compiler, case, plan):
    out = compiler.solidify(case, STEPS, plan)
    source = out.read_text()
    ast.parse(source)   # raises SyntaxError if invalid


def test_solidify_contains_imports(compiler, case, plan):
    out = compiler.solidify(case, STEPS, plan)
    src = out.read_text()
    assert "import pytest" in src
    assert "from openguirobot.runtime import" in src


def test_solidify_contains_function(compiler, case, plan):
    out = compiler.solidify(case, STEPS, plan)
    src = out.read_text()
    assert "def test_e_commerce_add_to_cart" in src


def test_solidify_contains_step_code(compiler, case, plan):
    out = compiler.solidify(case, STEPS, plan)
    src = out.read_text()
    assert "s.launch_app" in src
    assert "s.tap(locate" in src


def test_solidify_contains_case_id_marker(compiler, case, plan):
    out = compiler.solidify(case, STEPS, plan)
    src = out.read_text()
    assert "e_commerce.add_to_cart" in src


def test_solidify_contains_do_not_edit(compiler, case, plan):
    out = compiler.solidify(case, STEPS, plan)
    src = out.read_text()
    assert "DO NOT edit by hand" in src


def test_solidify_creates_parent_dirs(tmp_path, plan):
    compiler = Compiler(output_dir=tmp_path / "deep" / "nested")
    case = TestCase(
        case_id="a.b.c",
        title="Nested",
        intent="Test",
        platforms=["android"],
    )
    steps = [CodegenResult(code="s.tap(locate('x'))", expected_observation="ok", rollback_hint="back")]
    plan2 = Plan(steps=[plan.steps[0]], total_steps=1)
    out = compiler.solidify(case, steps, plan2)
    assert out.exists()
