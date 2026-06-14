from __future__ import annotations

import logging

import numpy as np
from PIL import Image, ImageDraw

from mojimaru.protocol import Bubble

log = logging.getLogger(__name__)


def _build_text_mask(image: Image.Image, bubbles: list[Bubble]) -> np.ndarray:
    gray = np.array(image.convert("L"), dtype=np.uint8)
    h, w = gray.shape
    mask = np.zeros((h, w), dtype=np.uint8)

    try:
        import cv2
    except ImportError:
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

        _, binary = cv2.threshold(region, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
        dilated = cv2.dilate(binary, kernel, iterations=1)

        mask[y1:y2, x1:x2] = np.maximum(mask[y1:y2, x1:x2], dilated)

    return mask


def inpaint_all(image: Image.Image, bubbles: list[Bubble]) -> Image.Image:
    if not bubbles:
        return image

    text_mask = _build_text_mask(image, bubbles)

    if not np.any(text_mask):
        return image

    try:
        import cv2

        src = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)

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
    out = image.convert("RGB").copy()
    draw = ImageDraw.Draw(out)
    for bubble in bubbles:
        bb = bubble.bbox
        draw.rectangle(
            [(bb.x, bb.y), (bb.x + bb.w, bb.y + bb.h)],
            fill=(255, 255, 255),
        )
    return out


def inpaint_bubble(image: Image.Image, bubble: Bubble) -> Image.Image:
    return inpaint_all(image, [bubble])
