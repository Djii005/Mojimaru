"""End-to-end smoke tests for the pipeline.

Tests marked ``ml`` require the RT-DETR model (transformers + torch) and are
skipped on CI via ``pytest -m 'not ml'``.  The remaining tests (sidecar, CLI)
work without any ML backend.
"""

from __future__ import annotations

import json
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pytest
from PIL import Image

from mojimaru.pipeline import translate_directory, translate_image
from mojimaru.protocol import TranslateImageRequest
from mojimaru.sidecar import run


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    path = tmp_path / "page.png"
    Image.new("RGB", (400, 600), (240, 240, 240)).save(path)
    return path


@pytest.mark.ml
def test_translate_image_writes_output(sample_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "out" / "page.png"
    translate_image(sample_image, out, source="ja", target="en")
    assert out.exists()
    # On a blank test image, the detector correctly finds no text regions.
    # The pipeline should still produce a valid output image.
    with Image.open(out) as im:
        assert im.size == (400, 600)


@pytest.mark.ml
def test_translate_directory_batch(tmp_path: Path) -> None:
    in_dir = tmp_path / "in"
    out_dir = tmp_path / "out"
    in_dir.mkdir()
    for name in ("p01.png", "p02.png", "p03.jpg"):
        Image.new("RGB", (200, 280), (255, 255, 255)).save(in_dir / name)
    (in_dir / "notes.txt").write_text("not an image")

    succeeded, failures = translate_directory(in_dir, out_dir, source="ja", target="en")
    assert succeeded == 3
    assert failures == []
    for name in ("p01.png", "p02.png", "p03.jpg"):
        assert (out_dir / name).exists()


@pytest.mark.ml
def test_translate_directory_recursive(tmp_path: Path) -> None:
    in_dir = tmp_path / "in"
    nested = in_dir / "chapter01"
    nested.mkdir(parents=True)
    Image.new("RGB", (100, 100), (255, 255, 255)).save(nested / "01.png")

    out_dir = tmp_path / "out"
    succeeded, failures = translate_directory(
        in_dir, out_dir, source="ja", target="en", recursive=True
    )
    assert succeeded == 1
    assert failures == []
    assert (out_dir / "chapter01" / "01.png").exists()


def test_sidecar_ping_pong() -> None:
    stdin = StringIO('{"id": "1", "kind": "ping"}\n')
    stdout = StringIO()
    run(stdin=stdin, stdout=stdout)
    response = json.loads(stdout.getvalue().strip())
    assert response == {"id": "1", "kind": "pong"}


def test_sidecar_info_includes_backends() -> None:
    stdin = StringIO('{"id": "x", "kind": "info"}\n')
    stdout = StringIO()
    run(stdin=stdin, stdout=stdout)
    response = json.loads(stdout.getvalue().strip())
    assert response["kind"] == "info_result"
    assert response["id"] == "x"
    assert "backends" in response
    assert isinstance(response["backends"], dict)


@pytest.mark.ml
def test_sidecar_translate_image_round_trip(sample_image: Path, tmp_path: Path) -> None:
    out = tmp_path / "translated.png"
    req = TranslateImageRequest(
        id="t1",
        input_path=str(sample_image),
        output_path=str(out),
        source="ja",
        target="en",
    )
    stdin = StringIO(req.model_dump_json() + "\n")
    stdout = StringIO()
    run(stdin=stdin, stdout=stdout)
    lines = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
    progress_lines = [m for m in lines if m["kind"] == "progress"]
    results = [m for m in lines if m["kind"] == "image_result"]
    assert progress_lines, "expected at least one progress event"
    assert len(results) == 1
    assert results[0]["output_path"] == str(out)
    assert out.exists()


def test_cli_help_runs() -> None:
    proc = subprocess.run(
        [sys.executable, "-m", "mojimaru", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "Mojimaru" in proc.stdout
