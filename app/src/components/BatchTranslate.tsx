import { useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";

import { LanguagePicker } from "./LanguagePicker";
import { ProgressBar } from "./ProgressBar";
import { onProgress, translateBatch } from "@/lib/sidecar";
import type {
  BatchResult,
  ProgressEvent,
  SourceLang,
  Stage,
  TargetLang,
} from "@/lib/types";

export function BatchTranslate() {
  const [inputDir, setInputDir] = useState("");
  const [outputDir, setOutputDir] = useState("");
  const [source, setSource] = useState<SourceLang>("auto");
  const [target, setTarget] = useState<TargetLang>("en");
  const [recursive, setRecursive] = useState(false);
  const [running, setRunning] = useState(false);
  const [stage, setStage] = useState<Stage | null>(null);
  const [current, setCurrent] = useState(0);
  const [total, setTotal] = useState(0);
  const [note, setNote] = useState("");
  const [result, setResult] = useState<BatchResult | null>(null);
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

  async function pickDir(setter: (s: string) => void) {
    const path = await open({ directory: true, multiple: false });
    if (typeof path === "string") setter(path);
  }

  async function run() {
    if (!inputDir || !outputDir) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const r = await translateBatch({
        inputDir,
        outputDir,
        source,
        target,
        recursive,
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
        <h1 className="font-display text-2xl">Batch translate</h1>
        <p className="text-sm text-washi-400">
          Translate every image in a directory and write the results into
          another directory.
        </p>
      </header>

      <div className="panel space-y-4 p-5">
        <DirField
          label="Input directory"
          value={inputDir}
          onPick={() => pickDir(setInputDir)}
        />
        <DirField
          label="Output directory"
          value={outputDir}
          onPick={() => pickDir(setOutputDir)}
        />
        <LanguagePicker
          source={source}
          target={target}
          onSourceChange={setSource}
          onTargetChange={setTarget}
        />
        <label className="flex items-center gap-2 text-sm text-washi-300">
          <input
            type="checkbox"
            checked={recursive}
            onChange={(e) => setRecursive(e.target.checked)}
            className="h-4 w-4 rounded border-washi-900 bg-ink text-shu-500 focus:ring-shu-500"
          />
          Recurse into subdirectories
        </label>
        <div className="flex items-center justify-end gap-3 pt-1">
          <button
            type="button"
            className="btn-primary"
            disabled={!inputDir || !outputDir || running}
            onClick={run}
          >
            {running ? "Translating…" : "Translate batch"}
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
            <div className="space-y-2 text-sm text-washi-300">
              <p>
                <span className="text-shu-400">{result.succeeded}</span>{" "}
                succeeded ·{" "}
                <span className="text-shu-400">{result.failed}</span> failed
              </p>
              {result.failures.length > 0 && (
                <details className="rounded-lg border border-washi-900 bg-ink p-3">
                  <summary className="cursor-pointer text-washi-200">
                    View failures
                  </summary>
                  <ul className="mt-2 space-y-1 font-mono text-xs text-washi-400">
                    {result.failures.map((f) => (
                      <li key={f}>{f}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
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

function DirField({
  label,
  value,
  onPick,
}: {
  label: string;
  value: string;
  onPick: () => void;
}) {
  return (
    <div className="space-y-1.5">
      <span className="field-label block">{label}</span>
      <div className="flex gap-2">
        <input
          readOnly
          value={value}
          placeholder="No directory selected"
          className="field-input font-mono text-xs"
        />
        <button type="button" className="btn-ghost shrink-0" onClick={onPick}>
          Browse
        </button>
      </div>
    </div>
  );
}
