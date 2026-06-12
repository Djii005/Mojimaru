export type SourceLang = "ja" | "zh" | "ko" | "auto";
export type TargetLang =
  | "en"
  | "id"
  | "es"
  | "fr"
  | "de"
  | "pt"
  | "ru"
  | "vi"
  | "th";

export type Stage =
  | "detect"
  | "ocr"
  | "translate"
  | "inpaint"
  | "typeset"
  | "io";

export interface BBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Bubble {
  bbox: BBox;
  orientation: "horizontal" | "vertical" | "unknown";
  confidence: number;
  source_text: string;
  translated_text: string;
}

export interface ProgressEvent {
  id: string;
  kind: "progress";
  stage: Stage;
  current: number;
  total: number;
  note: string;
}

export interface ImageResult {
  id: string;
  kind: "image_result";
  input_path: string;
  output_path: string;
  bubbles: Bubble[];
}

export interface BatchResult {
  id: string;
  kind: "batch_result";
  input_dir: string;
  output_dir: string;
  succeeded: number;
  failed: number;
  failures: string[];
}

export interface BackendDetail {
  name: string;
  installed: boolean;
  active: boolean;
  description: string;
  stage: string;
}

export interface InfoResult {
  id: string;
  kind: "info_result";
  version: string;
  python: string;
  backends: Record<string, boolean>;
  backend_details: BackendDetail[];
  translate_provider: string;
  font_path: string;
}

export interface ConfigureResult {
  id: string;
  kind: "configure_result";
  ok: boolean;
  message: string;
}

export interface PongResult {
  id: string;
  kind: "pong";
}

export interface ErrorResult {
  id: string;
  kind: "error";
  message: string;
  detail: string;
}

export type SidecarMessage =
  | ProgressEvent
  | ImageResult
  | BatchResult
  | InfoResult
  | ConfigureResult
  | PongResult
  | ErrorResult;
