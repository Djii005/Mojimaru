from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from mojimaru.detect import detect_bubbles
from mojimaru.inpaint import inpaint_all
from mojimaru.ocr import read_text
from mojimaru.protocol import Bubble, SourceLang, TargetLang
from mojimaru.translate import translate as translate_text
from mojimaru.typeset import typeset

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

ProgressCb = Callable[[str, int, int, str], None]


@dataclass(slots=True)
class TranslationResult:
    input_path: Path
    output_path: Path
    bubbles: list[Bubble]


def translate_image(
    input_path: Path,
    output_path: Path,
    source: SourceLang = "auto",
    target: TargetLang = "en",
    *,
    on_progress: ProgressCb | None = None,
) -> TranslationResult:
    progress = on_progress or (lambda *_: None)

    progress("io", 0, 1, f"read {input_path.name}")
    with Image.open(input_path) as im:
        page = im.convert("RGB").copy()

    progress("detect", 0, 1, "detect bubbles")
    bubbles = detect_bubbles(page)
    progress("detect", 1, 1, f"{len(bubbles)} bubble(s)")

    if not bubbles:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        progress("io", 1, 1, f"write {output_path.name} (no text found)")
        page.save(output_path)
        return TranslationResult(input_path=input_path, output_path=output_path, bubbles=[])

    total = len(bubbles)

    for idx, bubble in enumerate(bubbles, start=1):
        progress("ocr", idx, total, "")
        bubble.source_text = read_text(page, bubble, source)

    for idx, bubble in enumerate(bubbles, start=1):
        progress("translate", idx, total, "")
        bubble.translated_text = translate_text(bubble.source_text, source, target)

    progress("inpaint", 1, 1, f"inpainting {total} region(s)")
    cleaned = inpaint_all(page, bubbles)

    current = cleaned
    for idx, bubble in enumerate(bubbles, start=1):
        progress("typeset", idx, total, "")
        current = typeset(current, bubble, bubble.translated_text)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    progress("io", 1, 1, f"write {output_path.name}")
    current.save(output_path)

    return TranslationResult(
        input_path=input_path,
        output_path=output_path,
        bubbles=bubbles,
    )


def iter_image_files(root: Path, *, recursive: bool) -> Iterable[Path]:
    if recursive:
        for dirpath, _, files in os.walk(root):
            for name in sorted(files):
                p = Path(dirpath) / name
                if p.suffix.lower() in IMAGE_EXTS:
                    yield p
    else:
        for p in sorted(root.iterdir()):
            if p.is_file() and p.suffix.lower() in IMAGE_EXTS:
                yield p


def translate_directory(
    input_dir: Path,
    output_dir: Path,
    source: SourceLang = "auto",
    target: TargetLang = "en",
    *,
    recursive: bool = False,
    on_progress: ProgressCb | None = None,
) -> tuple[int, list[tuple[Path, str]]]:
    progress = on_progress or (lambda *_: None)
    files = list(iter_image_files(input_dir, recursive=recursive))
    total = len(files)
    succeeded = 0
    failures: list[tuple[Path, str]] = []

    for idx, src in enumerate(files, start=1):
        rel = src.relative_to(input_dir) if recursive else src.name
        dst = output_dir / rel
        progress("io", idx, total, str(src))
        try:
            translate_image(src, dst, source=source, target=target)
            succeeded += 1
        except Exception as exc:
            failures.append((src, f"{type(exc).__name__}: {exc}"))

    return succeeded, failures
