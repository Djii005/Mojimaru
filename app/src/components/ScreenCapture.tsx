/**
 * Placeholder for the live screen-capture translation mode (R7).
 *
 * Planned design:
 *  1. Global hotkey arms "capture mode".
 *  2. User draws a region on the screen.
 *  3. Region is sent to the sidecar; bubbles + translations come back.
 *  4. A transparent always-on-top window draws the translated text on top.
 */
export function ScreenCapture() {
  return (
    <section className="space-y-6">
      <header className="space-y-1">
        <h1 className="font-display text-2xl">Screen capture</h1>
        <p className="text-sm text-washi-400">
          Translate manga while reading online. Coming in v0.3.
        </p>
      </header>
      <div className="panel space-y-3 p-5 text-sm text-washi-300">
        <p>
          This mode will let you bind a global hotkey, drag-select a region of
          your screen, and see the translated text drawn over the original
          page through a transparent overlay window.
        </p>
        <p className="text-washi-400">
          Tracked in <span className="font-mono">issues/#screen-capture</span>.
        </p>
      </div>
    </section>
  );
}
