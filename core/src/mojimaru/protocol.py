from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

SourceLang = Literal["ja", "zh", "ko", "auto"]
TargetLang = Literal["en", "id", "es", "fr", "de", "pt", "ru", "vi", "th"]
Orientation = Literal["horizontal", "vertical", "unknown"]


class BBox(BaseModel):
    x: int
    y: int
    w: int
    h: int


class Bubble(BaseModel):
    bbox: BBox
    orientation: Orientation = "unknown"
    confidence: float = 0.0
    label: str = ""
    source_text: str = ""
    translated_text: str = ""


class BackendDetail(BaseModel):
    name: str
    installed: bool
    active: bool
    description: str = ""
    stage: str = ""


class _RequestBase(BaseModel):
    id: str
    kind: str


class PingRequest(_RequestBase):
    kind: Literal["ping"] = "ping"


class InfoRequest(_RequestBase):
    kind: Literal["info"] = "info"


class TranslateImageRequest(_RequestBase):
    kind: Literal["translate_image"] = "translate_image"
    input_path: str
    output_path: str
    source: SourceLang = "auto"
    target: TargetLang = "en"


class TranslateBatchRequest(_RequestBase):
    kind: Literal["translate_batch"] = "translate_batch"
    input_dir: str
    output_dir: str
    source: SourceLang = "auto"
    target: TargetLang = "en"
    recursive: bool = False


class CancelRequest(_RequestBase):
    kind: Literal["cancel"] = "cancel"
    target_id: str


class ConfigureRequest(_RequestBase):
    kind: Literal["configure"] = "configure"
    translate_provider: str | None = None
    translate_api_key: str | None = None
    translate_model_path: str | None = None
    font_path: str | None = None


Request = Annotated[
    PingRequest
    | InfoRequest
    | TranslateImageRequest
    | TranslateBatchRequest
    | CancelRequest
    | ConfigureRequest,
    Field(discriminator="kind"),
]


class _MessageBase(BaseModel):
    id: str
    kind: str


class ProgressEvent(_MessageBase):
    kind: Literal["progress"] = "progress"
    stage: Literal["detect", "ocr", "translate", "inpaint", "typeset", "io"]
    current: int
    total: int
    note: str = ""


class ImageResult(_MessageBase):
    kind: Literal["image_result"] = "image_result"
    input_path: str
    output_path: str
    bubbles: list[Bubble] = Field(default_factory=list)


class BatchResult(_MessageBase):
    kind: Literal["batch_result"] = "batch_result"
    input_dir: str
    output_dir: str
    succeeded: int
    failed: int
    failures: list[str] = Field(default_factory=list)


class InfoResult(_MessageBase):
    kind: Literal["info_result"] = "info_result"
    version: str
    python: str
    backends: dict[str, bool]
    backend_details: list[BackendDetail] = Field(default_factory=list)
    translate_provider: str = "stub"
    font_path: str = ""


class ConfigureResult(_MessageBase):
    kind: Literal["configure_result"] = "configure_result"
    ok: bool = True
    message: str = ""


class PongResult(_MessageBase):
    kind: Literal["pong"] = "pong"


class ErrorResult(_MessageBase):
    kind: Literal["error"] = "error"
    message: str
    detail: str = ""


Message = Annotated[
    ProgressEvent
    | ImageResult
    | BatchResult
    | InfoResult
    | ConfigureResult
    | PongResult
    | ErrorResult,
    Field(discriminator="kind"),
]
