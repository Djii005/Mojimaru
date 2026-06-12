# mojimaru (core)

The ML pipeline behind Mojimaru. Runs as:

- a **CLI** for direct/scripted use (`mojimaru translate ...`),
- a **JSON sidecar** spawned by the Tauri desktop shell (`mojimaru serve`).

The pipeline stages are:

1. **detect** — find speech bubbles and text regions in a manga page.
2. **ocr** — read CJK text (Japanese vertical/horizontal, Chinese, Korean).
3. **translate** — translate to the user's target language.
4. **inpaint** — clean the original text out of the bubble.
5. **typeset** — render the translated text back into the cleaned bubble.

Each stage is pluggable. The base install runs an end-to-end stub pipeline so the wiring is testable without GPU. Install the `[ml]` extra (or one of the per-stage extras) to plug in real models:

```bash
pip install -e ".[dev]"           # base + dev
pip install -e ".[ml]"            # full ML stack (large)
pip install -e ".[manga-ocr]"     # Japanese OCR only
```

## CLI

```bash
mojimaru translate --in ./chapter01 --out ./chapter01_en --source ja --target en
mojimaru translate --image page01.png --out ./out --source ja --target en
mojimaru serve                    # sidecar mode (read JSON from stdin)
mojimaru info                     # diagnostics
```

## Sidecar protocol

Newline-delimited JSON over stdin/stdout. See `mojimaru.protocol` for the message types.
