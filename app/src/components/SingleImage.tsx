import { useState } from "react";
import { open, save } from "@tauri-apps/plugin-dialog";

import { LanguagePicker } from "./LanguagePicker";
import { ProgressBar } from "./ProgressBar";
import { translateImage } from "@/lib/sidecar";
import type {
  ImageResult,
  ProgressEvent,
  SourceLang,
  Stage,
  TargetLang,
} from "@/lib/types";
import { onProgress } from "@/lib/sidecar";
import { useEffect } from "react";

export function SingleImage() {
  const [input, setInput] = useState<string>("");
  const [output, setOutput] = useState<string>("");
  const [source, setSource] = useState<SourceLang>("auto");
  const [target, setTarget] = useState<TargetLang>("en");
  const [running, setRunning] = useState(false);
  const [stage, setStage] = useState<Stage | null>(null);
  const [current, setCurrent] = useState(0);
  const [total, setTotal] = useState(0);
  const [note, setNote] = useState<string>("");
  const [result, setResult] = useState<ImageResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let unsub: (() => void) | undefined;
    onProgress((e: ProgressEvent) => {
      setStage(e.stage);
      setCurrent(e.current);
      setTotal(e.total);
      setNote(e.note);
    })
      .then((fn) => {
        unsub = fn;
      })
      .catch(() => {});
    return () => {
      unsub?.();
    };
  }, []);

  async function pickInput() {
    const path = await open({
      multiple: false,
      filters: [
        {
          name: "Images",
          extensions: ["png", "jpg", "jpeg", "webp", "bmp", "tif", "tiff"],
        },
      ],
    });
    if (typeof path === "string") setInput(path);
  }

  async function pickOutput() {
    const path = await save({
      defaultPath: input ? input.replace(/(\.[^./\\]+)$/, "_translated$1") : undefined,
      filters: [
        { name: "PNG", extensions: ["png"] },
        { name: "JPEG", extensions: ["jpg", "jpeg"] },
      ],
    });
    if (typeof path === "string") setOutput(path);
  }

  async function run() {
    if (!input || !output) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const r = await translateImage({
        inputPath: input,
        outputPath: output,
        source,
        target,
      });
      setResult(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setRunning(false);
    }
  }

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="font-display text-2xl">Single image</h1>
        <p className="text-sm text-washi-400">
          Translate one manga page. Pick an input image, choose where to save
          the result, and go.
        </p>
      </header>

      <div className="panel space-y-4 p-5">
        <PathField
          label="Input image"
          value={input}
          placeholder="No file selected"
          onPick={pickInput}
        />
        <PathField
          label="Output image"
          value={output}
          placeholder="Choose where to save"
          onPick={pickOutput}
        />
        <LanguagePicker
          source={source}
          target={target}
          onSourceChange={setSource}
          onTargetChange={setTarget}
        />
        <div className="flex items-center justify-end gap-3 pt-1">
          <button
            type="button"
            className="btn-primary"
            disabled={!input || !output || running}
            onClick={run}
          >
            {running ? "Translating…" : "Translate"}
          </button>
        </div>
      </div>

      {(running || result || error) && (
        <div className="panel space-y-3 p-5">
          <ProgressBar
            stage={stage}
            current={current}
            total={total}
            note={note}
          />
          {result && (
            <p className="text-sm text-washi-300">
              Wrote{" "}
              <span className="font-mono text-washi-100">
                {result.output_path}
              </span>{" "}
              · {result.bubbles.length} bubble(s).
            </p>
          )}
          {error && (
            <p className="text-sm text-shu-400" role="alert">
              {error}
            </p>
          )}
        </div>
      )}
    </section>
  );
}

interface PathFieldProps {
  label: string;
  value: string;
  placeholder?: string;
  onPick: () => void;
}

function PathField({ label, value, placeholder, onPick }: PathFieldProps) {
  return (
    <div className="space-y-1.5">
      <span className="field-label block">{label}</span>
      <div className="flex gap-2">
        <input
          readOnly
          value={value}
          placeholder={placeholder}
          className="field-input font-mono text-xs"
        />
        <button type="button" className="btn-ghost shrink-0" onClick={onPick}>
          Browse
        </button>
      </div>
    </div>
  );
}
