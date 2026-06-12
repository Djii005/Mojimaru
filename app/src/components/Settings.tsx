import { useCallback, useEffect, useState } from "react";

import { open } from "@tauri-apps/plugin-dialog";

import { loadConfig, saveConfig, type MojimaruConfig } from "@/lib/config";
import { configure, getInfo } from "@/lib/sidecar";
import type { BackendDetail, InfoResult } from "@/lib/types";

/* ------------------------------------------------------------------ */
/*  Status badge                                                       */
/* ------------------------------------------------------------------ */

function StatusBadge({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium ${
        ok
          ? "bg-emerald-500/15 text-emerald-400"
          : "bg-washi-900/60 text-washi-500"
      }`}
    >
      <span
        className={`inline-block h-1.5 w-1.5 rounded-full ${
          ok ? "bg-emerald-400 shadow-[0_0_6px_rgba(52,211,153,0.5)]" : "bg-washi-600"
        }`}
      />
      {ok ? "Active" : "Inactive"}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Backend card                                                       */
/* ------------------------------------------------------------------ */

function BackendCard({ detail }: { detail: BackendDetail }) {
  const stageLabels: Record<string, string> = {
    ocr: "OCR",
    detect: "Detection",
    inpaint: "Inpainting",
    typeset: "Typesetting",
    translate: "Translation",
  };

  return (
    <div className="flex items-start justify-between rounded-xl border border-washi-900/80 bg-ink px-4 py-3 transition hover:border-washi-900">
      <div className="space-y-1">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm text-washi-100">{detail.name}</span>
          <span className="rounded-md bg-washi-900/60 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-washi-500">
            {stageLabels[detail.stage] ?? detail.stage}
          </span>
        </div>
        <p className="text-xs text-washi-400">{detail.description}</p>
      </div>
      <StatusBadge ok={detail.active} />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Section wrapper                                                    */
/* ------------------------------------------------------------------ */

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="panel space-y-4 p-5">
      <div>
        <h2 className="text-base font-medium text-washi-100">{title}</h2>
        {subtitle && (
          <p className="mt-0.5 text-xs text-washi-400">{subtitle}</p>
        )}
      </div>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                     */
/* ------------------------------------------------------------------ */

export function Settings() {
  const [info, setInfo] = useState<InfoResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<MojimaruConfig | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveMessage, setSaveMessage] = useState("");

  // Load sidecar info + config on mount
  useEffect(() => {
    getInfo()
      .then(setInfo)
      .catch((e) => setError(String(e)));
    loadConfig().then(setConfig);
  }, []);

  const refreshInfo = useCallback(() => {
    setError(null);
    getInfo()
      .then(setInfo)
      .catch((e) => setError(String(e)));
  }, []);

  const handleSave = useCallback(async () => {
    if (!config) return;
    setSaving(true);
    setSaveMessage("");
    try {
      // Save to disk
      await saveConfig(config);

      // Push to sidecar
      await configure({
        translateProvider: config.translateProvider,
        translateApiKey: config.translateApiKey,
        translateModelPath: config.translateModelPath,
        fontPath: config.fontPath,
      });

      setSaveMessage("Settings saved");
      // Refresh info to see updated state
      refreshInfo();
      setTimeout(() => setSaveMessage(""), 3000);
    } catch (e) {
      setSaveMessage(`Error: ${e}`);
    } finally {
      setSaving(false);
    }
  }, [config, refreshInfo]);

  const handleFontPick = useCallback(async () => {
    const selected = await open({
      multiple: false,
      filters: [
        { name: "Font files", extensions: ["ttf", "otf", "woff", "woff2"] },
      ],
    });
    if (selected && typeof selected === "string") {
      setConfig((prev) => (prev ? { ...prev, fontPath: selected } : prev));
    }
  }, []);

  const handleModelPick = useCallback(async () => {
    const selected = await open({
      multiple: false,
      directory: true,
    });
    if (selected && typeof selected === "string") {
      setConfig((prev) => (prev ? { ...prev, translateModelPath: selected } : prev));
    }
  }, []);

  const updateConfig = useCallback(
    (patch: Partial<MojimaruConfig>) => {
      setConfig((prev) => (prev ? { ...prev, ...patch } : prev));
    },
    [],
  );

  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="font-display text-2xl">Settings</h1>
        <p className="text-sm text-washi-400">
          Diagnostics, ML backends, and pipeline configuration.
        </p>
      </header>

      {/* ---------- Sidecar diagnostics ---------- */}
      <Section title="Sidecar" subtitle="Python ML pipeline process">
        {error && (
          <div className="flex items-center justify-between rounded-lg border border-shu-700/40 bg-shu-700/10 px-4 py-2.5">
            <p className="text-sm text-shu-400" role="alert">
              {error}
            </p>
            <button
              type="button"
              onClick={refreshInfo}
              className="btn-ghost text-xs"
            >
              Retry
            </button>
          </div>
        )}
        {info && (
          <div className="space-y-3">
            <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
              <dt className="text-washi-400">Status</dt>
              <dd>
                <StatusBadge ok={true} />
              </dd>
              <dt className="text-washi-400">Version</dt>
              <dd className="font-mono text-washi-100">{info.version}</dd>
              <dt className="text-washi-400">Python</dt>
              <dd className="font-mono text-washi-100">{info.python}</dd>
              <dt className="text-washi-400">Translation</dt>
              <dd className="font-mono text-washi-100">
                {info.translate_provider === "auto"
                  ? "Auto-detect"
                  : info.translate_provider}
              </dd>
              {info.font_path && (
                <>
                  <dt className="text-washi-400">Font</dt>
                  <dd className="truncate font-mono text-xs text-washi-100">
                    {info.font_path}
                  </dd>
                </>
              )}
            </dl>
            <button
              type="button"
              onClick={refreshInfo}
              className="btn-ghost text-xs"
            >
              Refresh
            </button>
          </div>
        )}
        {!info && !error && (
          <div className="flex items-center gap-2 text-sm text-washi-400">
            <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-washi-500 border-t-transparent" />
            Connecting to sidecar…
          </div>
        )}
      </Section>

      {/* ---------- ML Backends ---------- */}
      {info && (
        <Section
          title="ML Backends"
          subtitle="Installed Python packages powering each pipeline stage"
        >
          <div className="grid gap-2 sm:grid-cols-2">
            {info.backend_details.length > 0
              ? info.backend_details.map((d) => (
                  <BackendCard key={d.name} detail={d} />
                ))
              : Object.entries(info.backends).map(([name, ok]) => (
                  <BackendCard
                    key={name}
                    detail={{
                      name,
                      installed: ok,
                      active: ok,
                      description: "",
                      stage: "",
                    }}
                  />
                ))}
          </div>
          <p className="text-xs text-washi-400">
            Missing backends fall back to stubs. Install extras (e.g.{" "}
            <span className="font-mono">pip install "mojimaru[ml]"</span>) to
            enable real ML.
          </p>
        </Section>
      )}

      {/* ---------- Translation Provider ---------- */}
      {config && (
        <Section
          title="Translation"
          subtitle="Configure which translation service to use"
        >
          <div className="space-y-3">
            <div>
              <label
                htmlFor="translate-provider"
                className="field-label mb-1 block"
              >
                Provider
              </label>
              <select
                id="translate-provider"
                value={config.translateProvider}
                onChange={(e) =>
                  updateConfig({
                    translateProvider: e.target.value as MojimaruConfig["translateProvider"],
                  })
                }
                className="field-input max-w-xs"
              >
                <option value="auto">Auto-detect (local first, then cloud)</option>
                <option value="sugoi">Local — Sugoi / MarianMT</option>
                <option value="ct2">Local — CTranslate2 (Sugoi native)</option>
                <option value="deepl">DeepL API</option>
                <option value="google">Google Cloud Translation API</option>
                <option value="stub">Stub (echo original text)</option>
              </select>
              <p className="mt-1 text-xs text-washi-500">
                {config.translateProvider === "auto"
                  ? "Tries local models first, then cloud APIs if a key is set."
                  : config.translateProvider === "sugoi"
                    ? "Uses Hugging Face transformers + MarianMT. Downloads Helsinki-NLP/opus-mt-ja-en on first use (~300MB)."
                    : config.translateProvider === "ct2"
                      ? "Faster inference using CTranslate2 format. Requires ctranslate2 + sentencepiece packages."
                      : config.translateProvider === "deepl"
                        ? "Best cloud quality for CJK→EN."
                        : config.translateProvider === "google"
                          ? "Broader language support via Google Cloud."
                          : "Returns original text with a marker — for testing only."}
              </p>
            </div>

            {/* Model path (for local providers) */}
            {(config.translateProvider === "sugoi" ||
              config.translateProvider === "ct2" ||
              config.translateProvider === "auto") && (
              <div>
                <label
                  htmlFor="translate-model-path"
                  className="field-label mb-1 block"
                >
                  Model directory (optional)
                </label>
                <div className="flex items-end gap-2">
                  <input
                    id="translate-model-path"
                    type="text"
                    value={config.translateModelPath}
                    onChange={(e) =>
                      updateConfig({ translateModelPath: e.target.value })
                    }
                    placeholder="Auto-detect (Helsinki-NLP or ~/.mojimaru/models/sugoi)"
                    className="field-input flex-1"
                    readOnly
                  />
                  <button
                    type="button"
                    onClick={handleModelPick}
                    className="btn-ghost shrink-0"
                  >
                    Browse
                  </button>
                  {config.translateModelPath && (
                    <button
                      type="button"
                      onClick={() => updateConfig({ translateModelPath: "" })}
                      className="btn-ghost shrink-0 text-washi-500"
                    >
                      Clear
                    </button>
                  )}
                </div>
                <p className="mt-1 text-xs text-washi-500">
                  Point to a local Sugoi model directory, or leave empty to auto-detect / download from Hugging Face.
                </p>
              </div>
            )}

            {/* API key (for cloud providers) */}
            {(config.translateProvider === "deepl" ||
              config.translateProvider === "google" ||
              config.translateProvider === "auto") && (
              <div>
                <label
                  htmlFor="translate-api-key"
                  className="field-label mb-1 block"
                >
                  API Key{config.translateProvider === "auto" ? " (optional)" : ""}
                </label>
                <input
                  id="translate-api-key"
                  type="password"
                  value={config.translateApiKey}
                  onChange={(e) =>
                    updateConfig({ translateApiKey: e.target.value })
                  }
                  placeholder={
                    config.translateProvider === "deepl"
                      ? "DeepL API key (ends with :fx for free tier)"
                      : config.translateProvider === "google"
                        ? "Google Cloud API key"
                        : "DeepL or Google API key (cloud fallback)"
                  }
                  className="field-input max-w-md"
                />
                <p className="mt-1 text-xs text-washi-500">
                  {config.translateProvider === "deepl"
                    ? "Get a free key at deepl.com/pro — 500K chars/month."
                    : config.translateProvider === "google"
                      ? "Requires a Google Cloud project with Translation API enabled."
                      : "Optional — used as fallback when local models aren't available."}
                </p>
              </div>
            )}
          </div>
        </Section>
      )}

      {/* ---------- Typesetting ---------- */}
      {config && (
        <Section
          title="Typesetting"
          subtitle="Font for rendered translated text"
        >
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label
                htmlFor="font-path"
                className="field-label mb-1 block"
              >
                Font file
              </label>
              <input
                id="font-path"
                type="text"
                value={config.fontPath}
                onChange={(e) =>
                  updateConfig({ fontPath: e.target.value })
                }
                placeholder="Default system font"
                className="field-input"
                readOnly
              />
            </div>
            <button
              type="button"
              onClick={handleFontPick}
              className="btn-ghost shrink-0"
            >
              Browse
            </button>
            {config.fontPath && (
              <button
                type="button"
                onClick={() => updateConfig({ fontPath: "" })}
                className="btn-ghost shrink-0 text-washi-500"
              >
                Clear
              </button>
            )}
          </div>
          <p className="text-xs text-washi-500">
            Pick a .ttf or .otf font. If empty, Pillow's default font is used.
          </p>
        </Section>
      )}

      {/* ---------- Save button ---------- */}
      {config && (
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving}
            className="btn-primary"
          >
            {saving ? "Saving…" : "Save settings"}
          </button>
          {saveMessage && (
            <span
              className={`text-sm ${
                saveMessage.startsWith("Error")
                  ? "text-shu-400"
                  : "text-emerald-400"
              }`}
            >
              {saveMessage}
            </span>
          )}
        </div>
      )}

      {/* ---------- About ---------- */}
      <Section title="About">
        <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-1 text-sm">
          <dt className="text-washi-400">App</dt>
          <dd className="text-washi-100">
            Mojimaru 文字丸 v{info?.version ?? "0.1.0"}
          </dd>
          <dt className="text-washi-400">License</dt>
          <dd className="text-washi-100">MIT</dd>
          <dt className="text-washi-400">Source</dt>
          <dd>
            <a
              href="https://github.com/Djii005/Mojimaru"
              target="_blank"
              rel="noopener noreferrer"
              className="text-shu-400 underline underline-offset-2 transition hover:text-shu-300"
            >
              github.com/Djii005/Mojimaru
            </a>
          </dd>
        </dl>
      </Section>
    </section>
  );
}
