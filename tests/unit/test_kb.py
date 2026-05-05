"""Unit tests for memory/kb.py."""
from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest

from openguirobot.memory.kb import (
    KBFrontMatter,
    LintReport,
    LintViolation,
    lint_file,
    lint_kb,
    parse_front_matter,
)


# ── Fixtures ───────────────────────────────────────────────────────────────────

VALID_FM = dedent("""\
    ---
    module: shopping_cart
    case: add_to_cart
    last_verified: 2026-05-01
    verified_versions: [Android 8.12]
    confidence: high
    owners: [team]
    tags: [p0, e-commerce]
    ---

    # Overview

    This document describes the add_to_cart flow.
    """)

MINIMAL_FM = dedent("""\
    ---
    module: auth
    case: login
    ---

    # Login flow
    """)

MISSING_FM = "# No front matter here\n\nJust content.\n"

BAD_YAML_FM = dedent("""\
    ---
    module: [broken
    case: oops
    ---

    Content.
    """)

WRONG_CONFIDENCE = dedent("""\
    ---
    module: auth
    case: login
    confidence: super_high
    ---

    Content.
    """)


# ── KBFrontMatter model ────────────────────────────────────────────────────────

def test_kb_front_matter_full():
    fm = KBFrontMatter(
        module="shopping_cart",
        case="add_to_cart",
        last_verified="2026-05-01",
        confidence="high",
        owners=["team"],
        tags=["p0"],
    )
    assert fm.module == "shopping_cart"
    assert fm.confidence == "high"
    assert str(fm.last_verified) == "2026-05-01"


def test_kb_front_matter_minimal():
    fm = KBFrontMatter(module="auth", case="login")
    assert fm.last_verified is None
    assert fm.confidence is None
    assert fm.tags == []
    assert fm.owners == []


def test_kb_front_matter_invalid_confidence():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        KBFrontMatter(module="m", case="c", confidence="super_high")  # type: ignore[arg-type]


def test_kb_front_matter_invalid_date():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        KBFrontMatter(module="m", case="c", last_verified="not-a-date")


# ── parse_front_matter ─────────────────────────────────────────────────────────

def test_parse_valid_front_matter():
    fm, err = parse_front_matter(VALID_FM)
    assert err is None
    assert fm is not None
    assert fm.module == "shopping_cart"
    assert fm.case == "add_to_cart"
    assert fm.confidence == "high"


def test_parse_minimal_front_matter():
    fm, err = parse_front_matter(MINIMAL_FM)
    assert err is None
    assert fm is not None
    assert fm.module == "auth"


def test_parse_missing_front_matter():
    fm, err = parse_front_matter(MISSING_FM)
    assert fm is None
    assert err is not None
    assert "front matter" in err.lower() or "---" in err


def test_parse_bad_yaml():
    fm, err = parse_front_matter(BAD_YAML_FM)
    assert fm is None
    assert err is not None
    assert "YAML" in err or "parse" in err.lower()


def test_parse_wrong_confidence():
    fm, err = parse_front_matter(WRONG_CONFIDENCE)
    assert fm is None
    assert err is not None


# ── lint_file ──────────────────────────────────────────────────────────────────

def test_lint_valid_file(tmp_path):
    kb_root = tmp_path / "kb"
    l0 = kb_root / "L0"
    l0.mkdir(parents=True)
    f = l0 / "modules.md"
    f.write_text(VALID_FM)

    violations = lint_file(f, kb_root, strict=False)
    assert violations == []


def test_lint_missing_front_matter(tmp_path):
    kb_root = tmp_path / "kb"
    l0 = kb_root / "L0"
    l0.mkdir(parents=True)
    f = l0 / "bad.md"
    f.write_text(MISSING_FM)

    violations = lint_file(f, kb_root)
    assert len(violations) > 0
    assert any("front matter" in v.message.lower() or "---" in v.message for v in violations)


def test_lint_l0_line_limit(tmp_path):
    """L0 file exceeding 200 lines should produce an error."""
    kb_root = tmp_path / "kb"
    l0 = kb_root / "L0"
    l0.mkdir(parents=True)
    f = l0 / "big.md"
    # Front matter (5 lines) + 200 lines of content = 205 lines
    content = MINIMAL_FM + ("x\n" * 200)
    f.write_text(content)

    violations = lint_file(f, kb_root)
    assert any("200" in v.message or "L0" in v.message for v in violations)


def test_lint_l1_line_limit_ok(tmp_path):
    """L1 file within 2000 lines should pass."""
    kb_root = tmp_path / "kb"
    l1 = kb_root / "L1"
    l1.mkdir(parents=True)
    f = l1 / "overview.md"
    content = MINIMAL_FM + ("x\n" * 100)
    f.write_text(content)

    violations = lint_file(f, kb_root)
    assert violations == []


def test_lint_l1_line_limit_exceeded(tmp_path):
    """L1 file exceeding 2000 lines should produce an error."""
    kb_root = tmp_path / "kb"
    l1 = kb_root / "L1"
    l1.mkdir(parents=True)
    f = l1 / "huge.md"
    content = MINIMAL_FM + ("x\n" * 2001)
    f.write_text(content)

    violations = lint_file(f, kb_root)
    assert any("2000" in v.message or "L1" in v.message for v in violations)


def test_lint_l2_no_line_limit(tmp_path):
    """L2 files have no line limit."""
    kb_root = tmp_path / "kb"
    l2 = kb_root / "L2"
    l2.mkdir(parents=True)
    f = l2 / "full_flow.md"
    content = MINIMAL_FM + ("x\n" * 5000)
    f.write_text(content)

    violations = lint_file(f, kb_root)
    assert violations == []


def test_lint_strict_flags_missing_confidence(tmp_path):
    kb_root = tmp_path / "kb"
    l1 = kb_root / "L1"
    l1.mkdir(parents=True)
    f = l1 / "no_confidence.md"
    f.write_text(MINIMAL_FM)

    violations = lint_file(f, kb_root, strict=True)
    assert any("confidence" in v.message for v in violations)


def test_lint_strict_flags_missing_last_verified(tmp_path):
    kb_root = tmp_path / "kb"
    l1 = kb_root / "L1"
    l1.mkdir(parents=True)
    f = l1 / "no_date.md"
    f.write_text(MINIMAL_FM)

    violations = lint_file(f, kb_root, strict=True)
    assert any("last_verified" in v.message for v in violations)


def test_lint_ignores_non_md_files(tmp_path):
    kb_root = tmp_path / "kb"
    l0 = kb_root / "L0"
    l0.mkdir(parents=True)
    (l0 / "notes.txt").write_text("just a text file")

    violations = lint_file(l0 / "notes.txt", kb_root)
    assert violations == []


# ── lint_kb ───────────────────────────────────────────────────────────────────

def test_lint_kb_clean(tmp_path):
    kb_root = tmp_path / "kb"
    l0 = kb_root / "L0"
    l0.mkdir(parents=True)
    (l0 / "glossary.md").write_text(VALID_FM)
    (l0 / "modules.md").write_text(VALID_FM)

    report = lint_kb(kb_root)
    assert report.files_checked == 2
    assert not report.has_errors


def test_lint_kb_missing_dir(tmp_path):
    kb_root = tmp_path / "nonexistent_kb"
    report = lint_kb(kb_root)
    assert report.has_errors
    assert any("does not exist" in v.message for v in report.violations)


def test_lint_kb_mixed_results(tmp_path):
    kb_root = tmp_path / "kb"
    l0 = kb_root / "L0"
    l0.mkdir(parents=True)
    (l0 / "good.md").write_text(VALID_FM)
    (l0 / "bad.md").write_text(MISSING_FM)

    report = lint_kb(kb_root)
    assert report.files_checked == 2
    assert report.has_errors   # bad.md causes an error


def test_lint_report_has_errors_and_warnings():
    report = LintReport()
    assert not report.has_errors
    assert not report.has_warnings

    report.add(LintViolation(file=Path("a.md"), line=1, message="err", severity="error"))
    report.add(LintViolation(file=Path("b.md"), line=2, message="warn", severity="warning"))

    assert report.has_errors
    assert report.has_warnings
