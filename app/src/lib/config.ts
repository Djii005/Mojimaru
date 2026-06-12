/**
 * Local config persistence via Tauri filesystem plugin.
 *
 * Stores user preferences (translation provider, API key, font path) in a
 * JSON file in the app's data directory.
 */

import { appDataDir, join } from "@tauri-apps/api/path";
import { exists, mkdir, readTextFile, writeTextFile } from "@tauri-apps/plugin-fs";

export interface MojimaruConfig {
  translateProvider: "auto" | "sugoi" | "local" | "ct2" | "deepl" | "google" | "stub";
  translateApiKey: string;
  translateModelPath: string;
  fontPath: string;
}

const DEFAULT_CONFIG: MojimaruConfig = {
  translateProvider: "auto",
  translateApiKey: "",
  translateModelPath: "",
  fontPath: "",
};

const CONFIG_FILENAME = "settings.json";

async function configPath(): Promise<string> {
  const dir = await appDataDir();
  return join(dir, CONFIG_FILENAME);
}

export async function loadConfig(): Promise<MojimaruConfig> {
  try {
    const dir = await appDataDir();
    const path = await join(dir, CONFIG_FILENAME);
    if (!(await exists(path))) {
      return { ...DEFAULT_CONFIG };
    }
    const raw = await readTextFile(path);
    const parsed = JSON.parse(raw) as Partial<MojimaruConfig>;
    return { ...DEFAULT_CONFIG, ...parsed };
  } catch {
    return { ...DEFAULT_CONFIG };
  }
}

export async function saveConfig(config: MojimaruConfig): Promise<void> {
  const dir = await appDataDir();
  // Ensure directory exists
  if (!(await exists(dir))) {
    await mkdir(dir, { recursive: true });
  }
  const path = await configPath();
  await writeTextFile(path, JSON.stringify(config, null, 2));
}
