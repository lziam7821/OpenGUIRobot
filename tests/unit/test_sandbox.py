"""Unit tests for action/sandbox.py."""
from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from openguirobot.action.sandbox import (
    Sandbox,
    SandboxConfig,
    SandboxResult,
    _run_subprocess,
)


# ── AST guard pre-flight ───────────────────────────────────────────────────────

def test_ast_violation_returns_error_without_subprocess():
    sandbox = Sandbox(SandboxConfig(tier=0))
    with patch("openguirobot.action.sandbox._run_subprocess") as mock_run:
        result = sandbox.run_step("eval('1+1')", {"platform": "android", "device_id": ""})
    assert result.returncode == -2
    assert result.exception == "ASTGuardError"
    mock_run.assert_not_called()


# ── Tier 0 (direct) ───────────────────────────────────────────────────────────

def test_tier0_calls_direct():
    sandbox = Sandbox(SandboxConfig(tier=0))
    mock_result = SandboxResult(returncode=0, stdout='{"ok":true}', stderr="",
                                timed_out=False, exception=None)
    with patch("openguirobot.action.sandbox._run_subprocess", return_value=mock_result) as m:
        result = sandbox.run_step("s.tap(locate('x'))", {"platform": "android", "device_id": ""})
    assert result.ok
    called_cmd = m.call_args[0][0]
    assert sys.executable in called_cmd


# ── Tier 1 Linux (bwrap) ──────────────────────────────────────────────────────

def test_tier1_linux_uses_bwrap():
    sandbox = Sandbox(SandboxConfig(tier=1))
    mock_result = SandboxResult(returncode=0, stdout='{"ok":true}', stderr="",
                                timed_out=False, exception=None)
    with patch("sys.platform", "linux"), \
         patch("openguirobot.action.sandbox._run_subprocess", return_value=mock_result) as m, \
         patch("openguirobot.action.sandbox._tier1_unavailable", return_value=False):
        result = sandbox.run_step("s.tap(locate('btn'))", {"platform": "android", "device_id": ""})
    cmd = m.call_args[0][0]
    assert "bwrap" in cmd


# ── Tier 1 macOS (sandbox-exec) ───────────────────────────────────────────────

def test_tier1_macos_uses_sandbox_exec():
    sandbox = Sandbox(SandboxConfig(tier=1))
    mock_result = SandboxResult(returncode=0, stdout='{"ok":true}', stderr="",
                                timed_out=False, exception=None)
    with patch("sys.platform", "darwin"), \
         patch("openguirobot.action.sandbox._run_subprocess", return_value=mock_result) as m, \
         patch("openguirobot.action.sandbox._tier1_unavailable", return_value=False):
        result = sandbox.run_step("s.tap(locate('btn'))", {"platform": "android", "device_id": ""})
    cmd = m.call_args[0][0]
    assert "sandbox-exec" in cmd


# ── Tier 1 falls back to direct when unavailable ──────────────────────────────

def test_tier1_falls_back_when_bwrap_missing():
    sandbox = Sandbox(SandboxConfig(tier=1))
    mock_result = SandboxResult(returncode=0, stdout='{"ok":true}', stderr="",
                                timed_out=False, exception=None)
    with patch("openguirobot.action.sandbox._tier1_unavailable", return_value=True), \
         patch("openguirobot.action.sandbox._run_subprocess", return_value=mock_result) as m:
        result = sandbox.run_step("s.tap(locate('x'))", {"platform": "android", "device_id": ""})
    cmd = m.call_args[0][0]
    # Should fall back to direct Python execution (no bwrap)
    assert "bwrap" not in cmd


# ── Timeout result ─────────────────────────────────────────────────────────────

def test_timed_out_result_not_ok():
    result = SandboxResult(returncode=-1, stdout="", stderr="timed out",
                           timed_out=True, exception="TimeoutExpired")
    assert not result.ok


# ── SandboxResult.ok ──────────────────────────────────────────────────────────

def test_sandbox_result_ok_true():
    r = SandboxResult(returncode=0, stdout="", stderr="", timed_out=False, exception=None)
    assert r.ok is True


def test_sandbox_result_ok_false_nonzero():
    r = SandboxResult(returncode=1, stdout="", stderr="err", timed_out=False, exception=None)
    assert r.ok is False


# ── Script template rendering ─────────────────────────────────────────────────

def test_script_template_contains_context():
    """The sandbox script must embed the context dict."""
    from openguirobot.action.sandbox import _SANDBOX_SCRIPT_TEMPLATE
    rendered = _SANDBOX_SCRIPT_TEMPLATE.format(
        context_json='{"appium_url":"http://localhost:4723"}',
        indented_code="    pass",
    )
    assert "http://localhost:4723" in rendered
    assert "_create_sandbox_session" in rendered
