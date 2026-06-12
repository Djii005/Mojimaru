"""Render translated text back into a cleaned bubble.

Key improvements over v1:
  - Auto-sizes font to fit the bubble (starts large, shrinks to fit)
  - Uses a proper TrueType font with fallback chain
  - Adds a white outline/stroke for readability on non-white backgrounds
  - Better word wrapping that respects the bubble's aspect ratio
"""

from __future__ import annotations

import logging
import os
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from mojimaru import get_base_dir
from mojimaru.protocol import Bubble

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Font loading with fallback chain
# ---------------------------------------------------------------------------

_cached_fonts: dict[int, ImageFont.FreeTypeFont] = {}

# Common system fonts that work well for manga typesetting (sans-serif)
_FONT_CANDIDATES = [
    # User-configured
    os.environ.get("MOJIMARU_FONT_PATH", ""),
    # Project-local
    str(get_base_dir() / "models" / "fonts"),
    # Windows
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/calibri.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    # macOS
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/SFNSText.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

_found_font_path: str | None = None
_font_search_done = False


def _find_font_path() -> str | None:
    """Find the first available TrueType font file."""
    global _found_font_path, _font_search_done
    if _font_search_done:
        return _found_font_path
    _font_search_done = True

    # Check env var first (may have been updated at runtime)
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
        # If it's a directory, look for .ttf files inside
        if p.is_dir():
            for f in sorted(p.glob("*.ttf")):
                _found_font_path = str(f)
                log.debug("Using font: %s", _found_font_path)
                return _found_font_path

    log.debug("No TrueType font found; using Pillow default")
    return None


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a font at the given size with caching."""
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

    # Pillow's built-in font (tiny but always works)
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Text fitting
# ---------------------------------------------------------------------------


def _measure_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> tuple[int, int]:
    """Measure the width and height of multi-line text."""
    bbox = draw.multiline_textbbox((0, 0), text, font=font, align="center")
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _fit_text(
    text: str,
    max_w: int,
    max_h: int,
    draw: ImageDraw.ImageDraw,
) -> tuple[str, ImageFont.FreeTypeFont | ImageFont.ImageFont, int, int]:
    """Find the largest font size that fits ``text`` inside (max_w, max_h).

    Returns (wrapped_text, font, text_width, text_height).
    """
    # Start from a generous size and shrink
    for size in range(max(8, min(max_h, max_w) // 2), 7, -1):
        font = _load_font(size)

        # Estimate chars per line based on font size
        avg_char_w = max(1, size * 6 // 10)  # rough estimate
        wrap_width = max(4, (max_w - 8) // avg_char_w)

        wrapped = textwrap.fill(text, width=wrap_width)
        tw, th = _measure_text(draw, wrapped, font)

        if tw <= max_w - 4 and th <= max_h - 4:
            return wrapped, font, tw, th

    # Minimum size fallback
    font = _load_font(8)
    wrap_width = max(4, (max_w - 4) // 5)
    wrapped = textwrap.fill(text, width=wrap_width)
    tw, th = _measure_text(draw, wrapped, font)
    return wrapped, font, tw, th


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def typeset(image: Image.Image, bubble: Bubble, text: str) -> Image.Image:
    """Draw ``text`` centred inside ``bubble`` on ``image``.

    Auto-sizes the font to fit the bubble region. Adds a white outline
    for readability on non-white backgrounds.
    """
    if not text:
        return image

    out = image.convert("RGB")
    draw = ImageDraw.Draw(out)
    bb = bubble.bbox

    # Padding inside the bubble
    pad = max(4, min(bb.w, bb.h) // 10)
    inner_w = max(10, bb.w - pad * 2)
    inner_h = max(10, bb.h - pad * 2)

    wrapped, font, tw, th = _fit_text(text, inner_w, inner_h, draw)

    # Centre text inside the bubble
    cx = bb.x + (bb.w - tw) // 2
    cy = bb.y + (bb.h - th) // 2

    # Draw white outline/stroke for readability
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
