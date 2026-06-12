//! Tauri entrypoint for the Mojimaru desktop shell.

mod sidecar;

use std::sync::Arc;

use serde_json::{json, Value};
use tauri::{Manager, State};

use crate::sidecar::{ConfigureInput, Sidecar, TranslateBatchInput, TranslateImageInput};

struct AppState {
    sidecar: Arc<Sidecar>,
}

#[tauri::command]
async fn sidecar_info(state: State<'_, AppState>) -> Result<Value, String> {
    state
        .sidecar
        .request::<Value>("info", json!({}))
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn sidecar_configure(
    state: State<'_, AppState>,
    input: ConfigureInput,
) -> Result<Value, String> {
    let mut payload = serde_json::Map::new();
    if let Some(ref p) = input.translate_provider {
        payload.insert("translate_provider".into(), Value::String(p.clone()));
    }
    if let Some(ref k) = input.translate_api_key {
        payload.insert("translate_api_key".into(), Value::String(k.clone()));
    }
    if let Some(ref m) = input.translate_model_path {
        payload.insert("translate_model_path".into(), Value::String(m.clone()));
    }
    if let Some(ref f) = input.font_path {
        payload.insert("font_path".into(), Value::String(f.clone()));
    }
    state
        .sidecar
        .request::<Value>("configure", Value::Object(payload))
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn sidecar_translate_image(
    state: State<'_, AppState>,
    input: TranslateImageInput,
) -> Result<Value, String> {
    let payload = json!({
        "input_path": input.input_path,
        "output_path": input.output_path,
        "source": input.source,
        "target": input.target,
    });
    state
        .sidecar
        .request::<Value>("translate_image", payload)
        .await
        .map_err(|e| e.to_string())
}

#[tauri::command]
async fn sidecar_translate_batch(
    state: State<'_, AppState>,
    input: TranslateBatchInput,
) -> Result<Value, String> {
    let payload = json!({
        "input_dir": input.input_dir,
        "output_dir": input.output_dir,
        "source": input.source,
        "target": input.target,
        "recursive": input.recursive,
    });
    state
        .sidecar
        .request::<Value>("translate_batch", payload)
        .await
        .map_err(|e| e.to_string())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let handle = app.handle().clone();
            tauri::async_runtime::block_on(async move {
                let sidecar = Sidecar::spawn(handle.clone()).await?;
                handle.manage(AppState {
                    sidecar: Arc::new(sidecar),
                });
                Ok::<_, anyhow::Error>(())
            })?;
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            sidecar_info,
            sidecar_configure,
            sidecar_translate_image,
            sidecar_translate_batch
        ])
        .run(tauri::generate_context!())
        .expect("error while running mojimaru");
}

