"""
L1 Skill — Locator: 2-tier element finding (rule layer → vision layer).

Tier 1 (Rule):  DOM accessibility_id / resource_id / exact text / substring text
Tier 2 (Vision): Qwen-VL / GPT-4o grounding (cloud API, fallback only)

At replay time (vision=None in LocatorRuntime), only the rule layer runs,
guaranteeing zero LLM / vision calls.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Literal, TypedDict

from openguirobot.driver.base import DomNode, DomTree

if TYPE_CHECKING:
    from openguirobot.obs.evidence import EvidenceWriter
    from openguirobot.vision.base import VisionModel


# ── Public types ───────────────────────────────────────────────────────────────

class ElementMatch(TypedDict):
    bbox:         tuple[int, int, int, int]   # x1, y1, x2, y2
    locator_kind: Literal["rule", "vision"]
    confidence:   float                        # 0.0 – 1.0
    debug:        dict                         # optional diagnostic info


class LocatorRuntime(TypedDict, total=False):
    vision:   "VisionModel | None"
    evidence: "EvidenceWriter | None"
    step:     int


class LocatorError(RuntimeError):
    """Raised when an element cannot be found by any available strategy."""


# ── Helper ─────────────────────────────────────────────────────────────────────

def bbox_center(bbox: tuple[int, int, int, int]) -> tuple[int, int]:
    x1, y1, x2, y2 = bbox
    return (x1 + x2) // 2, (y1 + y2) // 2


def _node_to_match(node: DomNode, debug_key: str) -> ElementMatch:
    return ElementMatch(
        bbox=node.bounds,
        locator_kind="rule",
        confidence=1.0,
        debug={"node_id": node.node_id, "match_by": debug_key, "text": node.text},
    )


# ── Rule layer ─────────────────────────────────────────────────────────────────

def _rule_locate(query: str, dom: DomTree) -> DomNode | None:
    """
    Try to find *query* in the DOM using static rules.
    Priority: resource_id → content_desc → exact text → substring text (len≥3).
    """
    # 1. Exact resource-id / name match
    nodes = dom.find_by_resource_id(query)
    if nodes:
        return nodes[0]

    # 2. Exact content-desc / accessibility label match
    nodes = dom.find_by_content_desc(query)
    if nodes:
        return nodes[0]

    # 3. Exact text match
    nodes = dom.find_by_text(query, exact=True)
    if nodes:
        return nodes[0]

    # 4. Substring text match (only for queries ≥3 chars to avoid noise)
    if len(query) >= 3:
        nodes = dom.find_by_text(query, exact=False)
        if nodes:
            return nodes[0]

    return None


# ── Vision layer ───────────────────────────────────────────────────────────────

def _vision_locate(
    query: str,
    screenshot: bytes,
    runtime: LocatorRuntime,
) -> ElementMatch | None:
    """Call the vision model to ground *query* in *screenshot*."""
    vision = runtime.get("vision")
    if vision is None:
        return None
    bbox = vision.ground(screenshot, query)
    if bbox is None:
        return None
    return ElementMatch(
        bbox=bbox,
        locator_kind="vision",
        confidence=0.7,
        debug={"query": query},
    )


# ── Public API ─────────────────────────────────────────────────────────────────

def locate(
    query: str,
    dom: DomTree,
    screenshot: bytes,
    runtime: LocatorRuntime,
) -> ElementMatch:
    """
    Find *query* in the current screen state.

    1. Rule layer (DOM-based, zero cost).
    2. Vision layer (cloud model, only when rule layer fails and vision is available).

    Raises LocatorError if neither layer succeeds.
    """
    node = _rule_locate(query, dom)
    if node is not None:
        return _node_to_match(node, "rule")

    match = _vision_locate(query, screenshot, runtime)
    if match is not None:
        return match

    vision_available = runtime.get("vision") is not None
    hint = "" if vision_available else " (vision model not configured)"
    raise LocatorError(f"Could not locate element: {query!r}{hint}")
