from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from PIL import Image

from mojimaru.protocol import Bubble, SourceLang

if TYPE_CHECKING:
    pass

log = logging.getLogger(__name__)

_manga_ocr_instance: Any = None
_paddle_ocr_instance: Any = None


def _get_manga_ocr() -> Any:
    global _manga_ocr_instance
    if _manga_ocr_instance is not None:
        return _manga_ocr_instance
    try:
        from manga_ocr import MangaOcr

        log.info("Loading manga-ocr model (first call — may download weights)…")
        _manga_ocr_instance = MangaOcr()
        log.info("manga-ocr model loaded.")
        return _manga_ocr_instance
    except Exception:
        log.debug("manga-ocr unavailable", exc_info=True)
        return None


def _get_paddle_ocr(lang: str = "japan") -> Any:

    global _paddle_ocr_instance
    if _paddle_ocr_instance is not None:
        return _paddle_ocr_instance
    try:
        from paddleocr import PaddleOCR

        log.info("Loading PaddleOCR model (lang=%s)…", lang)
        _paddle_ocr_instance = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
        log.info("PaddleOCR model loaded.")
        return _paddle_ocr_instance
    except Exception:
        log.debug("PaddleOCR unavailable", exc_info=True)
        return None


_PADDLE_LANG_MAP: dict[str, str] = {
    "ja": "japan",
    "zh": "ch",
    "ko": "korean",
}


def _crop_bubble(image: Image.Image, bubble: Bubble) -> Image.Image:
    bb = bubble.bbox
    return image.crop((bb.x, bb.y, bb.x + bb.w, bb.y + bb.h))


def read_text(image: Image.Image, bubble: Bubble, source: SourceLang) -> str:
    crop = _crop_bubble(image, bubble)

    if source in ("ja", "auto"):
        mocr = _get_manga_ocr()
        if mocr is not None:
            try:
                text: str = mocr(crop)
                if text.strip():
                    return text.strip()
            except Exception:
                log.warning("manga-ocr inference failed", exc_info=True)

    paddle_lang = _PADDLE_LANG_MAP.get(source, "japan") if source != "auto" else "japan"
    pocr = _get_paddle_ocr(paddle_lang)
    if pocr is not None:
        try:
            import numpy as np

            arr = np.array(crop.convert("RGB"))
            result = pocr.ocr(arr, cls=True)
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

    return ""
