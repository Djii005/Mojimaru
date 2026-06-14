from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from PIL import Image

from mojimaru import get_base_dir
from mojimaru.protocol import BBox, Bubble, Orientation

log = logging.getLogger(__name__)

_rtdetr_model: Any = None
_rtdetr_processor: Any = None
_rtdetr_attempted = False


_RTDETR_TEXT_LABELS = {"text_bubble", "text_free"}


def _get_rtdetr() -> Any:
    global _rtdetr_model, _rtdetr_processor, _rtdetr_attempted
    if _rtdetr_attempted:
        if _rtdetr_model is not None and _rtdetr_processor is not None:
            return (_rtdetr_model, _rtdetr_processor)
        return None
    _rtdetr_attempted = True

    try:
        from transformers import (
            RTDetrForObjectDetection,
            RTDetrImageProcessor,
        )

        model_name = "ogkalu/comic-text-and-bubble-detector"
        log.info("Loading RT-DETR model: %s", model_name)
        _rtdetr_processor = RTDetrImageProcessor.from_pretrained(model_name)
        _rtdetr_model = RTDetrForObjectDetection.from_pretrained(model_name)
        log.info("RT-DETR model loaded.")
        return (_rtdetr_model, _rtdetr_processor)
    except ImportError:
        log.debug("transformers not available for RT-DETR")
        return None
    except Exception:
        log.warning("RT-DETR load failed", exc_info=True)
        return None


def _detect_rtdetr(image: Image.Image) -> list[Bubble] | None:
    pair = _get_rtdetr()
    if pair is None:
        return None

    try:
        import torch

        model, processor = pair
        img_rgb = image.convert("RGB")

        inputs = processor(images=img_rgb, return_tensors="pt")
        with torch.no_grad():
            outputs = model(**inputs)

        target_sizes = torch.tensor([img_rgb.size[::-1]])
        results = processor.post_process_object_detection(
            outputs, target_sizes=target_sizes, threshold=0.3
        )[0]

        bubbles: list[Bubble] = []
        for score, label_id, box in zip(
            results["scores"], results["labels"], results["boxes"], strict=False
        ):
            label_name = model.config.id2label[label_id.item()]

            if label_name not in _RTDETR_TEXT_LABELS:
                continue

            x1, y1, x2, y2 = box.tolist()
            x1, y1 = max(0, int(x1)), max(0, int(y1))
            x2, y2 = min(img_rgb.width, int(x2)), min(img_rgb.height, int(y2))
            w, h = x2 - x1, y2 - y1

            if w < 10 or h < 10:
                continue

            bubbles.append(
                Bubble(
                    bbox=BBox(x=x1, y=y1, w=w, h=h),
                    orientation=_guess_orientation(w, h),
                    confidence=float(score),
                    label=label_name,
                )
            )

        if bubbles:
            bubbles.sort(key=lambda b: (b.bbox.y // 100, -b.bbox.x))
            log.info("RT-DETR detected %d text region(s)", len(bubbles))
            return bubbles
        return None

    except Exception:
        log.warning("RT-DETR inference failed", exc_info=True)
        return None


_yolo_model: Any = None
_yolo_attempted = False


def _get_yolo_model() -> Any:
    global _yolo_model, _yolo_attempted
    if _yolo_attempted:
        return _yolo_model
    _yolo_attempted = True

    model_path = os.environ.get("MOJIMARU_YOLO_MODEL")
    if not model_path:
        project_models = get_base_dir() / "models" / "yolo"
        for candidate in [
            project_models / "comic-text-detector.pt",
            project_models / "yolov8n.pt",
            Path.home() / ".mojimaru" / "models" / "comic-text-detector.pt",
            Path.home() / ".mojimaru" / "models" / "yolov8n.pt",
        ]:
            if candidate.exists():
                model_path = str(candidate)
                break

    if not model_path:
        log.debug("No YOLO model file found; skipping YOLO detection")
        return None

    try:
        import ultralytics

        ultralytics_any: Any = ultralytics
        log.info("Loading YOLO model from %s", model_path)
        _yolo_model = ultralytics_any.YOLO(model_path)
        log.info("YOLO model loaded.")
        return _yolo_model
    except Exception:
        log.debug("YOLO model load failed", exc_info=True)
        return None


def _detect_yolo(image: Image.Image) -> list[Bubble] | None:
    model = _get_yolo_model()
    if model is None:
        return None

    try:
        import numpy as np

        arr = np.array(image.convert("RGB"))
        results = model(arr, verbose=False)

        bubbles: list[Bubble] = []
        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                conf = float(box.conf[0])
                w = int(x2 - x1)
                h = int(y2 - y1)
                bubbles.append(
                    Bubble(
                        bbox=BBox(x=int(x1), y=int(y1), w=w, h=h),
                        orientation=_guess_orientation(w, h),
                        confidence=conf,
                    )
                )
        if bubbles:
            log.info("YOLO detected %d bubble(s)", len(bubbles))
            return bubbles
        return None
    except Exception:
        log.warning("YOLO inference failed", exc_info=True)
        return None


def detect_bubbles(image: Image.Image) -> list[Bubble]:
    result = _detect_rtdetr(image)
    if result:
        return result

    result = _detect_yolo(image)
    if result:
        return result

    log.warning("No detection backend produced results; returning empty list")
    return []


def _guess_orientation(w: int, h: int) -> Orientation:
    if h > w * 1.2:
        return "vertical"
    if w > h * 1.2:
        return "horizontal"
    return "unknown"
