"""
Vision model protocol and shared types.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

# Bounding box: (x1, y1, x2, y2) in pixels
BBox = tuple[int, int, int, int]


@runtime_checkable
class VisionModel(Protocol):
    """Unified interface for vision grounding models."""

    def ground(self, image: bytes, target: str) -> BBox | None:
        """
        Locate *target* in *image* and return its bounding box.
        Returns None if the target cannot be found.
        """
        ...
