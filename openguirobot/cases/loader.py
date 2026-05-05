"""
Test case schema (Pydantic) and YAML loader.
"""
from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field


class Platform(str, Enum):
    android = "android"
    ios     = "ios"


class AssertionKind(str, Enum):
    element_exists = "element_exists"
    ocr_text       = "ocr_text"
    visual         = "visual"


class AssertionSpec(BaseModel):
    kind:   AssertionKind
    desc:   str
    target: str | None = None   # locator query or expected text


class TestCase(BaseModel):
    case_id:    str
    title:      str
    intent:     str
    platforms:  list[Platform]
    priority:   Literal["p0", "p1", "p2", "p3"] = "p2"
    budget_usd: float = 1.5
    timeout_s:  int   = 600
    env:        dict[str, str] = Field(default_factory=dict)
    assertions: list[AssertionSpec] = Field(default_factory=list)

    @property
    def snake_name(self) -> str:
        """case_id with dots replaced by underscores → valid Python identifier."""
        return self.case_id.replace(".", "_")

    @property
    def group(self) -> str:
        """All but the last component of case_id, as a path-friendly string."""
        parts = self.case_id.split(".")
        return "/".join(parts[:-1]) if len(parts) > 1 else "default"

    @property
    def name(self) -> str:
        """Last component of case_id."""
        return self.case_id.split(".")[-1]


def load_case(
    case_id: str,
    cases_dir: Path | str = Path("tests/cases"),
) -> TestCase:
    """
    Search recursively under *cases_dir* for ``<name>.case.yaml`` and load it.

    Lookup strategy (first match wins):
    1. ``cases_dir/<part0>/<part1>/.../<name>.case.yaml``  (dotted → nested dirs)
    2. ``cases_dir/<case_id>.case.yaml``                   (flat)
    """
    base = Path(cases_dir)
    parts = case_id.split(".")
    candidates = [
        base.joinpath(*parts[:-1]) / f"{parts[-1]}.case.yaml",
        base / f"{case_id}.case.yaml",
    ]
    for path in candidates:
        if path.exists():
            with path.open() as f:
                data = yaml.safe_load(f)
            return TestCase.model_validate(data)
    raise FileNotFoundError(
        f"Case {case_id!r} not found. Searched:\n"
        + "\n".join(f"  {p}" for p in candidates)
    )


def list_cases(cases_dir: Path | str = Path("tests/cases")) -> list[TestCase]:
    """Return all test cases found recursively under *cases_dir*."""
    results: list[TestCase] = []
    for path in Path(cases_dir).rglob("*.case.yaml"):
        try:
            with path.open() as f:
                data = yaml.safe_load(f)
            results.append(TestCase.model_validate(data))
        except Exception:  # noqa: BLE001
            pass  # skip malformed or invalid files
    return results
