"""Translation backend.

Backends (tried in order):
  1. **Local (Sugoi / MarianMT)** — offline, no API key needed. Uses
     Hugging Face ``transformers`` with a MarianMT model. Set provider to
     ``sugoi`` or ``local``.  Supports custom model paths via
     ``MOJIMARU_TRANSLATE_MODEL`` or the ``translate_model_path`` config key.
  2. **CTranslate2** — faster inference for Sugoi's native CT2 format.
     Set provider to ``ct2``. Requires ``pip install ctranslate2 sentencepiece``.
  3. **DeepL API** — best cloud quality for JP/ZH/KO → EN. Requires
     ``MOJIMARU_DEEPL_KEY``.
  4. **Google Cloud Translation** — broader language support. Requires
     ``MOJIMARU_GOOGLE_KEY``.
  5. **Stub** — returns the original text with a ``[source→target]`` marker.

The active provider can be set via ``MOJIMARU_TRANSLATE_PROVIDER``
(``sugoi``, ``local``, ``ct2``, ``deepl``, ``google``, ``stub``) or
configured at runtime via the sidecar ``configure`` message.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from mojimaru import get_base_dir
from mojimaru.protocol import SourceLang, TargetLang

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Runtime configuration (can be changed via sidecar `configure` message)
# ---------------------------------------------------------------------------

_config: dict[str, str] = {}


def configure(
    provider: str | None = None,
    api_key: str | None = None,
    model_path: str | None = None,
) -> None:
    """Set the translation provider, API key, and/or model path at runtime."""
    if provider is not None:
        _config["provider"] = provider
    if api_key is not None:
        _config["api_key"] = api_key
    if model_path is not None:
        _config["model_path"] = model_path
        # Reset cached model so it reloads on next call
        global _marian_pipeline, _ct2_translator, _ct2_src_sp, _ct2_tgt_sp
        _marian_pipeline = None
        _ct2_translator = None
        _ct2_src_sp = None
        _ct2_tgt_sp = None


def _get_provider() -> str:
    """Resolve which provider to use."""
    return _config.get("provider") or os.environ.get("MOJIMARU_TRANSLATE_PROVIDER", "") or "auto"


def _get_api_key(provider: str) -> str:
    """Resolve the API key for the given provider."""
    if _config.get("api_key"):
        return _config["api_key"]
    if provider == "deepl":
        return os.environ.get("MOJIMARU_DEEPL_KEY", "")
    if provider == "google":
        return os.environ.get("MOJIMARU_GOOGLE_KEY", "")
    return ""


def _get_model_path() -> str:
    """Resolve the local model path."""
    return _config.get("model_path") or os.environ.get("MOJIMARU_TRANSLATE_MODEL", "")


# ---------------------------------------------------------------------------
# Hugging Face model name mapping (language pair → default HF model)
# ---------------------------------------------------------------------------

_HF_MODEL_MAP: dict[tuple[str, str], str] = {
    # Japanese → various
    ("ja", "en"): "Helsinki-NLP/opus-mt-ja-en",
    ("ja", "zh"): "Helsinki-NLP/opus-mt-ja-zh",
    ("ja", "fr"): "Helsinki-NLP/opus-mt-ja-fr",
    ("ja", "es"): "Helsinki-NLP/opus-mt-ja-es",
    ("ja", "de"): "Helsinki-NLP/opus-mt-ja-de",
    ("ja", "pt"): "Helsinki-NLP/opus-mt-ja-pt",
    ("ja", "ru"): "Helsinki-NLP/opus-mt-ja-ru",
    ("ja", "vi"): "Helsinki-NLP/opus-mt-ja-vi",
    # Chinese → English
    ("zh", "en"): "Helsinki-NLP/opus-mt-zh-en",
    # Korean → English
    ("ko", "en"): "Helsinki-NLP/opus-mt-ko-en",
}

# Well-known Sugoi model directories (checked in order)
# The project-local path is resolved relative to this source file:
#   core/src/mojimaru/translate.py → core/models/sugoi
_PROJECT_MODELS = get_base_dir() / "models"

_SUGOI_SEARCH_PATHS: list[Path] = [
    # 1. Project-local (core/models/sugoi/)
    _PROJECT_MODELS / "sugoi",
    # 2. User home
    Path.home() / ".mojimaru" / "models" / "sugoi",
    Path.home() / ".mojimaru" / "models" / "sugoi-translator",
    Path.home() / ".mojimaru" / "models" / "ja-en",
    # 3. Common Sugoi Toolkit install paths
    Path("C:/Sugoi-Translator/backendtranslation/Sugoi-Translator-Toolkit/Code/backendtranslation"),
    Path.home() / "Sugoi-Translator",
]


# ---------------------------------------------------------------------------
# Local MarianMT backend (via Hugging Face transformers)
# ---------------------------------------------------------------------------

_marian_pipeline: object | None = None
_marian_model_id: str = ""


def _resolve_hf_model(source: SourceLang, target: TargetLang) -> str:
    """Pick the best HF model ID for this language pair."""
    # Custom model path takes priority
    custom = _get_model_path()
    if custom:
        return custom

    # Check well-known Sugoi directories
    for path in _SUGOI_SEARCH_PATHS:
        if path.exists() and (path / "config.json").exists():
            log.info("Found local Sugoi model at %s", path)
            return str(path)

    # Fall back to HF hub model
    src = source if source != "auto" else "ja"
    key = (src, target)
    return _HF_MODEL_MAP.get(key, "Helsinki-NLP/opus-mt-ja-en")


def _get_marian_pipeline(source: SourceLang, target: TargetLang) -> object | None:
    """Load (or reuse) a MarianMT translation pipeline."""
    global _marian_pipeline, _marian_model_id

    model_id = _resolve_hf_model(source, target)

    # Reuse if same model
    if _marian_pipeline is not None and _marian_model_id == model_id:
        return _marian_pipeline

    try:
        from transformers import MarianMTModel, MarianTokenizer  # type: ignore[import-untyped]

        log.info("Loading MarianMT model: %s (may download on first use)…", model_id)
        tokenizer = MarianTokenizer.from_pretrained(model_id)
        model = MarianMTModel.from_pretrained(model_id)
        _marian_pipeline = (tokenizer, model)
        _marian_model_id = model_id
        log.info("MarianMT model loaded: %s", model_id)
        return _marian_pipeline
    except Exception:
        log.warning("Failed to load MarianMT model: %s", model_id, exc_info=True)
        return None


def _translate_local(text: str, source: SourceLang, target: TargetLang) -> str | None:
    """Translate using a local MarianMT model (Sugoi-compatible)."""
    pipeline = _get_marian_pipeline(source, target)
    if pipeline is None:
        return None

    try:
        import torch

        tokenizer, model = pipeline  # type: ignore[misc]

        # MarianMT works best line-by-line for manga text
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return ""

        translated_lines: list[str] = []
        for line in lines:
            inputs = tokenizer(
                line, return_tensors="pt", padding=True, truncation=True, max_length=512
            )  # type: ignore[operator]
            with torch.no_grad():
                outputs = model.generate(**inputs, max_length=512, num_beams=4)  # type: ignore[operator]
            result = tokenizer.decode(outputs[0], skip_special_tokens=True)  # type: ignore[operator]
            translated_lines.append(result)

        return "\n".join(translated_lines)
    except Exception:
        log.warning("MarianMT inference failed", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# CTranslate2 backend (Sugoi's native format — faster inference)
#
# Sugoi Translator typically ships with:
#   ct2_models/          model.bin, source_vocabulary, target_vocabulary
#   spmModels/           spm.ja.nopretok.model, spm.en.nopretok.model, …
#
# The user points to the *parent* directory that contains both, or directly
# to ct2_models/. We search upward to find the sibling spmModels/.
# ---------------------------------------------------------------------------

_ct2_translator: object | None = None
_ct2_src_sp: object | None = None
_ct2_tgt_sp: object | None = None


def _find_ct2_layout(root: Path) -> tuple[Path, Path] | None:
    """Locate (ct2_dir, spm_dir) starting from ``root``.

    Handles these common layouts:
      root/model.bin + root/spm.*.model          → (root, root)
      root/ct2_models/model.bin + root/spmModels/ → (root/ct2_models, root/spmModels)
      root/model.bin + ../spmModels/              → (root, root/../spmModels)
    """
    # Case 1: root itself IS the ct2 dir (model.bin right here)
    if (root / "model.bin").exists():
        # SPM in same dir?
        if any(root.glob("spm.*.model")) or any(root.glob("*.spm")):
            return (root, root)
        # SPM in sibling spmModels/?
        sibling = root.parent / "spmModels"
        if sibling.is_dir():
            return (root, sibling)
        return (root, root)  # will try to find spm files later

    # Case 2: root has ct2_models/ and spmModels/ subdirs
    ct2_sub = root / "ct2_models"
    spm_sub = root / "spmModels"
    if (ct2_sub / "model.bin").exists():
        return (ct2_sub, spm_sub if spm_sub.is_dir() else ct2_sub)

    # Case 3: root has ct2Model/ variant naming
    for ct2_name in ("ct2_models", "ct2Model", "ct2model", "ct2"):
        ct2_sub = root / ct2_name
        if (ct2_sub / "model.bin").exists():
            for spm_name in ("spmModels", "spm", "spmModel"):
                spm_sub = root / spm_name
                if spm_sub.is_dir():
                    return (ct2_sub, spm_sub)
            return (ct2_sub, ct2_sub)

    return None


def _find_spm_file(spm_dir: Path, lang: str) -> str | None:
    """Find a SentencePiece model file for the given language."""
    # Sugoi naming: spm.ja.nopretok.model, spm.en.nopretok.model
    candidates = [
        f"spm.{lang}.nopretok.model",
        f"spm.{lang}.model",
        f"{lang}.model",
        "source.spm" if lang == "ja" else "target.spm",
    ]
    for name in candidates:
        p = spm_dir / name
        if p.exists():
            return str(p)

    # Fallback: any .model or .spm file
    for pattern in ("*.model", "*.spm"):
        files = sorted(spm_dir.glob(pattern))
        if files:
            return str(files[0])

    return None


def _resolve_ct2_paths() -> tuple[Path, Path] | None:
    """Find ct2 + spm directories from config or well-known paths."""
    custom = _get_model_path()
    if custom:
        result = _find_ct2_layout(Path(custom))
        if result:
            return result

    for path in _SUGOI_SEARCH_PATHS:
        if path.exists():
            result = _find_ct2_layout(path)
            if result:
                return result

    return None


def _get_ct2_translator() -> tuple[object, object, object] | None:
    """Load CTranslate2 translator + source/target SentencePiece tokenizers."""
    global _ct2_translator, _ct2_src_sp, _ct2_tgt_sp
    if _ct2_translator is not None and _ct2_src_sp is not None:
        return (_ct2_translator, _ct2_src_sp, _ct2_tgt_sp or _ct2_src_sp)

    paths = _resolve_ct2_paths()
    if paths is None:
        return None

    ct2_dir, spm_dir = paths

    try:
        import ctranslate2  # type: ignore[import-untyped]
        import sentencepiece as spm  # type: ignore[import-untyped]

        log.info("Loading CTranslate2 model from %s", ct2_dir)
        translator = ctranslate2.Translator(str(ct2_dir), device="cpu")

        # Source tokenizer (Japanese)
        src_path = _find_spm_file(spm_dir, "ja")
        if not src_path:
            log.warning("No source SPM tokenizer found in %s", spm_dir)
            return None

        src_sp = spm.SentencePieceProcessor()
        src_sp.Load(src_path)
        log.info("Source SPM: %s", src_path)

        # Target tokenizer (English) — may be same file for some models
        tgt_path = _find_spm_file(spm_dir, "en")
        tgt_sp = None
        if tgt_path and tgt_path != src_path:
            tgt_sp = spm.SentencePieceProcessor()
            tgt_sp.Load(tgt_path)
            log.info("Target SPM: %s", tgt_path)

        _ct2_translator = translator
        _ct2_src_sp = src_sp
        _ct2_tgt_sp = tgt_sp
        log.info("CTranslate2 model loaded (ct2=%s, spm=%s)", ct2_dir, spm_dir)
        return (translator, src_sp, tgt_sp or src_sp)
    except ImportError:
        log.debug("ctranslate2 or sentencepiece not installed")
        return None
    except Exception:
        log.warning("CTranslate2 load failed", exc_info=True)
        return None


def _translate_ct2(text: str, source: SourceLang, target: TargetLang) -> str | None:
    """Translate using CTranslate2 (Sugoi native format)."""
    triple = _get_ct2_translator()
    if triple is None:
        return None

    try:
        translator, src_sp, tgt_sp = triple
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return ""

        translated_lines: list[str] = []
        for line in lines:
            # Tokenize with source SPM
            tokens = src_sp.Encode(line, out_type=str)  # type: ignore[union-attr]
            # Translate
            result = translator.translate_batch([tokens], beam_size=4)  # type: ignore[union-attr]
            output_tokens = result[0].hypotheses[0]
            # Decode with target SPM
            translated = tgt_sp.Decode(output_tokens)  # type: ignore[union-attr]
            translated_lines.append(translated)

        return "\n".join(translated_lines)
    except Exception:
        log.warning("CTranslate2 inference failed", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# DeepL lang-code mapping
# ---------------------------------------------------------------------------

_DEEPL_SOURCE_MAP: dict[str, str] = {
    "ja": "JA",
    "zh": "ZH",
    "ko": "KO",
}

_DEEPL_TARGET_MAP: dict[str, str] = {
    "en": "EN-US",
    "id": "ID",
    "es": "ES",
    "fr": "FR",
    "de": "DE",
    "pt": "PT-BR",
    "ru": "RU",
    "vi": "VI",
    "th": "TH",
}


# ---------------------------------------------------------------------------
# DeepL backend
# ---------------------------------------------------------------------------


def _translate_deepl(text: str, source: SourceLang, target: TargetLang) -> str | None:
    """Translate via the DeepL API. Returns None on failure."""
    key = _get_api_key("deepl")
    if not key:
        return None

    try:
        import requests

        # DeepL free tier uses api-free.deepl.com, pro uses api.deepl.com
        base_url = "https://api-free.deepl.com" if key.endswith(":fx") else "https://api.deepl.com"

        params: dict[str, str] = {
            "text": text,
            "target_lang": _DEEPL_TARGET_MAP.get(target, target.upper()),
        }

        if source != "auto":
            params["source_lang"] = _DEEPL_SOURCE_MAP.get(source, source.upper())

        resp = requests.post(
            f"{base_url}/v2/translate",
            headers={"Authorization": f"DeepL-Auth-Key {key}"},
            data=params,
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        translations = result.get("translations", [])
        if translations:
            return translations[0].get("text", "")
        return None
    except Exception:
        log.warning("DeepL translation failed", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Google Cloud Translation backend
# ---------------------------------------------------------------------------

_GOOGLE_LANG_MAP: dict[str, str] = {
    "ja": "ja",
    "zh": "zh-CN",
    "ko": "ko",
    "auto": "",
}


def _translate_google(text: str, source: SourceLang, target: TargetLang) -> str | None:
    """Translate via the Google Cloud Translation API v2."""
    key = _get_api_key("google")
    if not key:
        return None

    try:
        import requests

        params: dict[str, str] = {
            "q": text,
            "target": target,
            "key": key,
            "format": "text",
        }
        if source != "auto":
            params["source"] = _GOOGLE_LANG_MAP.get(source, source)

        resp = requests.post(
            "https://translation.googleapis.com/language/translate/v2",
            data=params,
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        translations = result.get("data", {}).get("translations", [])
        if translations:
            return translations[0].get("translatedText", "")
        return None
    except Exception:
        log.warning("Google translation failed", exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Stub backend
# ---------------------------------------------------------------------------


def _translate_stub(text: str, source: SourceLang, target: TargetLang) -> str:
    """Return the original text with a marker. Always works."""
    return f"[{source}→{target}] {text}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def translate(text: str, source: SourceLang, target: TargetLang) -> str:
    """Translate ``text`` from ``source`` to ``target``.

    Tries the configured provider, then auto-detects available providers,
    then falls back to the stub.
    """
    if not text:
        return ""

    provider = _get_provider()

    # Explicit provider selection
    if provider in ("sugoi", "local"):
        result = _translate_local(text, source, target)
        if result is not None:
            return result
        log.warning("Local/Sugoi selected but failed — falling back to stub")
        return _translate_stub(text, source, target)

    if provider == "ct2":
        result = _translate_ct2(text, source, target)
        if result is not None:
            return result
        log.warning("CTranslate2 selected but failed — falling back to stub")
        return _translate_stub(text, source, target)

    if provider == "deepl":
        result = _translate_deepl(text, source, target)
        if result is not None:
            return result
        log.warning("DeepL selected but failed — falling back to stub")
        return _translate_stub(text, source, target)

    if provider == "google":
        result = _translate_google(text, source, target)
        if result is not None:
            return result
        log.warning("Google selected but failed — falling back to stub")
        return _translate_stub(text, source, target)

    if provider == "stub":
        return _translate_stub(text, source, target)

    # Auto: try providers in priority order (local first, then cloud)
    for try_fn in (_translate_ct2, _translate_local, _translate_deepl, _translate_google):
        result = try_fn(text, source, target)
        if result is not None:
            return result

    return _translate_stub(text, source, target)
