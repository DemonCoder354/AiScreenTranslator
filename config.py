"""Loading and saving of ``config.json`` placed next to the program."""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from i18n import DEFAULT_UI_LANGUAGE, UI_LANGUAGES
from languages import is_supported

log = logging.getLogger(__name__)


def app_dir() -> Path:
    """Return the directory the application runs from (works for scripts and frozen builds)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    """Return the writable directory for config.json and logs.

    The built exe may sit in a read-only folder (Program Files, a zip preview), so
    it keeps its data in %APPDATA%\\ScreenTranslator; a script keeps it next to itself.
    """
    if getattr(sys, "frozen", False):
        path = Path(os.environ.get("APPDATA") or Path.home()) / "ScreenTranslator"
        path.mkdir(parents=True, exist_ok=True)
        return path
    return app_dir()


CONFIG_PATH: Path = data_dir() / "config.json"
DEFAULT_TESSERACT = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")

PROVIDER_LOCAL = "local"
PROVIDER_GEMINI = "gemini"
PROVIDERS = (PROVIDER_LOCAL, PROVIDER_GEMINI)
SPEECH_ENGINES = ("auto", "windows", "gemini")


@dataclass
class AppConfig:
    """User-editable application settings.

    Attributes:
        hotkey: Global hotkey for translating a screen area, e.g. ``"Ctrl+Alt+T"``.
        manual_hotkey: Global hotkey that opens the window for typed or pasted text.
        target_language: ISO 639-1 code of the default target language.
        source_language: Default source language code; empty means auto-detect.
        tesseract_path: Full path to ``tesseract.exe``; empty means the copy bundled
            with the program, else the standard installation.
        tessdata_dir: Directory with ``*.traineddata``; empty means Tesseract's default.
        provider: Translation backend: "local" (LM Studio) or "gemini" (Google Gemini API).
        lmstudio_base_url: Base URL of the LM Studio OpenAI-compatible server.
        model_name: Model id; empty means "first model loaded in LM Studio".
        temperature: Sampling temperature for translation.
        ocr_scale: Upscale factor applied to the screenshot before OCR.
        request_timeout: Timeout of a translation request in seconds.
        disable_reasoning: Ask reasoning models not to "think" before answering.
        gemini_text_models: Gemini API models for translation, in order of preference:
            when one is out of quota or overloaded, the next answers.
        gemini_dictionary_models: Gemini API models for the dictionary card, same rules.
        gemini_vision_models: Gemini API models that read screenshots, same rules.
        gemini_api_key_env: Name of the environment variable holding the Gemini key.
            The key itself is never stored in this file.
        cloud_ocr: With the Gemini provider, let Gemini read screenshots instead of
            Tesseract (much better on photos; Tesseract remains the fallback).
        speech_engine: Pronunciation in the dictionary: "auto" (Gemini Live in cloud
            mode, else an installed Windows voice), "windows" or "gemini".
        gemini_speech_model: Gemini Live model that pronounces words.
        gemini_speech_voice: Gemini prebuilt voice name, e.g. "Kore".
        speech_volume: Pronunciation volume from 0 to 1 (settings, dictionary card).
        ui_language: Interface language: "en" or "ru".
    """

    hotkey: str = "Ctrl+Alt+T"
    manual_hotkey: str = "Ctrl+Alt+R"
    target_language: str = "ru"
    source_language: str = ""
    tesseract_path: str = ""
    tessdata_dir: str = "tessdata"
    provider: str = PROVIDER_GEMINI  # works for anyone with a free key; LM Studio is optional
    lmstudio_base_url: str = "http://localhost:1234/v1"
    model_name: str = ""
    temperature: float = 0.2
    ocr_scale: float = 2.0
    request_timeout: float = 60.0
    disable_reasoning: bool = True
    # Gemma 4 26B has twice the free daily quota of Flash-Lite and translates as well;
    # Flash-Lite reads images ~4x faster, so it goes first there.
    gemini_text_models: tuple[str, ...] = ("gemma-4-26b-a4b-it", "gemini-3.5-flash-lite",
                                           "gemini-3.1-flash-lite")
    gemini_vision_models: tuple[str, ...] = ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
                                             "gemma-4-26b-a4b-it")
    # Gemini 3.1 Flash-Lite: as good as 3.5, a bit slower, its own quota. It backs up
    # 3.5 for the dictionary and images (better IPA, faster OCR than Gemma) and closes
    # the translation list.
    # Gemma garbles IPA (e.g. "spis" -> /spit/); Flash-Lite gets it right and answers ~3x faster.
    gemini_dictionary_models: tuple[str, ...] = ("gemini-3.5-flash-lite", "gemini-3.1-flash-lite",
                                                 "gemma-4-26b-a4b-it")
    gemini_api_key_env: str = "GEMINI_API_KEY"
    cloud_ocr: bool = True
    speech_engine: str = "auto"
    gemini_speech_model: str = "gemini-3.8-live"
    gemini_speech_voice: str = "Kore"
    speech_volume: float = 1.0
    ui_language: str = DEFAULT_UI_LANGUAGE

    def resolved_tesseract_path(self) -> Path:
        """Return the Tesseract executable to use."""
        if self.tesseract_path:
            return Path(self.tesseract_path)
        bundled = app_dir() / "tesseract" / "tesseract.exe"
        return bundled if bundled.is_file() else DEFAULT_TESSERACT

    def resolved_tessdata_dir(self) -> Path | None:
        """Return the absolute tessdata directory, or None to use Tesseract's default."""
        if not self.tessdata_dir:
            return None
        path = Path(self.tessdata_dir)
        return path if path.is_absolute() else app_dir() / path

    def validate(self) -> None:
        """Replace invalid values with defaults, logging each correction."""
        defaults = AppConfig()
        if not is_supported(self.target_language):
            log.warning("Unsupported target_language %r, using %r",
                        self.target_language, defaults.target_language)
            self.target_language = defaults.target_language
        self.target_language = self.target_language.lower()
        self.source_language = self.source_language.lower()
        if self.source_language and not is_supported(self.source_language):
            log.warning("Unsupported source_language %r, using auto-detect",
                        self.source_language)
            self.source_language = ""
        self.provider = self.provider.strip().lower()
        if self.provider not in PROVIDERS:
            log.warning("Unknown provider %r, using %r", self.provider, defaults.provider)
            self.provider = defaults.provider
        self.gemini_text_models = _model_list(self.gemini_text_models,
                                              defaults.gemini_text_models)
        self.gemini_vision_models = _model_list(self.gemini_vision_models,
                                                defaults.gemini_vision_models)
        self.gemini_dictionary_models = _model_list(self.gemini_dictionary_models,
                                                    defaults.gemini_dictionary_models)
        self.gemini_api_key_env = self.gemini_api_key_env.strip() or defaults.gemini_api_key_env
        self.speech_engine = self.speech_engine.strip().lower()
        if self.speech_engine not in SPEECH_ENGINES:
            log.warning("Unknown speech_engine %r, using %r", self.speech_engine,
                        defaults.speech_engine)
            self.speech_engine = defaults.speech_engine
        self.gemini_speech_model = self.gemini_speech_model.strip() or defaults.gemini_speech_model
        self.gemini_speech_voice = self.gemini_speech_voice.strip() or defaults.gemini_speech_voice
        if not 0.0 <= self.temperature <= 2.0:
            self.temperature = defaults.temperature
        if not 1.0 <= self.ocr_scale <= 4.0:
            self.ocr_scale = defaults.ocr_scale
        self.speech_volume = min(max(self.speech_volume, 0.0), 1.0)
        self.ui_language = self.ui_language.strip().lower()
        if self.ui_language not in UI_LANGUAGES:
            self.ui_language = defaults.ui_language
        if self.request_timeout <= 0:
            self.request_timeout = defaults.request_timeout


def _model_list(value: object, default: tuple[str, ...]) -> tuple[str, ...]:
    """Clean a list of model ids from the config; the default if it is not usable."""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple)):
        return default
    models = tuple(dict.fromkeys(str(v).strip() for v in value if str(v).strip()))
    return models or default


def load_config(path: Path = CONFIG_PATH) -> AppConfig:
    """Load config from ``path``, creating it with defaults if missing or unreadable.

    Unknown keys are ignored, missing keys get default values, and the file is
    rewritten so that it always contains every supported key.
    """
    config = AppConfig()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            known = {f.name for f in fields(AppConfig)}
            for key, value in data.items():
                if key not in known:
                    continue
                default = getattr(config, key)
                if isinstance(default, tuple):  # lists of model ids: cleaned in validate()
                    setattr(config, key, value)
                    continue
                try:
                    setattr(config, key, type(default)(value))
                except (TypeError, ValueError):
                    log.warning("Invalid value for %s: %r, using default", key, value)
        except (OSError, ValueError, AttributeError) as exc:
            log.error("Cannot read %s (%s), using defaults", path, exc)
            config = AppConfig()
    config.validate()
    save_config(config, path)
    return config


def save_config(config: AppConfig, path: Path = CONFIG_PATH) -> None:
    """Write ``config`` to ``path`` as pretty-printed UTF-8 JSON."""
    try:
        path.write_text(json.dumps(asdict(config), ensure_ascii=False, indent=2),
                        encoding="utf-8")
    except OSError as exc:
        log.error("Cannot write %s: %s", path, exc)
