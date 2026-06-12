import type { SourceLang, TargetLang } from "@/lib/types";

const SOURCES: { value: SourceLang; label: string }[] = [
  { value: "auto", label: "Auto-detect" },
  { value: "ja", label: "Japanese (日本語)" },
  { value: "zh", label: "Chinese (中文)" },
  { value: "ko", label: "Korean (한국어)" },
];

const TARGETS: { value: TargetLang; label: string }[] = [
  { value: "en", label: "English" },
  { value: "id", label: "Indonesian" },
  { value: "es", label: "Spanish" },
  { value: "fr", label: "French" },
  { value: "de", label: "German" },
  { value: "pt", label: "Portuguese" },
  { value: "ru", label: "Russian" },
  { value: "vi", label: "Vietnamese" },
  { value: "th", label: "Thai" },
];

interface Props {
  source: SourceLang;
  target: TargetLang;
  onSourceChange: (s: SourceLang) => void;
  onTargetChange: (t: TargetLang) => void;
}

export function LanguagePicker({
  source,
  target,
  onSourceChange,
  onTargetChange,
}: Props) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <label className="space-y-1.5">
        <span className="field-label block">From</span>
        <select
          className="field-input"
          value={source}
          onChange={(e) => onSourceChange(e.target.value as SourceLang)}
        >
          {SOURCES.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      <label className="space-y-1.5">
        <span className="field-label block">To</span>
        <select
          className="field-input"
          value={target}
          onChange={(e) => onTargetChange(e.target.value as TargetLang)}
        >
          {TARGETS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
