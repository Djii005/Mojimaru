"""OCR adapter.

Tries real backends in order:
  1. manga-ocr  (``[manga-ocr]`` extra) — best for Japanese vertical text.
  2. PaddleOCR  (``[paddle]`` extra)    — good for CJK in general.
  3. Stub       (always available)      — returns empty string.

Model instances are cached at module level because they are expensive to load.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PIL import Image

from mojimaru.protocol import Bubble, SourceLang

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy-loaded model singletons
# ---------------------------------------------------------------------------

_manga_ocr_instance: object | None = None
_paddle_ocr_instance: object | None = None


def _get_manga_ocr() -> object | None:
    """Return a cached ``MangaOcr`` instance, or *None* if unavailable."""
    global _manga_ocr_instance
    if _manga_ocr_instance is not None:
        return _manga_ocr_instance
    try:
        from manga_ocr import MangaOcr  # type: ignore[import-untyped]

        log.info("Loading manga-ocr model (first call — may download weights)…")
        _manga_ocr_instance = MangaOcr()
        log.info("manga-ocr model loaded.")
        return _manga_ocr_instance
    except Exception:
        log.debug("manga-ocr unavailable", exc_info=True)
        return None


def _get_paddle_ocr(lang: str = "japan") -> object | None:
    """Return a cached ``PaddleOCR`` instance, or *None* if unavailable."""
    global _paddle_ocr_instance
    if _paddle_ocr_instance is not None:
        return _paddle_ocr_instance
    try:
        from paddleocr import PaddleOCR  # type: ignore[import-untyped]

        log.info("Loading PaddleOCR model (lang=%s)…", lang)
        _paddle_ocr_instance = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
        log.info("PaddleOCR model loaded.")
        return _paddle_ocr_instance
    except Exception:
        log.debug("PaddleOCR unavailable", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Language → PaddleOCR lang code mapping
# ---------------------------------------------------------------------------

_PADDLE_LANG_MAP: dict[str, str] = {
    "ja": "japan",
    "zh": "ch",
    "ko": "korean",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def _crop_bubble(image: Image.Image, bubble: Bubble) -> Image.Image:
    """Crop ``image`` to the bubble's bounding box."""
    bb = bubble.bbox
    return image.crop((bb.x, bb.y, bb.x + bb.w, bb.y + bb.h))


def read_text(image: Image.Image, bubble: Bubble, source: SourceLang) -> str:
    """Read text from the bubble's region of ``image``.

    Attempts real backends first, falls back to the stub (empty string).
    """
    crop = _crop_bubble(image, bubble)

    # --- Try manga-ocr for Japanese (or auto-detect) ---
    if source in ("ja", "auto"):
        mocr = _get_manga_ocr()
        if mocr is not None:
            try:
                text: str = mocr(crop)  # type: ignore[operator]
                if text.strip():
                    return text.strip()
            except Exception:
                log.warning("manga-ocr inference failed", exc_info=True)

    # --- Try PaddleOCR ---
    paddle_lang = _PADDLE_LANG_MAP.get(source, "japan") if source != "auto" else "japan"
    pocr = _get_paddle_ocr(paddle_lang)
    if pocr is not None:
        try:
            import numpy as np

            arr = np.array(crop.convert("RGB"))
            result = pocr.ocr(arr, cls=True)  # type: ignore[union-attr]
            if result and result[0]:
                lines: list[str] = []
                for line in result[0]:
                    if line and len(line) >= 2:
                        text_info = line[1]
                        if isinstance(text_info, (list, tuple)) and len(text_info) >= 1:
                            lines.append(str(text_info[0]))
                        elif isinstance(text_info, str):
                            lines.append(text_info)
                text = "\n".join(lines)
                if text.strip():
                    return text.strip()
        except Exception:
            log.warning("PaddleOCR inference failed", exc_info=True)

    # --- Stub fallback ---
    return ""
