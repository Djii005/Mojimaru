from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from mojimaru import get_base_dir
from mojimaru.protocol import SourceLang, TargetLang

log = logging.getLogger(__name__)

_config: dict[str, str] = {}


def configure(
    provider: str | None = None,
    api_key: str | None = None,
    model_path: str | None = None,
) -> None:
    if provider is not None:
        _config["provider"] = provider
    if api_key is not None:
        _config["api_key"] = api_key
    if model_path is not None:
        _config["model_path"] = model_path
        global _marian_pipeline, _ct2_translator, _ct2_src_sp, _ct2_tgt_sp
        _marian_pipeline = None
        _ct2_translator = None
        _ct2_src_sp = None
        _ct2_tgt_sp = None


def _get_provider() -> str:
    return _config.get("provider") or os.environ.get("MOJIMARU_TRANSLATE_PROVIDER", "") or "auto"


def _get_api_key(provider: str) -> str:
    if _config.get("api_key"):
        return _config["api_key"]
    if provider == "deepl":
        return os.environ.get("MOJIMARU_DEEPL_KEY", "")
    if provider == "google":
        return os.environ.get("MOJIMARU_GOOGLE_KEY", "")
    return ""


def _get_model_path() -> str:
    return _config.get("model_path") or os.environ.get("MOJIMARU_TRANSLATE_MODEL", "")


_HF_MODEL_MAP: dict[tuple[str, str], str] = {
    ("ja", "en"): "Helsinki-NLP/opus-mt-ja-en",
    ("ja", "zh"): "Helsinki-NLP/opus-mt-ja-zh",
    ("ja", "fr"): "Helsinki-NLP/opus-mt-ja-fr",
    ("ja", "es"): "Helsinki-NLP/opus-mt-ja-es",
    ("ja", "de"): "Helsinki-NLP/opus-mt-ja-de",
    ("ja", "pt"): "Helsinki-NLP/opus-mt-ja-pt",
    ("ja", "ru"): "Helsinki-NLP/opus-mt-ja-ru",
    ("ja", "vi"): "Helsinki-NLP/opus-mt-ja-vi",
    ("zh", "en"): "Helsinki-NLP/opus-mt-zh-en",
    ("ko", "en"): "Helsinki-NLP/opus-mt-ko-en",
}

_PROJECT_MODELS = get_base_dir() / "models"

_SUGOI_SEARCH_PATHS: list[Path] = [
    _PROJECT_MODELS / "sugoi",
    Path.home() / ".mojimaru" / "models" / "sugoi",
    Path.home() / ".mojimaru" / "models" / "sugoi-translator",
    Path.home() / ".mojimaru" / "models" / "ja-en",
    Path("C:/Sugoi-Translator/backendtranslation/Sugoi-Translator-Toolkit/Code/backendtranslation"),
    Path.home() / "Sugoi-Translator",
]

_marian_pipeline: Any = None
_marian_model_id: str = ""


def _resolve_hf_model(source: SourceLang, target: TargetLang) -> str:
    custom = _get_model_path()
    if custom:
        return custom

    for path in _SUGOI_SEARCH_PATHS:
        if path.exists() and (path / "config.json").exists():
            log.info("Found local Sugoi model at %s", path)
            return str(path)

    src = source if source != "auto" else "ja"
    key = (src, target)
    return _HF_MODEL_MAP.get(key, "Helsinki-NLP/opus-mt-ja-en")


def _get_marian_pipeline(source: SourceLang, target: TargetLang) -> Any:

    global _marian_pipeline, _marian_model_id

    model_id = _resolve_hf_model(source, target)

    if _marian_pipeline is not None and _marian_model_id == model_id:
        return _marian_pipeline

    try:
        from transformers import MarianMTModel, MarianTokenizer

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
    pipeline = _get_marian_pipeline(source, target)
    if pipeline is None:
        return None

    try:
        import torch

        tokenizer, model = pipeline

        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if not lines:
            return ""

        translated_lines: list[str] = []
        for line in lines:
            inputs = tokenizer(
                line, return_tensors="pt", padding=True, truncation=True, max_length=512
            )
            with torch.no_grad():
                outputs = model.generate(**inputs, max_length=512, num_beams=4)
            result = tokenizer.decode(outputs[0], skip_special_tokens=True)
            translated_lines.append(result)

        return "\n".join(translated_lines)
    except Exception:
        log.warning("MarianMT inference failed", exc_info=True)
        return None


_ct2_translator: Any = None
_ct2_src_sp: Any = None
_ct2_tgt_sp: Any = None


def _find_ct2_layout(root: Path) -> tuple[Path, Path] | None:
    if (root / "model.bin").exists():
        if any(root.glob("spm.*.model")) or any(root.glob("*.spm")):
            return (root, root)
        sibling = root.parent / "spmModels"
        if sibling.is_dir():
            return (root, sibling)
        return (root, root)

    ct2_sub = root / "ct2_models"
    spm_sub = root / "spmModels"
    if (ct2_sub / "model.bin").exists():
        return (ct2_sub, spm_sub if spm_sub.is_dir() else ct2_sub)

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

    for pattern in ("*.model", "*.spm"):
        files = sorted(spm_dir.glob(pattern))
        if files:
            return str(files[0])

    return None


def _resolve_ct2_paths() -> tuple[Path, Path] | None:
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


def _get_ct2_translator() -> Any:
    global _ct2_translator, _ct2_src_sp, _ct2_tgt_sp
    if _ct2_translator is not None and _ct2_src_sp is not None:
        return (_ct2_translator, _ct2_src_sp, _ct2_tgt_sp or _ct2_src_sp)

    paths = _resolve_ct2_paths()
    if paths is None:
        return None

    ct2_dir, spm_dir = paths

    try:
        import ctranslate2
        import sentencepiece as spm

        log.info("Loading CTranslate2 model from %s", ct2_dir)
        translator = ctranslate2.Translator(str(ct2_dir), device="cpu")

        src_path = _find_spm_file(spm_dir, "ja")
        if not src_path:
            log.warning("No source SPM tokenizer found in %s", spm_dir)
            return None

        src_sp = spm.SentencePieceProcessor()
        src_sp.Load(src_path)
        log.info("Source SPM: %s", src_path)

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
            tokens = src_sp.Encode(line, out_type=str)
            result = translator.translate_batch([tokens], beam_size=4)
            output_tokens = result[0].hypotheses[0]
            translated = tgt_sp.Decode(output_tokens)
            translated_lines.append(translated)

        return "\n".join(translated_lines)
    except Exception:
        log.warning("CTranslate2 inference failed", exc_info=True)
        return None


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


def _translate_deepl(text: str, source: SourceLang, target: TargetLang) -> str | None:
    key = _get_api_key("deepl")
    if not key:
        return None

    try:
        import requests

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
            return str(translations[0].get("text", ""))

        return None
    except Exception:
        log.warning("DeepL translation failed", exc_info=True)
        return None


_GOOGLE_LANG_MAP: dict[str, str] = {
    "ja": "ja",
    "zh": "zh-CN",
    "ko": "ko",
    "auto": "",
}


def _translate_google(text: str, source: SourceLang, target: TargetLang) -> str | None:
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
            return str(translations[0].get("translatedText", ""))
        return None
    except Exception:
        log.warning("Google translation failed", exc_info=True)
        return None


def _translate_stub(text: str, source: SourceLang, target: TargetLang) -> str:
    return f"[{source}→{target}] {text}"


def translate(text: str, source: SourceLang, target: TargetLang) -> str:
    if not text:
        return ""

    provider = _get_provider()

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

    for try_fn in (_translate_ct2, _translate_local, _translate_deepl, _translate_google):
        result = try_fn(text, source, target)
        if result is not None:
            return result

    return _translate_stub(text, source, target)
