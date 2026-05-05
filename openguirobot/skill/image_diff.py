"""
L1 Skill — ImageDiff: perceptual hash and structural similarity comparison.

Two algorithms:
  - phash  (imagehash, <5 ms): fast, good for detecting navigation changes
  - ssim   (scikit-image, optional): slower but pixel-accurate structural diff

SimilarityResult.similarity ranges from 0.0 (completely different) to 1.0 (identical).
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Literal


@dataclass
class SimilarityResult:
    """Result of a screenshot comparison."""

    similarity: float          # 0.0 – 1.0  (1.0 = identical)
    algorithm: Literal["phash", "ssim"]
    hamming_distance: int | None = None   # phash only (0–64)
    changed: bool = False                  # True when similarity < threshold
    threshold: float = 0.75               # threshold used for the `changed` decision


# ── phash ─────────────────────────────────────────────────────────────────────

def phash_similarity(img1: bytes, img2: bytes, threshold: float = 0.75) -> SimilarityResult:
    """
    Compare two PNG images using perceptual hash (imagehash.phash).

    Hamming distance: 0 = identical, 64 = completely different.
    Similarity       = 1 - hamming_distance / 64.

    Args:
        img1:      PNG bytes of the first image.
        img2:      PNG bytes of the second image.
        threshold: Similarity below this value is considered a significant change.
                   Default 0.75 means >25% of hash bits differ → changed=True.

    Returns:
        SimilarityResult with algorithm="phash".
    """
    try:
        import imagehash
    except ImportError as exc:
        raise ImportError(
            "imagehash is required for phash comparison. "
            "Install with: pip install imagehash>=4.3"
        ) from exc

    from PIL import Image

    h1 = imagehash.phash(Image.open(io.BytesIO(img1)))
    h2 = imagehash.phash(Image.open(io.BytesIO(img2)))
    dist = h1 - h2                      # hamming distance, integer 0–64
    sim  = 1.0 - dist / 64.0
    return SimilarityResult(
        similarity=float(round(sim, 4)),
        algorithm="phash",
        hamming_distance=int(dist),
        changed=bool(sim < threshold),
        threshold=threshold,
    )


# ── SSIM (optional) ───────────────────────────────────────────────────────────

def ssim_similarity(img1: bytes, img2: bytes, threshold: float = 0.75) -> SimilarityResult:
    """
    Compare two PNG images using Structural Similarity Index (SSIM).

    Requires scikit-image (optional extra: pip install openguirobot[vision-extra]).
    Images are resized to match if they differ in dimensions.

    Args:
        img1:      PNG bytes of the first image.
        img2:      PNG bytes of the second image.
        threshold: Similarity below this value is considered a significant change.

    Returns:
        SimilarityResult with algorithm="ssim".
    """
    try:
        from skimage.metrics import structural_similarity  # type: ignore[import]
    except ImportError as exc:
        raise ImportError(
            "scikit-image is required for SSIM comparison. "
            "Install with: pip install scikit-image>=0.22  or  pip install openguirobot[vision-extra]"
        ) from exc

    import numpy as np
    from PIL import Image

    pil1 = Image.open(io.BytesIO(img1)).convert("L")   # grayscale
    pil2 = Image.open(io.BytesIO(img2)).convert("L")

    # Resize img2 to match img1 if needed
    if pil1.size != pil2.size:
        pil2 = pil2.resize(pil1.size, Image.LANCZOS)

    arr1 = np.array(pil1)
    arr2 = np.array(pil2)

    score: float = float(structural_similarity(arr1, arr2, data_range=255))
    # SSIM can be slightly negative for very different images; clamp to [0, 1]
    score = max(0.0, min(1.0, score))

    return SimilarityResult(
        similarity=round(score, 4),
        algorithm="ssim",
        hamming_distance=None,
        changed=score < threshold,
        threshold=threshold,
    )


# ── Convenience wrapper ────────────────────────────────────────────────────────

def compare(
    img1: bytes,
    img2: bytes,
    algorithm: Literal["phash", "ssim"] = "phash",
    threshold: float = 0.75,
) -> SimilarityResult:
    """
    Compare two PNG screenshots and return a SimilarityResult.

    Chooses phash by default (fast, no extra deps beyond imagehash).
    Falls back to phash if scikit-image is unavailable and ssim is requested.
    """
    if algorithm == "ssim":
        try:
            return ssim_similarity(img1, img2, threshold)
        except ImportError:
            # Graceful fallback if scikit-image not installed
            return phash_similarity(img1, img2, threshold)
    return phash_similarity(img1, img2, threshold)
