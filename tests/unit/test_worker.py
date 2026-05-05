"""Unit tests for jobs/worker.py."""
from __future__ import annotations

import asyncio
import os
from unittest.mock import patch

import pytest

from openguirobot.jobs.worker import (
    InProcRunner,
    WorkerSettings,
    assert_task,
    codegen_task,
    enqueue,
    get_runner,
)


# ── codegen_task ───────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_codegen_task_returns_dict():
    ctx: dict = {}
    result = await codegen_task(ctx, case_id="my.case", step_intent="tap login button")
    assert isinstance(result, dict)
    assert result["case_id"] == "my.case"
    assert result["step_intent"] == "tap login button"
    assert "code" in result
    assert "cost_usd" in result
    assert isinstance(result["cost_usd"], float)


@pytest.mark.asyncio
async def test_codegen_task_default_platform():
    ctx: dict = {}
    result = await codegen_task(ctx, case_id="c", step_intent="x")
    assert result["platform"] == "android"


@pytest.mark.asyncio
async def test_codegen_task_custom_platform():
    ctx: dict = {}
    result = await codegen_task(ctx, case_id="c", step_intent="x", platform="ios")
    assert result["platform"] == "ios"


# ── assert_task ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_assert_task_returns_dict():
    ctx: dict = {}
    result = await assert_task(ctx, case_id="my.case", step_index=3)
    assert isinstance(result, dict)
    assert result["case_id"] == "my.case"
    assert result["step_index"] == 3
    assert "results" in result
    assert isinstance(result["results"], list)


@pytest.mark.asyncio
async def test_assert_task_decodes_screenshot():
    import base64

    ctx: dict = {}
    fake_png = b"\x89PNG\r\n"
    b64 = base64.b64encode(fake_png).decode()
    result = await assert_task(ctx, case_id="c", step_index=1, screenshot_b64=b64)
    assert result["screenshot_len"] == len(fake_png)


@pytest.mark.asyncio
async def test_assert_task_empty_screenshot():
    ctx: dict = {}
    result = await assert_task(ctx, case_id="c", step_index=1, screenshot_b64="")
    assert result["screenshot_len"] == 0


# ── InProcRunner ───────────────────────────────────────────────────────────────

def test_inproc_runner_run():
    runner = InProcRunner()
    result = runner.run(codegen_task, case_id="x", step_intent="tap")
    assert result["case_id"] == "x"


def test_inproc_runner_enqueue_same_as_run():
    runner = InProcRunner()
    r1 = runner.run(codegen_task, case_id="a", step_intent="y")
    r2 = runner.enqueue(codegen_task, case_id="a", step_intent="y")
    assert r1["case_id"] == r2["case_id"]


# ── get_runner ─────────────────────────────────────────────────────────────────

def test_get_runner_returns_inproc():
    with patch.dict(os.environ, {"OGR_JOBS_BACKEND": "inproc"}):
        # Re-import to pick up env var (module-level _BACKEND is cached,
        # so we test the function directly)
        runner = get_runner()
        assert isinstance(runner, InProcRunner)


def test_get_runner_raises_for_arq_backend():
    # Temporarily pretend the backend is arq
    import openguirobot.jobs.worker as worker_mod
    original = worker_mod._BACKEND
    worker_mod._BACKEND = "arq"
    try:
        with pytest.raises(RuntimeError, match="inproc"):
            get_runner()
    finally:
        worker_mod._BACKEND = original


# ── enqueue (inproc path) ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_enqueue_inproc_runs_immediately():
    import openguirobot.jobs.worker as worker_mod
    original = worker_mod._BACKEND
    worker_mod._BACKEND = "inproc"
    try:
        result = await enqueue(codegen_task, case_id="enqueue.test", step_intent="tap")
        assert result["case_id"] == "enqueue.test"
    finally:
        worker_mod._BACKEND = original


# ── WorkerSettings ─────────────────────────────────────────────────────────────

def test_worker_settings_functions():
    assert codegen_task in WorkerSettings.functions
    assert assert_task in WorkerSettings.functions


def test_worker_settings_queue_name():
    assert WorkerSettings.queue_name == "ogr:jobs"


def test_worker_settings_redis_settings_no_arq():
    """When arq is not installed, redis_settings() should return None gracefully."""
    import sys
    orig = sys.modules.get("arq")
    orig_conn = sys.modules.get("arq.connections")
    sys.modules["arq"] = None  # type: ignore[assignment]
    sys.modules["arq.connections"] = None  # type: ignore[assignment]
    try:
        result = WorkerSettings.redis_settings()
        assert result is None
    finally:
        if orig is None:
            sys.modules.pop("arq", None)
        else:
            sys.modules["arq"] = orig
        if orig_conn is None:
            sys.modules.pop("arq.connections", None)
        else:
            sys.modules["arq.connections"] = orig_conn
