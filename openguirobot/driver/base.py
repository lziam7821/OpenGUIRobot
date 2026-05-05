"""
L0 Driver Layer — base protocols and shared data structures.

Every upper layer imports exclusively from this module; never from platform-specific drivers.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Protocol, runtime_checkable


# ── Key codes ─────────────────────────────────────────────────────────────────

class KeyCode(IntEnum):
    HOME       = 3
    BACK       = 4
    ENTER      = 66
    TAB        = 61
    DELETE     = 67
    VOLUME_UP  = 24
    VOLUME_DOWN = 25
    POWER      = 26


# ── DOM model ──────────────────────────────────────────────────────────────────

@dataclass
class DomNode:
    node_id:      str
    class_name:   str
    text:         str
    resource_id:  str
    content_desc: str
    bounds:       tuple[int, int, int, int]   # x1, y1, x2, y2
    children:     list[DomNode] = field(default_factory=list)
    attrs:        dict[str, str] = field(default_factory=dict)

    @property
    def center(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.bounds
        return (x1 + x2) // 2, (y1 + y2) // 2


def _parse_bounds(bounds_str: str) -> tuple[int, int, int, int]:
    """Parse '[x1,y1][x2,y2]' or '(x1,y1,x2,y2)' style bounds strings."""
    import re
    nums = list(map(int, re.findall(r"\d+", bounds_str)))
    if len(nums) == 4:
        return (nums[0], nums[1], nums[2], nums[3])
    return (0, 0, 0, 0)


def _build_node(element: ET.Element, id_counter: list[int]) -> DomNode:
    id_counter[0] += 1
    attrib = element.attrib
    bounds_raw = attrib.get("bounds", "[0,0][0,0]")
    node = DomNode(
        node_id      = str(id_counter[0]),
        class_name   = attrib.get("class", attrib.get("type", element.tag or "")),
        text         = attrib.get("text", attrib.get("label", attrib.get("value", ""))),
        resource_id  = attrib.get("resource-id", attrib.get("name", "")),
        content_desc = attrib.get("content-desc", attrib.get("name", "")),
        bounds       = _parse_bounds(bounds_raw),
        attrs        = dict(attrib),
    )
    for child in element:
        node.children.append(_build_node(child, id_counter))
    return node


@dataclass
class DomTree:
    root:     DomNode
    platform: str      # "android" | "ios"
    raw_xml:  str

    # ── BFS helpers ─────────────────────────────────────────────────────────

    def _bfs(self) -> list[DomNode]:
        result: list[DomNode] = []
        queue = [self.root]
        while queue:
            node = queue.pop(0)
            result.append(node)
            queue.extend(node.children)
        return result

    def find_by_resource_id(self, rid: str) -> list[DomNode]:
        return [n for n in self._bfs() if n.resource_id == rid]

    def find_by_content_desc(self, desc: str) -> list[DomNode]:
        return [n for n in self._bfs() if n.content_desc == desc]

    def find_by_text(self, text: str, exact: bool = True) -> list[DomNode]:
        if exact:
            return [n for n in self._bfs() if n.text == text]
        text_lower = text.lower()
        return [n for n in self._bfs() if text_lower in n.text.lower()]

    def find_by_class(self, class_name: str) -> list[DomNode]:
        return [n for n in self._bfs() if n.class_name == class_name]

    def all_nodes(self) -> list[DomNode]:
        return self._bfs()

    @classmethod
    def from_xml(cls, xml_str: str, platform: str) -> "DomTree":
        root_el = ET.fromstring(xml_str)
        counter = [0]
        root_node = _build_node(root_el, counter)
        return cls(root=root_node, platform=platform, raw_xml=xml_str)


# ── Driver Protocol ────────────────────────────────────────────────────────────

@runtime_checkable
class Driver(Protocol):
    """Unified driver interface across Android, iOS, and Web."""

    def attach(self, device_id: str) -> None:
        """Connect to the specified device and start a session."""
        ...

    def detach(self) -> None:
        """End the session and release resources."""
        ...

    def tap(self, x: int, y: int) -> None:
        """Tap at pixel coordinates (x, y)."""
        ...

    def swipe(
        self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300
    ) -> None:
        """Swipe from (x1, y1) to (x2, y2) over duration_ms milliseconds."""
        ...

    def input_text(self, text: str) -> None:
        """Type text into the currently focused element."""
        ...

    def press_key(self, key: KeyCode) -> None:
        """Press a hardware or system key."""
        ...

    def screenshot(self) -> bytes:
        """Capture the current screen and return raw PNG bytes."""
        ...

    def dump_dom(self) -> DomTree:
        """Return the current UI accessibility tree."""
        ...

    def get_window_size(self) -> tuple[int, int]:
        """Return (width, height) of the device screen in pixels."""
        ...

    def launch_app(self, package_or_bundle_id: str) -> None:
        """Launch (or bring to foreground) the specified application."""
        ...

    def kill_app(self, package_or_bundle_id: str) -> None:
        """Terminate the specified application."""
        ...

    def get_current_app(self) -> str:
        """Return the package name / bundle ID of the foreground application."""
        ...


# ── Exceptions ────────────────────────────────────────────────────────────────

class DriverError(RuntimeError):
    """Base class for all driver exceptions."""


class AttachError(DriverError):
    """Failed to connect to device or start Appium session."""


class ActionError(DriverError):
    """A UI action (tap / swipe / input) failed."""


class DriverTimeoutError(DriverError):
    """An operation exceeded its time limit."""
