"""
L2 Action — AST Guard (Tier 0 sandbox).

Performs static analysis of LLM-generated code before execution:
  - Validates imports against the allowed whitelist
  - Detects calls to banned builtins (eval, exec, compile, __import__, open)
  - Catches syntax errors early

This is a security-critical module. Coverage target: ≥95%.
"""
from __future__ import annotations

import ast

# ── Allowlist / blocklist ─────────────────────────────────────────────────────

ALLOWED_IMPORT_PREFIXES: frozenset[str] = frozenset(
    {
        "openguirobot.skill",
        "openguirobot.skills",   # alias used in generated code
        "openguirobot.driver",
        "openguirobot.runtime",  # session, locate, assert_visual
        "re",
        "json",
        "typing",
        "datetime",
        "dataclasses",
    }
)

BANNED_BUILTINS: frozenset[str] = frozenset(
    {"eval", "exec", "compile", "__import__", "open"}
)


# ── Exceptions ────────────────────────────────────────────────────────────────

class ASTGuardError(ValueError):
    """Raised when generated code violates the security policy."""


# ── Validator ─────────────────────────────────────────────────────────────────

class ASTGuard:
    """Static code validator — raises ASTGuardError on any policy violation."""

    @staticmethod
    def validate(code: str) -> None:
        """
        Parse *code* and walk the AST, raising ASTGuardError on the first violation.

        Checks:
        1. Syntax validity
        2. All ``import`` / ``from … import`` statements are in the allowlist
        3. No calls or references to banned builtins
        """
        try:
            tree = ast.parse(code, mode="exec")
        except SyntaxError as exc:
            raise ASTGuardError(f"Syntax error in generated code: {exc}") from exc

        for node in ast.walk(tree):
            ASTGuard._check_import(node)
            ASTGuard._check_call(node)
            ASTGuard._check_name(node)

    # ── Private checks ────────────────────────────────────────────────────────

    @staticmethod
    def _check_import(node: ast.AST) -> None:
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _is_allowed(alias.name):
                    raise ASTGuardError(
                        f"Disallowed import: {alias.name!r}. "
                        f"Allowed prefixes: {sorted(ALLOWED_IMPORT_PREFIXES)}"
                    )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if not _is_allowed(module):
                raise ASTGuardError(
                    f"Disallowed 'from … import': {module!r}. "
                    f"Allowed prefixes: {sorted(ALLOWED_IMPORT_PREFIXES)}"
                )

    @staticmethod
    def _check_call(node: ast.AST) -> None:
        if not isinstance(node, ast.Call):
            return
        func = node.func
        # Direct call: eval(...), exec(...), etc.
        if isinstance(func, ast.Name) and func.id in BANNED_BUILTINS:
            raise ASTGuardError(f"Banned builtin call: {func.id!r}")
        # Attribute call: builtins.eval(...), __builtins__['exec'](...) style
        if isinstance(func, ast.Attribute) and func.attr in BANNED_BUILTINS:
            raise ASTGuardError(f"Banned builtin via attribute: {func.attr!r}")

    @staticmethod
    def _check_name(node: ast.AST) -> None:
        """Catch bare references to banned names (e.g. assigning eval to a variable)."""
        if (
            isinstance(node, ast.Name)
            and node.id in BANNED_BUILTINS
            and isinstance(node.ctx, ast.Load)
        ):
            raise ASTGuardError(f"Reference to banned builtin: {node.id!r}")


# ── Helper ─────────────────────────────────────────────────────────────────────

def _is_allowed(module: str) -> bool:
    """Return True if *module* starts with any allowed prefix."""
    for prefix in ALLOWED_IMPORT_PREFIXES:
        if module == prefix or module.startswith(prefix + "."):
            return True
    return False
