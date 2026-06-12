"""Inpainting — remove original text from detected bubbles.

The key insight: apply inpainting **once** with a combined mask of all
text regions, rather than per-bubble (which cumulatively degrades the image).

Backends:
  1. OpenCV ``cv2.inpaint`` with a tight text-only mask.
  2. White-fill stub (fallback).
"""

from __future__ import annotations

import logging

import numpy as np
from PIL import Image, ImageDraw

from mojimaru.protocol import Bubble

log = logging.getLogger(__name__)


def _build_text_mask(image: Image.Image, bubbles: list[Bubble]) -> np.ndarray:
    """Build a combined binary mask marking text pixels across all bubbles.

    Uses Otsu thresholding within each bubble region to separate dark text
    from the (typically white/light) bubble background. Much more accurate
    than the old percentile-based approach.

    Returns an (H, W) uint8 array: 255 = text pixel to inpaint, 0 = keep.
    """
    gray = np.array(image.convert("L"), dtype=np.uint8)
    h, w = gray.shape
    mask = np.zeros((h, w), dtype=np.uint8)

    try:
        import cv2
    except ImportError:
        # No cv2 → just mask entire bbox regions
        for bubble in bubbles:
            bb = bubble.bbox
            y1 = max(0, bb.y)
            y2 = min(h, bb.y + bb.h)
            x1 = max(0, bb.x)
            x2 = min(w, bb.x + bb.w)
            mask[y1:y2, x1:x2] = 255
        return mask

    for bubble in bubbles:
        bb = bubble.bbox
        y1 = max(0, bb.y)
        y2 = min(h, bb.y + bb.h)
        x1 = max(0, bb.x)
        x2 = min(w, bb.x + bb.w)

        region = gray[y1:y2, x1:x2]
        if region.size == 0:
            continue

        # Otsu threshold to find dark text on light background
        _, binary = cv2.threshold(region, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

        # Dilate slightly to close gaps in text strokes
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(binary, kernel, iterations=1)

        mask[y1:y2, x1:x2] = np.maximum(mask[y1:y2, x1:x2], dilated)

    return mask


def inpaint_all(image: Image.Image, bubbles: list[Bubble]) -> Image.Image:
    """Inpaint all text regions in one pass.

    This is the correct approach: build a single combined mask for ALL
    detected text regions, then inpaint the entire image once. Avoids
    the cumulative degradation caused by per-bubble inpainting.
    """
    if not bubbles:
        return image

    text_mask = _build_text_mask(image, bubbles)

    # If mask is empty (no text detected), skip inpainting
    if not np.any(text_mask):
        return image

    try:
        import cv2

        src = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)

        # Use INPAINT_TELEA with a small radius for clean text removal
        result = cv2.inpaint(src, text_mask, inpaintRadius=2, flags=cv2.INPAINT_TELEA)

        result_rgb = cv2.cvtColor(result, cv2.COLOR_BGR2RGB)
        return Image.fromarray(result_rgb)

    except ImportError:
        log.debug("cv2 not available; using white-fill fallback")
        return _inpaint_stub(image, bubbles)
    except Exception:
        log.warning("cv2.inpaint failed; using white-fill fallback", exc_info=True)
        return _inpaint_stub(image, bubbles)


def _inpaint_stub(image: Image.Image, bubbles: list[Bubble]) -> Image.Image:
    """Fallback: fill each bubble bbox with white."""
    out = image.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    for bubble in bubbles:
        bb = bubble.bbox
        draw.rectangle(
            [(bb.x, bb.y), (bb.x + bb.w, bb.y + bb.h)],
            fill=(255, 255, 255),
        )
    return out


# Keep old single-bubble API for backward compatibility
def inpaint_bubble(image: Image.Image, bubble: Bubble) -> Image.Image:
    """Inpaint a single bubble. Prefer ``inpaint_all`` for batched use."""
    return inpaint_all(image, [bubble])
