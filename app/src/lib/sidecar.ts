/**
 * Thin wrapper around the Tauri commands that drive the Python ML sidecar.
 *
 * The Rust side owns the actual child process and message routing; from React
 * we only call `invoke` for one-shot RPCs and subscribe to a single event
 * channel for streamed progress.
 */

import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

import type {
  BatchResult,
  ConfigureResult,
  ImageResult,
  InfoResult,
  ProgressEvent,
  SidecarMessage,
  SourceLang,
  TargetLang,
} from "./types";

export interface TranslateImageInput {
  inputPath: string;
  outputPath: string;
  source: SourceLang;
  target: TargetLang;
}

export interface TranslateBatchInput {
  inputDir: string;
  outputDir: string;
  source: SourceLang;
  target: TargetLang;
  recursive: boolean;
}

export interface ConfigureInput {
  translateProvider?: string;
  translateApiKey?: string;
  translateModelPath?: string;
  fontPath?: string;
}

export async function getInfo(): Promise<InfoResult> {
  return invoke<InfoResult>("sidecar_info");
}

export async function configure(
  input: ConfigureInput,
): Promise<ConfigureResult> {
  return invoke<ConfigureResult>("sidecar_configure", { input });
}

export async function translateImage(
  input: TranslateImageInput,
): Promise<ImageResult> {
  return invoke<ImageResult>("sidecar_translate_image", { input });
}

export async function translateBatch(
  input: TranslateBatchInput,
): Promise<BatchResult> {
  return invoke<BatchResult>("sidecar_translate_batch", { input });
}

export async function onProgress(
  handler: (event: ProgressEvent) => void,
): Promise<UnlistenFn> {
  return listen<SidecarMessage>("mojimaru://progress", (e) => {
    if (e.payload.kind === "progress") {
      handler(e.payload);
    }
  });
}
