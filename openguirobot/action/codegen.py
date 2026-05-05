"""
L2 Action — Code-as-Action Codegen.

Two LLM calls per exploration:
  1. plan()     — decompose intent into N atomic steps (plan.j2)
  2. gen_step() — generate Python code for one step (codegen_step.j2)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from jinja2 import Environment, PackageLoader, select_autoescape
from pydantic import BaseModel

from openguirobot.driver.base import DomTree
from openguirobot.llm.base import LLMClient, Message

if TYPE_CHECKING:
    from openguirobot.cases.loader import TestCase
    from openguirobot.obs.evidence import EvidenceWriter


# ── Jinja2 environment ────────────────────────────────────────────────────────

_jinja_env = Environment(
    loader=PackageLoader("openguirobot", "action/templates"),
    autoescape=select_autoescape([]),   # no HTML escaping for Python/JSON templates
    keep_trailing_newline=True,
)


# ── Data models ───────────────────────────────────────────────────────────────

class PlanStep(BaseModel):
    index:         int
    intent:        str
    rollback_hint: str


class Plan(BaseModel):
    steps:       list[PlanStep]
    total_steps: int


class CodegenResult(BaseModel):
    code:                 str
    expected_observation: str
    rollback_hint:        str


class PlanGenerationError(RuntimeError):
    pass


class CodegenError(RuntimeError):
    pass


# ── DOM summarizer ────────────────────────────────────────────────────────────

_MAX_NODES = 50


def _summarize_dom(dom: DomTree, max_nodes: int = _MAX_NODES) -> tuple[str, int]:
    """
    Return (summary_text, node_count) for the first *max_nodes* DOM nodes.
    Each line: [idx] class="..." text="..." resource_id="..." bounds="(x1,y1,x2,y2)"
    """
    nodes = dom.all_nodes()
    total = len(nodes)
    lines: list[str] = []
    for i, node in enumerate(nodes[:max_nodes]):
        x1, y1, x2, y2 = node.bounds
        lines.append(
            f'[{i + 1}] class="{node.class_name}" '
            f'text="{node.text}" '
            f'resource_id="{node.resource_id}" '
            f'content_desc="{node.content_desc}" '
            f'bounds="({x1},{y1},{x2},{y2})"'
        )
    if total > max_nodes:
        lines.append(f"... ({total - max_nodes} more nodes omitted)")
    return "\n".join(lines), min(total, max_nodes)


# ── Codegen class ─────────────────────────────────────────────────────────────

class Codegen:
    """Orchestrates Plan generation and per-step code generation via LLM."""

    def __init__(self, llm: LLMClient, evidence: "EvidenceWriter") -> None:
        self._llm = llm
        self._evidence = evidence

    # ── Plan generation ───────────────────────────────────────────────────────

    def plan(
        self,
        case: "TestCase",
        platform: str,
        initial_screenshot: bytes,   # noqa: ARG002 — reserved for future multi-modal plan
        initial_dom: DomTree,
    ) -> Plan:
        dom_summary, _ = _summarize_dom(initial_dom)
        template = _jinja_env.get_template("plan.j2")
        prompt_text = template.render(
            case_id=case.case_id,
            intent=case.intent,
            platform=platform,
            current_state_description=dom_summary,
        )
        messages = [Message(role="user", content=prompt_text)]

        raw = self._call_llm(messages, step=0, context="plan")
        try:
            return Plan.model_validate(json.loads(raw))
        except Exception as exc:
            raise PlanGenerationError(
                f"Failed to parse plan from LLM response: {exc}\nResponse: {raw[:500]}"
            ) from exc

    # ── Per-step codegen ──────────────────────────────────────────────────────

    def gen_step(
        self,
        step: PlanStep,
        case: "TestCase",
        platform: str,
        dom: DomTree,
        previous_result: str,
        step_index: int,
        total_steps: int,
    ) -> CodegenResult:
        dom_summary, node_count = _summarize_dom(dom)
        template = _jinja_env.get_template("codegen_step.j2")
        prompt_text = template.render(
            case_id=case.case_id,
            step_index=step_index,
            total_steps=total_steps,
            step_intent=step.intent,
            platform=platform,
            dom_summary=dom_summary,
            dom_node_count=node_count,
            previous_result=previous_result,
        )
        messages = [Message(role="user", content=prompt_text)]

        raw = self._call_llm(messages, step=step_index, context="codegen")
        try:
            return CodegenResult.model_validate(json.loads(raw))
        except Exception as exc:
            raise CodegenError(
                f"Failed to parse codegen result for step {step_index}: {exc}\nResponse: {raw[:500]}"
            ) from exc

    # ── Internal LLM call with evidence logging ───────────────────────────────

    def _call_llm(self, messages: list[Message], step: int, context: str) -> str:
        completion = self._llm.chat(messages)
        self._evidence.write_llm_call(
            step,
            {
                "ts":         datetime.now(tz=timezone.utc).isoformat(),
                "context":    context,
                "model":      completion.model,
                "tokens_in":  completion.tokens_in,
                "tokens_out": completion.tokens_out,
                "cost_usd":   completion.cost_usd,
                "latency_ms": completion.latency_ms,
            },
        )
        return completion.content
