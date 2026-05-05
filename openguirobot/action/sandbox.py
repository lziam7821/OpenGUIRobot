"""
L2 Action — Sandbox executor (Tier 0 + Tier 1).

Tier 0: AST Guard (always active — see ast_guard.py)
Tier 1: OS-level process isolation
  - Linux: bubblewrap (bwrap)
  - macOS: sandbox-exec with a restrictive profile

The generated code runs inside a subprocess that:
  1. Imports openguirobot.runtime to get session/locate/assert_visual
  2. Executes the LLM-generated code snippet
  3. Reports success/failure as JSON on stdout

The subprocess communicates with Appium over HTTP (network is kept open).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


# ── Result type ────────────────────────────────────────────────────────────────

@dataclass
class SandboxResult:
    returncode: int
    stdout:     str
    stderr:     str
    timed_out:  bool
    exception:  str | None   # exception type if the generated code raised one

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


# ── Config ─────────────────────────────────────────────────────────────────────

@dataclass
class SandboxConfig:
    tier:             int = 1   # 0 = AST only, 1 = bwrap/sandbox-exec
    cpu_limit:        int = 1
    memory_limit_mb:  int = 512
    step_timeout_s:   int = 30
    total_timeout_s:  int = 600


# ── Script template injected into the sandbox subprocess ──────────────────────
# The parent process fills in `context_json` and `generated_code`.
# The subprocess uses exec() only on TRUSTED runtime-setup code,
# while generated code is placed inline in the script file by the parent.

_SANDBOX_SCRIPT_TEMPLATE = """\
import sys, json, os

# ── Runtime bootstrap ──────────────────────────────────────────────────────────
context = {context_json}

_appium_url = context.get("appium_url", "http://localhost:4723")
_device_id  = context.get("device_id", "")
_platform   = context.get("platform", "android")

from openguirobot.runtime import _create_sandbox_session, locate, assert_visual
s = _create_sandbox_session(context)

# ── Generated code ─────────────────────────────────────────────────────────────
_result = {{"ok": False, "error": None}}
try:
{indented_code}
    _result = {{"ok": True}}
except Exception as _exc:
    _result = {{"ok": False, "error": str(_exc), "type": type(_exc).__name__}}
    sys.exit(1)
finally:
    print(json.dumps(_result), flush=True)
"""

_BWRAP_BASE_ARGS = [
    "bwrap",
    "--proc", "/proc",
    "--dev",  "/dev",
    "--tmpfs", "/tmp",
    "--unshare-all",
    "--share-net",      # keep network: Appium REST + vision model APIs
    "--die-with-parent",
]


# ── Sandbox class ──────────────────────────────────────────────────────────────

class Sandbox:
    """Execute LLM-generated code in a sandboxed subprocess."""

    def __init__(self, config: SandboxConfig | None = None) -> None:
        self._config = config or SandboxConfig()

    def run_step(self, code: str, context: dict[str, Any]) -> SandboxResult:
        """
        Validate *code* via ASTGuard, then execute it in a sandboxed subprocess.

        *context* must contain at minimum:
          - appium_url: str
          - device_id:  str
          - platform:   str  ("android" | "ios")
        """
        from openguirobot.action.ast_guard import ASTGuard, ASTGuardError

        # Tier 0: static AST check (always, regardless of tier setting)
        try:
            ASTGuard.validate(code)
        except ASTGuardError as exc:
            return SandboxResult(
                returncode=-2,
                stdout="",
                stderr=str(exc),
                timed_out=False,
                exception="ASTGuardError",
            )

        # Build the script
        indented = "\n".join(f"    {line}" for line in code.splitlines())
        script_text = _SANDBOX_SCRIPT_TEMPLATE.format(
            context_json=json.dumps(context),
            indented_code=indented,
        )

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(script_text)
            script_path = f.name

        try:
            if self._config.tier == 0 or _tier1_unavailable():
                return self._run_direct(script_path)
            elif sys.platform == "linux":
                return self._run_bwrap(script_path)
            elif sys.platform == "darwin":
                return self._run_sandbox_exec(script_path)
            else:
                # Fallback: direct execution on unsupported platforms
                return self._run_direct(script_path)
        finally:
            try:
                os.unlink(script_path)
            except OSError:
                pass

    # ── Execution backends ─────────────────────────────────────────────────────

    def _run_direct(self, script_path: str) -> SandboxResult:
        """Tier 0: run directly (AST-checked only, no OS isolation)."""
        return _run_subprocess([sys.executable, script_path], self._config.step_timeout_s)

    def _run_bwrap(self, script_path: str) -> SandboxResult:
        """Tier 1 Linux: run inside bubblewrap."""
        import shutil

        # Bind the current Python prefix (venv) read-only inside the sandbox
        prefix = Path(sys.prefix)
        extra_binds: list[str] = []
        for path in _ro_bind_paths(prefix):
            if path.exists():
                extra_binds += ["--ro-bind", str(path), str(path)]

        # Bind the script's temp directory
        tmp_dir = str(Path(script_path).parent)
        extra_binds += ["--bind", tmp_dir, tmp_dir]

        # Bind system libraries
        sys_binds: list[str] = []
        for sysdir in ["/usr", "/lib", "/lib64", "/lib32"]:
            if Path(sysdir).exists():
                sys_binds += ["--ro-bind", sysdir, sysdir]

        cmd = [
            *_BWRAP_BASE_ARGS,
            *sys_binds,
            *extra_binds,
            sys.executable, script_path,
        ]
        return _run_subprocess(cmd, self._config.step_timeout_s)

    def _run_sandbox_exec(self, script_path: str) -> SandboxResult:
        """Tier 1 macOS: run inside sandbox-exec with restrictive profile."""
        profile_path = (
            Path(__file__).parent / "sandbox_profiles" / "macos_default.sb"
        )
        cmd = [
            "sandbox-exec",
            "-f", str(profile_path),
            sys.executable, script_path,
        ]
        return _run_subprocess(cmd, self._config.step_timeout_s)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _run_subprocess(cmd: list[str], timeout_s: int) -> SandboxResult:
    try:
        proc = subprocess.run(
            cmd,
            timeout=timeout_s,
            capture_output=True,
            text=True,
            env=os.environ.copy(),  # inherit API keys etc.
        )
        exception = None
        if proc.returncode != 0:
            # Try to extract exception type from JSON output
            try:
                data = json.loads(proc.stdout)
                exception = data.get("type")
            except (json.JSONDecodeError, AttributeError):
                pass
        return SandboxResult(
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            timed_out=False,
            exception=exception,
        )
    except subprocess.TimeoutExpired:
        return SandboxResult(
            returncode=-1,
            stdout="",
            stderr=f"Step timed out after {timeout_s}s",
            timed_out=True,
            exception="TimeoutExpired",
        )


def _ro_bind_paths(prefix: Path) -> list[Path]:
    """Return paths inside the Python prefix that should be ro-bound in bwrap."""
    candidates = [
        prefix,
        prefix / "lib",
        prefix / "lib64",
        prefix / "bin",
        prefix / "include",
    ]
    return [p for p in candidates if p.exists()]


def _tier1_unavailable() -> bool:
    """Return True if Tier 1 sandbox is not available on this system."""
    import shutil

    if sys.platform == "linux":
        return shutil.which("bwrap") is None
    if sys.platform == "darwin":
        return shutil.which("sandbox-exec") is None
    return True
