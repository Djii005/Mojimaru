from __future__ import annotations

import logging
import os
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from mojimaru import get_base_dir
from mojimaru.protocol import Bubble

log = logging.getLogger(__name__)

_cached_fonts: dict[int, ImageFont.FreeTypeFont] = {}

_FONT_CANDIDATES = [
    os.environ.get("MOJIMARU_FONT_PATH", ""),
    str(get_base_dir() / "models" / "fonts"),
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/calibri.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/SFNSText.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

_found_font_path: str | None = None
_font_search_done = False


def _find_font_path() -> str | None:
    global _found_font_path, _font_search_done
    if _font_search_done:
        return _found_font_path
    _font_search_done = True

    env_path = os.environ.get("MOJIMARU_FONT_PATH", "")
    if env_path and os.path.isfile(env_path):
        _found_font_path = env_path
        return _found_font_path

    for candidate in _FONT_CANDIDATES:
        if not candidate:
            continue
        p = Path(candidate)
        if p.is_file() and p.suffix.lower() in (".ttf", ".otf", ".ttc"):
            _found_font_path = str(p)
            log.debug("Using font: %s", _found_font_path)
            return _found_font_path
        if p.is_dir():
            for f in sorted(p.glob("*.ttf")):
                _found_font_path = str(f)
                log.debug("Using font: %s", _found_font_path)
                return _found_font_path

    log.debug("No TrueType font found; using Pillow default")
    return None


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    if size in _cached_fonts:
        return _cached_fonts[size]

    path = _find_font_path()
    if path:
        try:
            font = ImageFont.truetype(path, size)
            _cached_fonts[size] = font
            return font
        except OSError:
            pass

    return ImageFont.load_default()


def _measure_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> tuple[int, int]:
    bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center")
    return int(bbox[2] - bbox[0]), int(bbox[3] - bbox[1])


def _fit_text(
    text: str,
    max_w: int,
    max_h: int,
    draw: ImageDraw.ImageDraw,
) -> tuple[str, ImageFont.FreeTypeFont | ImageFont.ImageFont, int, int]:
    for size in range(max(8, min(max_h, max_w) // 2), 7, -1):
        font = _load_font(size)

        avg_char_w = max(1, size * 6 // 10)
        wrap_width = max(4, (max_w - 8) // avg_char_w)

        wrapped = textwrap.fill(text, width=wrap_width)
        tw, th = _measure_text(draw, wrapped, font)

        if tw <= max_w - 4 and th <= max_h - 4:
            return wrapped, font, tw, th

    font = _load_font(8)
    wrap_width = max(4, (max_w - 4) // 5)
    wrapped = textwrap.fill(text, width=wrap_width)
    tw, th = _measure_text(draw, wrapped, font)
    return wrapped, font, tw, th


def typeset(image: Image.Image, bubble: Bubble, text: str) -> Image.Image:
    if not text:
        return image

    out = image.convert("RGB")
    draw = ImageDraw.Draw(out)
    bb = bubble.bbox

    pad = max(4, min(bb.w, bb.h) // 10)
    inner_w = max(10, bb.w - pad * 2)
    inner_h = max(10, bb.h - pad * 2)

    wrapped, font, tw, th = _fit_text(text, inner_w, inner_h, draw)

    cx = bb.x + (bb.w - tw) // 2
    cy = bb.y + (bb.h - th) // 2

    stroke_w = max(1, min(3, tw // 60))
    draw.multiline_text(
        (cx, cy),
        wrapped,
        font=font,
        fill=(20, 20, 20),
        align="center",
        stroke_width=stroke_w,
        stroke_fill=(255, 255, 255),
    )
    return out
