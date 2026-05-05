"""Unit tests for obs/evidence.py."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from openguirobot.obs.evidence import EvidenceWriter


@pytest.fixture
def writer(tmp_path):
    return EvidenceWriter("test.case", run_id="20260501T000000Z", base_dir=tmp_path)


def test_run_dir_created(writer, tmp_path):
    assert (tmp_path / "test.case" / "20260501T000000Z").is_dir()


def test_write_screenshot_before(writer):
    path = writer.write_screenshot(1, "before", b"\x89PNG")
    assert path.name == "step-001-before.png"
    assert path.read_bytes() == b"\x89PNG"


def test_write_screenshot_after(writer):
    path = writer.write_screenshot(3, "after", b"data")
    assert path.name == "step-003-after.png"


def test_write_dom(writer):
    path = writer.write_dom(2, "<hierarchy/>")
    assert path.name == "step-002-dom.xml"
    assert path.read_text() == "<hierarchy/>"


def test_write_llm_call_single(writer):
    writer.write_llm_call(1, {"model": "claude", "cost_usd": 0.001})
    path = writer.run_dir / "step-001-llm.jsonl"
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["model"] == "claude"


def test_write_llm_call_appends(writer):
    writer.write_llm_call(1, {"model": "a"})
    writer.write_llm_call(1, {"model": "b"})
    path = writer.run_dir / "step-001-llm.jsonl"
    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["model"] == "b"


def test_write_summary(writer):
    steps = [{"index": 1, "status": "ok"}, {"index": 2, "status": "ok"}]
    path = writer.write_summary(steps, total_time_s=12.5, total_cost_usd=0.042)
    data = json.loads(path.read_text())
    assert data["case_id"] == "test.case"
    assert data["total_time_s"] == 12.5
    assert data["step_count"] == 2
    assert len(data["steps"]) == 2


def test_step_zero_prefix(writer):
    """Step 0 is used for plan-phase LLM calls."""
    writer.write_llm_call(0, {"model": "m"})
    path = writer.run_dir / "step-000-llm.jsonl"
    assert path.exists()


def test_run_id_property(writer):
    assert writer.run_id == "20260501T000000Z"
