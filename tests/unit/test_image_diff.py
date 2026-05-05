"""Unit tests for skill/image_diff.py."""
from __future__ import annotations

import io
from unittest.mock import MagicMock, patch

import pytest

from openguirobot.skill.image_diff import SimilarityResult, compare, phash_similarity


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_png(color: tuple[int, int, int] = (255, 255, 255), size: tuple[int, int] = (64, 64)) -> bytes:
    """Create a minimal solid-color PNG for testing."""
    from PIL import Image

    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_checkerboard_png(size: tuple[int, int] = (64, 64)) -> bytes:
    """Create a high-contrast checkerboard PNG — structurally very different from solid colors."""
    import numpy as np
    from PIL import Image

    arr = np.zeros((*size, 3), dtype=np.uint8)
    for y in range(size[1]):
        for x in range(size[0]):
            arr[y, x] = (255, 255, 255) if (x // 8 + y // 8) % 2 == 0 else (0, 0, 0)
    img = Image.fromarray(arr, "RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


WHITE_PNG       = _make_png((255, 255, 255))
BLACK_PNG       = _make_png((0, 0, 0))
RED_PNG         = _make_png((255, 0, 0))
CHECKER_PNG     = _make_checkerboard_png()   # structurally distinct from solid color


# ── SimilarityResult dataclass ────────────────────────────────────────────────

def test_similarity_result_fields():
    r = SimilarityResult(similarity=0.9, algorithm="phash", hamming_distance=6, changed=False)
    assert r.similarity == 0.9
    assert r.algorithm == "phash"
    assert r.hamming_distance == 6
    assert r.changed is False


# ── phash_similarity ──────────────────────────────────────────────────────────

def test_phash_identical_images():
    result = phash_similarity(WHITE_PNG, WHITE_PNG)
    assert result.algorithm == "phash"
    assert result.similarity == 1.0
    assert result.hamming_distance == 0
    assert result.changed is False


def test_phash_very_different_images():
    # Checkerboard vs solid white: structurally different → phash detects change at threshold=0.8
    result = phash_similarity(WHITE_PNG, CHECKER_PNG, threshold=0.8)
    assert result.algorithm == "phash"
    assert result.similarity < 0.95      # should differ perceptually
    assert result.changed is True        # similarity(0.75) < threshold(0.8)


def test_phash_returns_similarity_result():
    result = phash_similarity(WHITE_PNG, RED_PNG)
    assert isinstance(result, SimilarityResult)
    assert 0.0 <= result.similarity <= 1.0
    assert result.hamming_distance is not None
    assert 0 <= result.hamming_distance <= 64


def test_phash_custom_threshold():
    # With threshold=0.0, nothing is ever "changed" (similarity always >= 0)
    result = phash_similarity(WHITE_PNG, CHECKER_PNG, threshold=0.0)
    assert result.threshold == 0.0
    assert result.changed is False


def test_phash_high_threshold():
    # With threshold=1.0, identical images are still not "changed"
    result = phash_similarity(WHITE_PNG, WHITE_PNG, threshold=1.0)
    # similarity == 1.0, threshold == 1.0  → sim < threshold is False
    assert result.changed is False


def test_phash_missing_imagehash_raises():
    import sys
    orig = sys.modules.get("imagehash")
    sys.modules["imagehash"] = None  # type: ignore[assignment]
    try:
        with pytest.raises(ImportError, match="imagehash"):
            phash_similarity(WHITE_PNG, WHITE_PNG)
    finally:
        if orig is None:
            sys.modules.pop("imagehash", None)
        else:
            sys.modules["imagehash"] = orig


# ── compare wrapper ────────────────────────────────────────────────────────────

def test_compare_defaults_to_phash():
    result = compare(WHITE_PNG, WHITE_PNG)
    assert result.algorithm == "phash"


def test_compare_phash_explicit():
    result = compare(WHITE_PNG, WHITE_PNG, algorithm="phash")
    assert result.algorithm == "phash"


def test_compare_ssim_fallback_to_phash_if_no_scikit():
    """If scikit-image is not installed, ssim falls back to phash gracefully."""
    import sys
    orig = sys.modules.get("skimage")
    sys.modules["skimage"] = None  # type: ignore[assignment]
    sys.modules["skimage.metrics"] = None  # type: ignore[assignment]
    try:
        result = compare(WHITE_PNG, WHITE_PNG, algorithm="ssim")
        # Should have fallen back to phash
        assert result.algorithm == "phash"
    finally:
        sys.modules.pop("skimage", None)
        sys.modules.pop("skimage.metrics", None)
        if orig is not None:
            sys.modules["skimage"] = orig


def test_compare_ssim_when_available():
    """If scikit-image is available, ssim should return an ssim result."""
    pytest.importorskip("skimage", reason="scikit-image not installed")
    from openguirobot.skill.image_diff import ssim_similarity

    result = ssim_similarity(WHITE_PNG, WHITE_PNG)
    assert result.algorithm == "ssim"
    assert result.similarity >= 0.99   # identical images → near 1.0
    assert result.hamming_distance is None
