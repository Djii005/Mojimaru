import clsx from "clsx";

export type View = "single" | "batch" | "capture" | "settings";

interface SidebarProps {
  view: View;
  onChange: (v: View) => void;
}

const NAV: { id: View; label: string; jp: string; soon?: boolean }[] = [
  { id: "single", label: "Single image", jp: "一枚" },
  { id: "batch", label: "Batch", jp: "一括" },
  { id: "capture", label: "Screen capture", jp: "画面", soon: true },
  { id: "settings", label: "Settings", jp: "設定" },
];

export function Sidebar({ view, onChange }: SidebarProps) {
  return (
    <nav
      aria-label="Primary"
      className="flex w-52 shrink-0 flex-col gap-1 border-r border-washi-900/80 p-3"
    >
      {NAV.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => onChange(item.id)}
          aria-current={view === item.id ? "page" : undefined}
          disabled={item.soon}
          className={clsx(
            "group flex items-center justify-between rounded-xl px-3 py-2 text-left transition",
            view === item.id
              ? "bg-shu-500/15 text-washi-50 shadow-glow"
              : "text-washi-300 hover:bg-washi-900/40",
            item.soon && "cursor-not-allowed opacity-50",
          )}
        >
          <span className="flex flex-col">
            <span className="text-sm font-medium">{item.label}</span>
            <span className="font-jp text-[11px] text-washi-500">
              {item.jp}
            </span>
          </span>
          {item.soon && (
            <span className="rounded-md border border-washi-900 px-1.5 py-0.5 text-[9px] uppercase tracking-widest text-washi-500">
              soon
            </span>
          )}
        </button>
      ))}
    </nav>
  );
}
