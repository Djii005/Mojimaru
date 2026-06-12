/**
 * App title bar. Uses the native window chrome for now; later this can be
 * swapped for a custom Tauri decorations:false bar to lean further into the
 * otaku theme.
 */
export function TitleBar() {
  return (
    <header className="flex items-center gap-3 border-b border-washi-900/80 px-5 py-3">
      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-shu-500 font-display text-washi-50">
        丸
      </div>
      <div>
        <div className="font-display text-lg leading-none">Mojimaru</div>
        <div className="text-[10px] uppercase tracking-[0.3em] text-washi-400">
          文字丸 · manga translator
        </div>
      </div>
    </header>
  );
}
