"""Unit tests for action/codegen.py."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from openguirobot.action.codegen import Codegen, CodegenError, Plan, PlanGenerationError, _summarize_dom
from openguirobot.cases.loader import TestCase
from openguirobot.driver.base import DomTree
from openguirobot.llm.base import Completion


SIMPLE_XML = """
<hierarchy>
  <android.widget.FrameLayout bounds="[0,0][1080,2400]" resource-id="" text="">
    <android.widget.TextView text="Search" resource-id="id/search" bounds="[0,100][540,200]"/>
  </android.widget.FrameLayout>
</hierarchy>
"""

VALID_PLAN = {
    "steps": [
        {"index": 1, "intent": "Tap search bar", "rollback_hint": "Press back"},
        {"index": 2, "intent": "Type query",     "rollback_hint": "Clear field"},
    ],
    "total_steps": 2,
}

VALID_STEP = {
    "code": "s.tap(locate('搜索框'))",
    "expected_observation": "Keyboard appears",
    "rollback_hint": "Press back",
}


@pytest.fixture
def dom():
    return DomTree.from_xml(SIMPLE_XML, platform="android")


@pytest.fixture
def case():
    return TestCase(
        case_id="e.test",
        title="Test",
        intent="Search and add",
        platforms=["android"],
    )


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    return llm


@pytest.fixture
def mock_evidence():
    return MagicMock()


def _make_completion(content: str) -> Completion:
    return Completion(content=content, model="claude", tokens_in=100, tokens_out=50,
                      cost_usd=0.001, latency_ms=500)


# ── _summarize_dom ─────────────────────────────────────────────────────────────

def test_summarize_dom_basic(dom):
    summary, count = _summarize_dom(dom)
    assert "Search" in summary
    assert count >= 1


def test_summarize_dom_truncates(dom):
    summary, count = _summarize_dom(dom, max_nodes=1)
    assert "omitted" in summary or count == 1


# ── Codegen.plan ──────────────────────────────────────────────────────────────

def test_plan_success(mock_llm, mock_evidence, case, dom):
    mock_llm.chat.return_value = _make_completion(json.dumps(VALID_PLAN))
    cg = Codegen(llm=mock_llm, evidence=mock_evidence)
    plan = cg.plan(case, "android", b"", dom)
    assert plan.total_steps == 2
    assert plan.steps[0].intent == "Tap search bar"


def test_plan_records_llm_call(mock_llm, mock_evidence, case, dom):
    mock_llm.chat.return_value = _make_completion(json.dumps(VALID_PLAN))
    cg = Codegen(llm=mock_llm, evidence=mock_evidence)
    cg.plan(case, "android", b"", dom)
    mock_evidence.write_llm_call.assert_called_once()
    call_args = mock_evidence.write_llm_call.call_args[0]
    assert call_args[0] == 0  # step=0 for plan


def test_plan_invalid_json_raises(mock_llm, mock_evidence, case, dom):
    mock_llm.chat.return_value = _make_completion("not valid json")
    cg = Codegen(llm=mock_llm, evidence=mock_evidence)
    with pytest.raises(PlanGenerationError, match="Failed to parse plan"):
        cg.plan(case, "android", b"", dom)


# ── Codegen.gen_step ──────────────────────────────────────────────────────────

def test_gen_step_success(mock_llm, mock_evidence, case, dom):
    mock_llm.chat.return_value = _make_completion(json.dumps(VALID_STEP))
    plan = Plan.model_validate(VALID_PLAN)
    cg = Codegen(llm=mock_llm, evidence=mock_evidence)
    result = cg.gen_step(plan.steps[0], case, "android", dom, "ok", 1, 2)
    assert result.code == "s.tap(locate('搜索框'))"


def test_gen_step_invalid_json_raises(mock_llm, mock_evidence, case, dom):
    mock_llm.chat.return_value = _make_completion("```python\nno json```")
    plan = Plan.model_validate(VALID_PLAN)
    cg = Codegen(llm=mock_llm, evidence=mock_evidence)
    with pytest.raises(CodegenError):
        cg.gen_step(plan.steps[0], case, "android", dom, "ok", 1, 2)


def test_gen_step_records_llm_call(mock_llm, mock_evidence, case, dom):
    mock_llm.chat.return_value = _make_completion(json.dumps(VALID_STEP))
    plan = Plan.model_validate(VALID_PLAN)
    cg = Codegen(llm=mock_llm, evidence=mock_evidence)
    cg.gen_step(plan.steps[0], case, "android", dom, "ok", 1, 2)
    mock_evidence.write_llm_call.assert_called_once()
    call_args = mock_evidence.write_llm_call.call_args[0]
    assert call_args[0] == 1  # step=1
