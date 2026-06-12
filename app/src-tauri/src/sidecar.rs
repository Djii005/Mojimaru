//! Python sidecar manager.
//!
//! Spawns `mojimaru serve` as a long-lived child process and exposes a
//! request/response API on top of its newline-delimited JSON protocol.
//!
//! Each in-flight request gets its own `oneshot` channel keyed by id. A
//! reader task on the child's stdout dispatches each parsed message to the
//! waiting caller and forwards `progress` events to the Tauri frontend.

use std::collections::HashMap;
use std::env;
use std::path::PathBuf;
use std::sync::Arc;

use anyhow::{anyhow, Result};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use tauri::{AppHandle, Emitter};
use tauri_plugin_shell::process::CommandEvent;
use tauri_plugin_shell::ShellExt;
use tokio::sync::{oneshot, Mutex};
use tokio::task::JoinHandle;
use uuid::Uuid;

/// Event channel name. Keep in sync with `app/src/lib/sidecar.ts`.
pub const PROGRESS_EVENT: &str = "mojimaru://progress";

type PendingMap = Arc<Mutex<HashMap<String, oneshot::Sender<Value>>>>;

pub struct Sidecar {
    child: Arc<Mutex<tauri_plugin_shell::process::CommandChild>>,
    pending: PendingMap,
    _reader: JoinHandle<()>,
}

impl Sidecar {
    /// Spawn the Python sidecar. Looks up the interpreter in this order:
    ///   1. `MOJIMARU_PYTHON` environment variable,
    ///   2. `../../core/.venv/bin/python` (dev layout),
    ///   3. `python3` on PATH.
    /// In production builds, falls back to Tauri's bundled sidecar binary.
    pub async fn spawn(app: AppHandle) -> Result<Self> {
        let python = resolve_python();
        let core_src = resolve_core_src();

        let command = if cfg!(debug_assertions) || resolve_python_exists() {
            let python_str = python.to_string_lossy().into_owned();
            let mut cmd = app.shell().command(python_str);
            cmd = cmd.args(["-m", "mojimaru", "serve"]);
            if let Some(src) = core_src {
                cmd = cmd.env("PYTHONPATH", src);
            }
            cmd
        } else {
            app.shell().sidecar("mojimaru")?
        };

        let (mut rx, child) = command
            .spawn()
            .map_err(|e| anyhow!("failed to spawn sidecar: {e}"))?;

        let pending: PendingMap = Arc::new(Mutex::new(HashMap::new()));
        let reader_pending = pending.clone();
        let app_clone = app.clone();
        let reader = tokio::spawn(async move {
            let mut buffer = Vec::new();
            while let Some(event) = rx.recv().await {
                match event {
                    CommandEvent::Stdout(data) => {
                        buffer.extend_from_slice(&data);
                        while let Some(idx) = buffer.iter().position(|&b| b == b'\n') {
                            let line_bytes = buffer.drain(..=idx).collect::<Vec<u8>>();
                            let line = String::from_utf8_lossy(&line_bytes);
                            let trimmed = line.trim();
                            if trimmed.is_empty() {
                                continue;
                            }
                            let Ok(payload) = serde_json::from_str::<Value>(trimmed) else {
                                eprintln!("sidecar: unparseable line: {trimmed}");
                                continue;
                            };
                            let kind = payload
                                .get("kind")
                                .and_then(Value::as_str)
                                .unwrap_or("")
                                .to_string();
                            let id = payload
                                .get("id")
                                .and_then(Value::as_str)
                                .unwrap_or("")
                                .to_string();

                            if kind == "progress" {
                                let _ = app_clone.emit(PROGRESS_EVENT, payload);
                                continue;
                            }

                            let mut map = reader_pending.lock().await;
                            if let Some(tx) = map.remove(&id) {
                                let _ = tx.send(payload);
                            }
                        }
                    }
                    CommandEvent::Stderr(data) => {
                        let msg = String::from_utf8_lossy(&data);
                        eprint!("sidecar stderr: {msg}");
                    }
                    CommandEvent::Terminated(status) => {
                        eprintln!("sidecar terminated with code: {:?}", status.code);
                        break;
                    }
                    CommandEvent::Error(err) => {
                        eprintln!("sidecar process error: {err}");
                        break;
                    }
                    _ => {}
                }
            }
        });

        Ok(Self {
            child: Arc::new(Mutex::new(child)),
            pending,
            _reader: reader,
        })
    }

    /// Send a request and await the matching response.
    pub async fn request<T: for<'de> Deserialize<'de>>(
        &self,
        kind: &str,
        extra: Value,
    ) -> Result<T> {
        let id = Uuid::new_v4().to_string();
        let (tx, rx) = oneshot::channel();
        self.pending.lock().await.insert(id.clone(), tx);

        let mut payload = match extra {
            Value::Object(map) => map,
            _ => serde_json::Map::new(),
        };
        payload.insert("id".into(), Value::String(id.clone()));
        payload.insert("kind".into(), Value::String(kind.to_string()));

        let mut line = serde_json::to_vec(&Value::Object(payload))?;
        line.push(b'\n');

        {
            let mut child = self.child.lock().await;
            child
                .write(&line)
                .map_err(|e| anyhow!("failed to write to sidecar stdin: {e}"))?;
        }

        let resp = rx
            .await
            .map_err(|_| anyhow!("sidecar dropped before responding to {kind}"))?;

        if resp.get("kind").and_then(Value::as_str) == Some("error") {
            let msg = resp
                .get("message")
                .and_then(Value::as_str)
                .unwrap_or("sidecar error")
                .to_string();
            return Err(anyhow!(msg));
        }

        Ok(serde_json::from_value(resp)?)
    }
}

fn resolve_python_exists() -> bool {
    let python = resolve_python();
    python.exists()
}

fn resolve_python() -> PathBuf {
    if let Ok(env_path) = env::var("MOJIMARU_PYTHON") {
        return PathBuf::from(env_path);
    }

    let cwd = env::current_dir().unwrap_or_else(|_| PathBuf::from("."));
    let dev_venv = cwd
        .join("..")
        .join("..")
        .join("core")
        .join(".venv")
        .join(if cfg!(windows) {
            "Scripts/python.exe"
        } else {
            "bin/python"
        });
    if dev_venv.exists() {
        return dev_venv;
    }

    PathBuf::from(if cfg!(windows) { "python.exe" } else { "python3" })
}

fn resolve_core_src() -> Option<String> {
    let cwd = env::current_dir().ok()?;
    let src = cwd.join("..").join("..").join("core").join("src");
    if src.exists() {
        Some(src.to_string_lossy().into_owned())
    } else {
        None
    }
}

/// Tauri serialises `#[command]` arguments from JS using camelCase by
/// default, so the structs we deserialise into must opt into the same
/// rename. Without this, calls from `app/src/lib/sidecar.ts` fail with
/// `missing field "input_path"` and friends.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TranslateImageInput {
    pub input_path: String,
    pub output_path: String,
    pub source: String,
    pub target: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct TranslateBatchInput {
    pub input_dir: String,
    pub output_dir: String,
    pub source: String,
    pub target: String,
    pub recursive: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct ConfigureInput {
    pub translate_provider: Option<String>,
    pub translate_api_key: Option<String>,
    pub translate_model_path: Option<String>,
    pub font_path: Option<String>,
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn translate_image_input_deserialises_camel_case() {
        // The TS layer in app/src/lib/sidecar.ts sends these fields camelCased.
        let v = json!({
            "inputPath": "/in.png",
            "outputPath": "/out.png",
            "source": "auto",
            "target": "en",
        });
        let parsed: TranslateImageInput = serde_json::from_value(v).expect("camelCase parse");
        assert_eq!(parsed.input_path, "/in.png");
        assert_eq!(parsed.output_path, "/out.png");
    }

    #[test]
    fn translate_batch_input_deserialises_camel_case() {
        let v = json!({
            "inputDir": "/in",
            "outputDir": "/out",
            "source": "auto",
            "target": "en",
            "recursive": true,
        });
        let parsed: TranslateBatchInput = serde_json::from_value(v).expect("camelCase parse");
        assert_eq!(parsed.input_dir, "/in");
        assert!(parsed.recursive);
    }
}
