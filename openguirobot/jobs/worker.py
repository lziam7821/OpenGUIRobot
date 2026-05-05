"""
L5 — Arq worker: async task queue for codegen and assertion jobs.

Supports two backends selected by the OGR_JOBS_BACKEND environment variable:

  inproc  (default) — tasks run in the same process, no Redis required.
                       Suitable for single-machine development and CI.
  arq     — full Arq worker with Redis broker (production multi-device setup).

The inproc backend is intentionally minimal: it executes tasks synchronously
inside an asyncio event loop, making it easy to test without any infrastructure.

Redis/Arq backend is a thin wrapper that delegates to the arq library.
Full multi-device parallelism is planned for v0.3.

Task signatures
---------------
codegen_task(ctx, case_id, step_intent, platform, llm_provider)
    Generates Python code for one step.  Returns {"code": str, "cost_usd": float}.

assert_task(ctx, case_id, step_index, screenshot_b64)
    Runs assertions for one step.  Returns {"results": list[dict]}.
"""
from __future__ import annotations

import asyncio
import base64
import os
from typing import Any


# ── Backend selection ──────────────────────────────────────────────────────────

_BACKEND = os.environ.get("OGR_JOBS_BACKEND", "inproc").lower()


# ── Task implementations ───────────────────────────────────────────────────────

async def codegen_task(
    ctx: dict[str, Any],
    case_id: str,
    step_intent: str,
    platform: str = "android",
    llm_provider: str | None = None,
) -> dict[str, Any]:
    """
    Generate Python code for a single test step.

    This is an Arq-compatible coroutine: the first parameter ``ctx`` is the
    Arq job context (worker metadata), which is ignored in inproc mode.

    Returns:
        {"code": str, "cost_usd": float, "case_id": str}
    """
    # In v0.2, this is a stub that returns a placeholder.
    # Full codegen integration with the Action layer is wired in v0.3.
    return {
        "case_id":    case_id,
        "step_intent": step_intent,
        "platform":   platform,
        "code":       f"# codegen stub for: {step_intent}",
        "cost_usd":   0.0,
        "status":     "stub",
    }


async def assert_task(
    ctx: dict[str, Any],
    case_id: str,
    step_index: int,
    screenshot_b64: str = "",
) -> dict[str, Any]:
    """
    Run assertions for a completed test step.

    Args:
        ctx:            Arq job context (ignored in inproc mode).
        case_id:        Case identifier.
        step_index:     Which step this assertion applies to.
        screenshot_b64: Base64-encoded PNG screenshot bytes (may be empty in stub).

    Returns:
        {"results": list[dict], "case_id": str, "step_index": int}
    """
    screenshot: bytes = base64.b64decode(screenshot_b64) if screenshot_b64 else b""

    # Stub: real assertion dispatch will be wired in v0.3
    return {
        "case_id":    case_id,
        "step_index": step_index,
        "screenshot_len": len(screenshot),
        "results":    [],
        "status":     "stub",
    }


# ── WorkerSettings for Arq backend ────────────────────────────────────────────

class WorkerSettings:
    """
    Arq WorkerSettings — used when OGR_JOBS_BACKEND=arq.

    The Redis URL is read from the OGR_REDIS_URL environment variable
    (default: redis://localhost:6379).
    """
    functions = [codegen_task, assert_task]
    queue_name = "ogr:jobs"

    @classmethod
    def redis_settings(cls) -> Any:
        try:
            from arq.connections import RedisSettings  # type: ignore[import]
            redis_url = os.environ.get("OGR_REDIS_URL", "redis://localhost:6379")
            return RedisSettings.from_dsn(redis_url)
        except ImportError:
            return None


# ── InProc runner ──────────────────────────────────────────────────────────────

class InProcRunner:
    """
    Synchronous in-process task runner.  No Redis, no extra processes.

    Used when OGR_JOBS_BACKEND=inproc (the default).

    Usage::

        runner = InProcRunner()
        result = runner.run(codegen_task, case_id="my.case", step_intent="tap login")
    """

    def run(self, func: Any, **kwargs: Any) -> Any:
        """Run an async task coroutine synchronously."""
        ctx: dict[str, Any] = {}
        return asyncio.run(func(ctx, **kwargs))

    def enqueue(self, func: Any, **kwargs: Any) -> Any:
        """Alias for run() — in inproc mode, tasks are always executed immediately."""
        return self.run(func, **kwargs)


# ── Arq enqueue helper ────────────────────────────────────────────────────────

async def enqueue(func: Any, **kwargs: Any) -> Any:
    """
    Enqueue a task on the configured backend.

    - inproc: runs immediately in the current event loop
    - arq:    enqueues to Redis and returns a job ID

    Usage::

        result = await enqueue(codegen_task, case_id="...", step_intent="...")
    """
    if _BACKEND == "arq":
        try:
            from arq import create_pool  # type: ignore[import]
            settings = WorkerSettings.redis_settings()
            pool = await create_pool(settings)
            job = await pool.enqueue_job(func.__name__, **kwargs)
            return job
        except ImportError as exc:
            raise ImportError(
                "arq package is required for OGR_JOBS_BACKEND=arq. "
                "Install with: pip install openguirobot[jobs]"
            ) from exc
    else:
        # inproc: run immediately
        ctx: dict[str, Any] = {}
        return await func(ctx, **kwargs)


# ── Module-level convenience ───────────────────────────────────────────────────

def get_runner() -> InProcRunner:
    """Return an InProcRunner (only valid when OGR_JOBS_BACKEND=inproc)."""
    if _BACKEND != "inproc":
        raise RuntimeError(
            f"get_runner() is only valid for the inproc backend. "
            f"Current backend: {_BACKEND!r}"
        )
    return InProcRunner()
