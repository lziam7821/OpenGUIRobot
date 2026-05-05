"""
L1 Skill — Assertor: element existence and OCR text matching.

v0.1 scope:
  - assert_element_exists: DOM rule-layer check (zero cost)
  - assert_ocr_text: RapidOCR on screenshot bytes
  - run_assertions: dispatch from AssertionSpec list
"""
from __future__ import annotations

from typing import TYPE_CHECKING, TypedDict

from openguirobot.driver.base import DomTree
from openguirobot.skill.locator import _rule_locate

if TYPE_CHECKING:
    from openguirobot.cases.loader import AssertionSpec


class AssertResult(TypedDict):
    passed:     bool
    confidence: float
    reasoning:  str


# ── OCR engine (lazily loaded, module-level singleton) ────────────────────────

_ocr_engine = None


def _get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        try:
            from rapidocr_onnxruntime import RapidOCR  # type: ignore[import]
            _ocr_engine = RapidOCR()
        except ImportError as exc:
            raise ImportError(
                "rapidocr-onnxruntime is required for OCR assertions. "
                "Install with: pip install rapidocr-onnxruntime"
            ) from exc
    return _ocr_engine


# ── Assertion functions ───────────────────────────────────────────────────────

def assert_element_exists(query: str, dom: DomTree) -> AssertResult:
    """Check that *query* matches at least one DOM node via the rule layer."""
    node = _rule_locate(query, dom)
    if node is not None:
        return AssertResult(
            passed=True,
            confidence=1.0,
            reasoning=f"Found element matching {query!r}: text={node.text!r} resource_id={node.resource_id!r}",
        )
    return AssertResult(
        passed=False,
        confidence=1.0,
        reasoning=f"No DOM node matched {query!r}",
    )


def assert_ocr_text(expected_text: str, screenshot: bytes) -> AssertResult:
    """
    Check that *expected_text* appears anywhere on the screen via OCR.
    Uses RapidOCR (CPU-friendly, no GPU required).
    """
    import io
    import numpy as np
    from PIL import Image

    img = Image.open(io.BytesIO(screenshot)).convert("RGB")
    img_array = np.array(img)

    engine = _get_ocr()
    result, _ = engine(img_array)   # returns list of (bbox, text, confidence)

    if result is None:
        return AssertResult(
            passed=False,
            confidence=0.0,
            reasoning="OCR returned no results",
        )

    found_texts = [item[1] for item in result if item and len(item) > 1]
    full_text = " ".join(found_texts)

    if expected_text in full_text:
        return AssertResult(
            passed=True,
            confidence=0.9,
            reasoning=f"OCR found {expected_text!r} in screen text",
        )
    return AssertResult(
        passed=False,
        confidence=0.9,
        reasoning=(
            f"OCR did not find {expected_text!r}. "
            f"Detected text (truncated): {full_text[:200]!r}"
        ),
    )


def run_assertions(
    specs: list["AssertionSpec"],
    dom: DomTree,
    screenshot: bytes,
) -> list[AssertResult]:
    """Dispatch each AssertionSpec to the appropriate assertion function."""
    from openguirobot.cases.loader import AssertionKind

    results: list[AssertResult] = []
    for spec in specs:
        if spec.kind == AssertionKind.element_exists:
            results.append(assert_element_exists(spec.target or spec.desc, dom))
        elif spec.kind == AssertionKind.ocr_text:
            results.append(assert_ocr_text(spec.target or spec.desc, screenshot))
        else:
            # visual / unknown — placeholder for v0.2
            results.append(AssertResult(
                passed=True,
                confidence=0.0,
                reasoning=f"Assertion kind {spec.kind!r} not implemented in v0.1 — skipped",
            ))
    return results
