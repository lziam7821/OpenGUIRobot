"""
L3 Memory — Knowledge Base (KB) schema, linting, and validation.

KB files are Markdown documents with a YAML front matter block.
Files live under docs/kb/:
  L0/  ≤ 200 lines   (glossary, recent failures — fast-path for LLM context)
  L1/  ≤ 2 000 lines (module overviews)
  L2/  unlimited     (full case flows, screenshots)

Front matter schema (all fields optional except module + case)::

    ---
    module: shopping_cart
    case: add_to_cart
    last_verified: 2026-05-01
    verified_versions: [Android 8.12]
    confidence: high
    owners: [team]
    tags: [p0, e-commerce]
    ---

The `ogr kb lint` command validates:
  - YAML front matter is parseable and contains required fields
  - L0 files do not exceed 200 lines
  - L1 files do not exceed 2 000 lines
  - confidence is one of: high | medium | low
  - last_verified is an ISO date string (YYYY-MM-DD)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator


# ── Front-matter model ─────────────────────────────────────────────────────────

class KBFrontMatter(BaseModel):
    """
    Pydantic model for the YAML front matter of a KB document.

    Only `module` and `case` are required; all other fields are optional
    but validated when present.
    """
    module:            str
    case:              str
    last_verified:     date | None = None
    verified_versions: list[str]   = Field(default_factory=list)
    confidence:        Literal["high", "medium", "low"] | None = None
    owners:            list[str]   = Field(default_factory=list)
    tags:              list[str]   = Field(default_factory=list)

    @field_validator("last_verified", mode="before")
    @classmethod
    def parse_date(cls, v: object) -> object:
        if isinstance(v, str):
            # Let Pydantic parse as date from ISO string
            return v
        return v


# ── Lint result types ──────────────────────────────────────────────────────────

@dataclass
class LintViolation:
    file:     Path
    line:     int | None
    message:  str
    severity: Literal["error", "warning"] = "error"


@dataclass
class LintReport:
    violations:  list[LintViolation] = field(default_factory=list)
    files_checked: int = 0

    @property
    def has_errors(self) -> bool:
        return any(v.severity == "error" for v in self.violations)

    @property
    def has_warnings(self) -> bool:
        return any(v.severity == "warning" for v in self.violations)

    def add(self, violation: LintViolation) -> None:
        self.violations.append(violation)


# ── Tier line limits ───────────────────────────────────────────────────────────

_TIER_LIMITS: dict[str, int | None] = {
    "L0": 200,
    "L1": 2000,
    "L2": None,   # unlimited
}

_FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n?", re.DOTALL)


# ── Core parsing ──────────────────────────────────────────────────────────────

def _detect_tier(path: Path, kb_root: Path) -> str | None:
    """Return 'L0', 'L1', or 'L2' based on the file's location under kb_root."""
    try:
        relative = path.relative_to(kb_root)
        parts = relative.parts
        if parts and parts[0] in _TIER_LIMITS:
            return parts[0]
    except ValueError:
        pass
    return None


def parse_front_matter(content: str) -> tuple[KBFrontMatter | None, str | None]:
    """
    Extract and parse the YAML front matter from a Markdown file.

    Returns:
        (KBFrontMatter, None)     on success
        (None, error_message)     on failure
    """
    m = _FRONT_MATTER_RE.match(content)
    if not m:
        return None, "Missing YAML front matter (expected '---' block at top of file)"

    raw_yaml = m.group(1)
    try:
        data = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError as exc:
        return None, f"YAML parse error: {exc}"

    if not isinstance(data, dict):
        return None, "Front matter must be a YAML mapping"

    try:
        fm = KBFrontMatter.model_validate(data)
    except Exception as exc:  # noqa: BLE001
        return None, f"Front matter validation error: {exc}"

    return fm, None


# ── File linter ────────────────────────────────────────────────────────────────

def lint_file(path: Path, kb_root: Path, strict: bool = False) -> list[LintViolation]:
    """
    Lint a single KB Markdown file.

    Checks:
      1. File is readable and is a .md file
      2. Front matter is present and valid
      3. Required fields: module, case
      4. Line count within tier limit
      5. (strict) confidence field is present
      6. (strict) last_verified field is present

    Args:
        path:    Absolute path to the file.
        kb_root: Root of the KB tree (parent of L0/, L1/, L2/).
        strict:  If True, also error on missing optional-but-recommended fields.

    Returns:
        List of LintViolation (empty = clean).
    """
    violations: list[LintViolation] = []

    if path.suffix.lower() != ".md":
        return violations  # ignore non-markdown files

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(LintViolation(file=path, line=None, message=f"Cannot read file: {exc}"))
        return violations

    total_lines = content.count("\n") + (0 if content.endswith("\n") else 1)

    # ── Front matter ──────────────────────────────────────────────────────────
    fm, err = parse_front_matter(content)
    if err:
        violations.append(LintViolation(file=path, line=1, message=err))
        return violations  # can't check further without valid front matter

    # ── Tier line limit ───────────────────────────────────────────────────────
    tier = _detect_tier(path, kb_root)
    if tier is not None:
        limit = _TIER_LIMITS.get(tier)
        if limit is not None and total_lines > limit:
            violations.append(LintViolation(
                file=path,
                line=limit + 1,
                message=(
                    f"{tier} files must not exceed {limit} lines "
                    f"(this file has {total_lines} lines)"
                ),
                severity="error",
            ))

    # ── Strict checks ─────────────────────────────────────────────────────────
    if strict:
        if fm.confidence is None:
            violations.append(LintViolation(
                file=path, line=None,
                message="Missing recommended field: 'confidence' (high|medium|low)",
                severity="warning" if not strict else "error",
            ))
        if fm.last_verified is None:
            violations.append(LintViolation(
                file=path, line=None,
                message="Missing recommended field: 'last_verified' (YYYY-MM-DD)",
                severity="warning" if not strict else "error",
            ))

    return violations


# ── Directory linter ───────────────────────────────────────────────────────────

def lint_kb(kb_root: Path, strict: bool = False) -> LintReport:
    """
    Recursively lint all Markdown files under *kb_root*.

    Args:
        kb_root: Root directory containing L0/, L1/, L2/ subdirectories.
        strict:  Propagated to lint_file(); also errors on missing optional fields.

    Returns:
        LintReport with all violations and the count of files checked.
    """
    report = LintReport()

    if not kb_root.is_dir():
        report.add(LintViolation(
            file=kb_root, line=None,
            message=f"KB root directory does not exist: {kb_root}",
        ))
        return report

    md_files = sorted(kb_root.rglob("*.md"))
    report.files_checked = len(md_files)

    for md_file in md_files:
        violations = lint_file(md_file, kb_root, strict=strict)
        for v in violations:
            report.add(v)

    return report
