import { useState } from "react";

import { BatchTranslate } from "./components/BatchTranslate";
import { ScreenCapture } from "./components/ScreenCapture";
import { Settings } from "./components/Settings";
import { Sidebar, type View } from "./components/Sidebar";
import { SingleImage } from "./components/SingleImage";
import { TitleBar } from "./components/TitleBar";

export default function App() {
  const [view, setView] = useState<View>("single");

  return (
    <div className="flex h-full min-h-screen flex-col bg-ink bg-washi-grain bg-washi-grain text-washi-100">
      <TitleBar />
      <div className="flex min-h-0 flex-1">
        <Sidebar view={view} onChange={setView} />
        <main className="min-h-0 flex-1 overflow-y-auto p-8">
          {view === "single" && <SingleImage />}
          {view === "batch" && <BatchTranslate />}
          {view === "capture" && <ScreenCapture />}
          {view === "settings" && <Settings />}
        </main>
      </div>
    </div>
  );
}
