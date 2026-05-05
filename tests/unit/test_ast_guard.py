"""Unit tests for action/ast_guard.py — security-critical, target ≥95% coverage."""
from __future__ import annotations

import pytest

from openguirobot.action.ast_guard import ASTGuard, ASTGuardError, _is_allowed


# ── _is_allowed helper ─────────────────────────────────────────────────────────

def test_is_allowed_exact():
    assert _is_allowed("re") is True
    assert _is_allowed("json") is True
    assert _is_allowed("typing") is True
    assert _is_allowed("datetime") is True
    assert _is_allowed("dataclasses") is True


def test_is_allowed_submodule():
    assert _is_allowed("openguirobot.skill.locator") is True
    assert _is_allowed("openguirobot.driver.android") is True
    assert _is_allowed("openguirobot.runtime") is True


def test_is_allowed_rejected():
    assert _is_allowed("os") is False
    assert _is_allowed("subprocess") is False
    assert _is_allowed("requests") is False
    assert _is_allowed("socket") is False
    assert _is_allowed("pathlib") is False


# ── Banned builtins — direct call ──────────────────────────────────────────────

@pytest.mark.parametrize("builtin", ["eval", "exec", "compile", "__import__", "open"])
def test_banned_builtin_direct_call(builtin):
    with pytest.raises(ASTGuardError, match=builtin):
        ASTGuard.validate(f"{builtin}('hello')")


# ── Banned builtins — attribute call ──────────────────────────────────────────

def test_banned_builtin_attribute_call():
    with pytest.raises(ASTGuardError, match="eval"):
        ASTGuard.validate("builtins.eval('1+1')")


# ── Banned builtins — bare name reference ─────────────────────────────────────

def test_banned_builtin_bare_reference_eval():
    with pytest.raises(ASTGuardError, match="eval"):
        ASTGuard.validate("f = eval")


def test_banned_builtin_bare_reference_open():
    with pytest.raises(ASTGuardError, match="open"):
        ASTGuard.validate("x = open")


# ── Disallowed imports ─────────────────────────────────────────────────────────

def test_disallowed_import_os():
    with pytest.raises(ASTGuardError, match="os"):
        ASTGuard.validate("import os")


def test_disallowed_import_subprocess():
    with pytest.raises(ASTGuardError, match="subprocess"):
        ASTGuard.validate("import subprocess")


def test_disallowed_from_import():
    with pytest.raises(ASTGuardError, match="pathlib"):
        ASTGuard.validate("from pathlib import Path")


def test_disallowed_import_requests():
    with pytest.raises(ASTGuardError, match="requests"):
        ASTGuard.validate("import requests")


# ── Allowed code ───────────────────────────────────────────────────────────────

def test_allowed_simple_tap():
    ASTGuard.validate("s.tap(locate('搜索入口'))")


def test_allowed_import_re():
    ASTGuard.validate("import re")


def test_allowed_import_json():
    ASTGuard.validate("import json")


def test_allowed_from_openguirobot():
    ASTGuard.validate("from openguirobot.skill.locator import locate")


def test_allowed_from_runtime():
    ASTGuard.validate("from openguirobot.runtime import locate")


def test_allowed_multiline():
    code = """
s.launch_app('com.example.app')
s.tap(locate('搜索框'))
s.input_text('无线耳机')
s.press_key('ENTER')
"""
    ASTGuard.validate(code)


# ── Syntax error ───────────────────────────────────────────────────────────────

def test_syntax_error():
    with pytest.raises(ASTGuardError, match="Syntax error"):
        ASTGuard.validate("def foo(:")


# ── Empty code ─────────────────────────────────────────────────────────────────

def test_empty_code_is_valid():
    ASTGuard.validate("")   # should not raise
    ASTGuard.validate("# just a comment")
