import type { Stage } from "@/lib/types";

interface ProgressBarProps {
  stage: Stage | null;
  current: number;
  total: number;
  note?: string;
}

const STAGE_LABEL: Record<Stage, string> = {
  detect: "Detecting bubbles",
  ocr: "Reading text",
  translate: "Translating",
  inpaint: "Cleaning bubbles",
  typeset: "Typesetting",
  io: "I/O",
};

export function ProgressBar({ stage, current, total, note }: ProgressBarProps) {
  const pct = total > 0 ? Math.min(100, (current / total) * 100) : 0;
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between text-xs text-washi-300">
        <span>{stage ? STAGE_LABEL[stage] : "Idle"}</span>
        <span className="font-mono text-washi-400">
          {current}/{total || "?"}
          {note ? ` · ${note}` : ""}
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-washi-900/80">
        <div
          className="h-full rounded-full bg-shu-500 transition-[width] duration-200"
          style={{ width: `${pct}%` }}
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={total || 100}
          aria-valuenow={current}
        />
      </div>
    </div>
  );
}
