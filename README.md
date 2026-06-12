# Mojimaru 文字丸

Desktop manga translator. Drop in a manga page, get back a translated version with text replaced in the bubbles.

![Tauri](https://img.shields.io/badge/Tauri_2-FFC131?logo=tauri&logoColor=333)
![React](https://img.shields.io/badge/React-61DAFB?logo=react&logoColor=333)
![Python](https://img.shields.io/badge/Python_3.12+-3776AB?logo=python&logoColor=fff)

## What it does

1. **Detects** speech bubbles and text regions using an RT-DETR model trained on manga/comics
2. **Reads** the Japanese text with manga-ocr
3. **Translates** using local Sugoi/MarianMT models (no API keys needed) or optionally DeepL/Google
4. **Cleans** the original text with OpenCV inpainting
5. **Typesets** the English translation back into the bubbles with auto-sized fonts

Everything runs locally on your machine. No cloud dependencies unless you want them.

## Project structure

```
Mojimaru/
├── app/              Tauri 2 desktop shell (Rust + React + TypeScript)
│   ├── src/          React frontend
│   └── src-tauri/    Rust backend + sidecar manager
├── core/             Python ML pipeline
│   ├── src/mojimaru/ Pipeline modules (detect, ocr, translate, inpaint, typeset)
│   ├── models/       Model weights (not committed, see below)
│   └── tests/        Pytest tests
└── docs/             Architecture & dev docs
```

## Setup

### Prerequisites

- **Node.js** 18+ and **pnpm**
- **Rust** (latest stable)
- **Python** 3.12+

### Install

```bash
# Frontend
cd app
pnpm install

# Backend
cd ../core
python -m venv .venv
.venv/Scripts/activate  # Windows
pip install -e ".[dev]"
```

### Models

The ML models are not committed to git (too large). On first run, the translation model (`Helsinki-NLP/opus-mt-ja-en`) downloads automatically from HuggingFace (~300MB).

If you have Sugoi Translator CT2 models, drop them in:

```
core/models/sugoi/
  ct2_models/    model.bin, source_vocabulary.txt, target_vocabulary.txt
  spmModels/     spm.ja.nopretok.model, spm.en.nopretok.model
```

The text detection model (`ogkalu/comic-text-and-bubble-detector`) also downloads automatically on first use.

### Run

```bash
cd app
pnpm tauri dev
```

## Translation backends

| Backend | Type | Setup |
|---------|------|-------|
| Sugoi/MarianMT | Local | Auto-downloads on first use |
| CTranslate2 | Local | Drop CT2 model files in `core/models/sugoi/` |
| DeepL | Cloud | Add API key in Settings |
| Google | Cloud | Add API key in Settings |

The app tries local models first, then falls back to cloud APIs if you've configured them.

## Tech stack

- **Desktop shell**: Tauri 2 + React + TypeScript + Tailwind
- **ML pipeline**: Python with manga-ocr, transformers, OpenCV, CTranslate2
- **IPC**: Newline-delimited JSON over stdin/stdout between Tauri and the Python sidecar

## License

MIT
