from __future__ import annotations

import json
import os
import sys

os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
import traceback
from pathlib import Path
from typing import Any, TextIO

from pydantic import TypeAdapter, ValidationError

from mojimaru import __version__, get_base_dir
from mojimaru.pipeline import translate_directory, translate_image
from mojimaru.protocol import (
    BackendDetail,
    BatchResult,
    Bubble,
    CancelRequest,
    ConfigureRequest,
    ConfigureResult,
    ErrorResult,
    ImageResult,
    InfoRequest,
    InfoResult,
    Message,
    PingRequest,
    PongResult,
    ProgressEvent,
    Request,
    TranslateBatchRequest,
    TranslateImageRequest,
)

REQUEST_ADAPTER: TypeAdapter[Request] = TypeAdapter(Request)
MESSAGE_ADAPTER: TypeAdapter[Message] = TypeAdapter(Message)


def _detect_backends() -> dict[str, bool]:
    backends: dict[str, bool] = {}
    for name in ("manga_ocr", "paddleocr", "ultralytics", "cv2"):
        try:
            __import__(name)
            backends[name] = True
        except ImportError:
            backends[name] = False
    return backends


def _detect_backend_details() -> list[BackendDetail]:
    details: list[BackendDetail] = []

    try:
        __import__("manga_ocr")
        installed = True
    except ImportError:
        installed = False
    details.append(
        BackendDetail(
            name="manga_ocr",
            installed=installed,
            active=installed,
            description="Japanese manga OCR (kha-white/manga-ocr)",
            stage="ocr",
        )
    )

    try:
        __import__("transformers")
        rtdetr_installed = True
    except ImportError:
        rtdetr_installed = False
    details.append(
        BackendDetail(
            name="rtdetr_comic",
            installed=rtdetr_installed,
            active=rtdetr_installed,
            description="RT-DETR comic text & bubble detector (ogkalu/comic-text-and-bubble-detector)",
            stage="detect",
        )
    )

    try:
        __import__("ultralytics")
        installed = True
    except ImportError:
        installed = False
    project_yolo = get_base_dir() / "models" / "yolo"
    has_model = bool(os.environ.get("MOJIMARU_YOLO_MODEL")) or any(
        p.exists()
        for p in [
            project_yolo / "comic-text-detector.pt",
            project_yolo / "yolov8n.pt",
            Path.home() / ".mojimaru" / "models" / "comic-text-detector.pt",
            Path.home() / ".mojimaru" / "models" / "yolov8n.pt",
        ]
    )
    details.append(
        BackendDetail(
            name="ultralytics",
            installed=installed,
            active=installed and has_model,
            description="YOLO object detection for speech bubbles"
            + ("" if has_model else " (no model file found)"),
            stage="detect",
        )
    )

    try:
        __import__("cv2")
        installed = True
    except ImportError:
        installed = False
    details.append(
        BackendDetail(
            name="cv2",
            installed=installed,
            active=installed,
            description="OpenCV for inpainting & image processing",
            stage="inpaint",
        )
    )

    return details


def _get_translate_provider() -> str:
    from mojimaru.translate import _get_provider

    return _get_provider()


def _get_font_path() -> str:
    return os.environ.get("MOJIMARU_FONT_PATH", "")


def _emit(stream: TextIO, message: Message) -> None:
    try:
        stream.write(message.model_dump_json() + "\n")
        stream.flush()
    except OSError:
        pass


def _handle(req: Request, stdout: TextIO) -> Message:
    if isinstance(req, PingRequest):
        return PongResult(id=req.id)

    if isinstance(req, InfoRequest):
        return InfoResult(
            id=req.id,
            version=__version__,
            python=sys.version.split()[0],
            backends=_detect_backends(),
            backend_details=_detect_backend_details(),
            translate_provider=_get_translate_provider(),
            font_path=_get_font_path(),
        )

    if isinstance(req, ConfigureRequest):
        try:
            from mojimaru.translate import configure as configure_translate

            if (
                req.translate_provider is not None
                or req.translate_api_key is not None
                or req.translate_model_path is not None
            ):
                configure_translate(
                    provider=req.translate_provider,
                    api_key=req.translate_api_key,
                    model_path=req.translate_model_path,
                )

            if req.font_path is not None:
                os.environ["MOJIMARU_FONT_PATH"] = req.font_path

            return ConfigureResult(id=req.id, ok=True, message="configuration updated")
        except Exception as exc:
            return ConfigureResult(id=req.id, ok=False, message=str(exc))

    if isinstance(req, TranslateImageRequest):

        def on_progress(stage: Any, current: int, total: int, note: str) -> None:
            _emit(
                stdout,
                ProgressEvent(
                    id=req.id,
                    stage=stage,
                    current=current,
                    total=total,
                    note=note,
                ),
            )

        result = translate_image(
            Path(req.input_path),
            Path(req.output_path),
            source=req.source,
            target=req.target,
            on_progress=on_progress,
        )
        return ImageResult(
            id=req.id,
            input_path=str(result.input_path),
            output_path=str(result.output_path),
            bubbles=[Bubble.model_validate(b.model_dump()) for b in result.bubbles],
        )

    if isinstance(req, TranslateBatchRequest):

        def on_progress(stage: Any, current: int, total: int, note: str) -> None:
            _emit(
                stdout,
                ProgressEvent(
                    id=req.id,
                    stage=stage,
                    current=current,
                    total=total,
                    note=note,
                ),
            )

        succeeded, failures = translate_directory(
            Path(req.input_dir),
            Path(req.output_dir),
            source=req.source,
            target=req.target,
            recursive=req.recursive,
            on_progress=on_progress,
        )
        return BatchResult(
            id=req.id,
            input_dir=req.input_dir,
            output_dir=req.output_dir,
            succeeded=succeeded,
            failed=len(failures),
            failures=[f"{p}: {msg}" for p, msg in failures],
        )

    if isinstance(req, CancelRequest):
        return PongResult(id=req.id)

    return ErrorResult(id=req.id, message=f"unhandled request kind: {req.kind}")


def run(stdin: TextIO = sys.stdin, stdout: TextIO = sys.stdout) -> None:
    for raw in stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
            req = REQUEST_ADAPTER.validate_python(payload)
        except (json.JSONDecodeError, ValidationError) as exc:
            _emit(
                stdout,
                ErrorResult(
                    id=str(payload.get("id", ""))
                    if isinstance(payload := _safe_json(line), dict)
                    else "",
                    message="invalid request",
                    detail=str(exc),
                ),
            )
            continue

        try:
            response = _handle(req, stdout)
        except Exception as exc:
            traceback.print_exc(file=sys.stderr)
            response = ErrorResult(id=req.id, message=str(exc), detail=type(exc).__name__)
        _emit(stdout, response)


def _safe_json(line: str) -> object:
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None
