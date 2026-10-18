"""Builds the :class:`Translator` for the provider selected in the config."""

from __future__ import annotations

import logging
import os
import sys

import openai

from config import PROVIDER_GEMINI, AppConfig
from i18n import tr
from translator import LOCAL_SERVICE, TranslationError, Translator

log = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
GEMINI_SERVICE = "Gemini API"


def read_api_key(variable: str) -> str:
    """Return the API key from environment variable ``variable`` ("" if not set).

    A variable created with ``setx`` after the program started is not in this
    process's environment yet, so the user's registry copy is checked as well:
    the key then works without restarting the program.
    """
    value = os.environ.get(variable, "").strip()
    if value or sys.platform != "win32" or not variable:
        return value
    import winreg  # Windows only

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
            value, _ = winreg.QueryValueEx(key, variable)
    except OSError:
        return ""
    return str(value).strip()


# Model families that cannot answer a text chat request (embeddings, image/video/music
# generation, speech, the voice-only Live models).
_NOT_CHAT = ("embedding", "imagen", "veo", "lyria", "tts", "live", "aqa", "-image", "transcribe",
             "native-audio", "computer-use", "robotics")


def list_gemini_models(api_key: str, timeout: float = 15.0) -> list[str]:
    """Return the ids of the chat models this key can use in Google AI Studio, sorted.

    Raises:
        TranslationError: If the list cannot be loaded (no connection, invalid key).
    """
    client = openai.OpenAI(base_url=GEMINI_BASE_URL, api_key=api_key, max_retries=0,
                           timeout=timeout)
    try:
        ids = [m.id.removeprefix("models/") for m in client.models.list()]
    except openai.APIError as exc:
        raise TranslationError(str(getattr(exc, "message", "") or exc)) from exc
    finally:
        client.close()
    chat = {i for i in ids if i.startswith(("gemini", "gemma"))
            and not any(part in i for part in _NOT_CHAT)}
    return sorted(chat)


def make_translator(config: AppConfig) -> Translator:
    """Create the translator for ``config.provider``.

    Raises:
        TranslationError: If the cloud provider is selected but its key is missing.
    """
    if config.provider == PROVIDER_GEMINI:
        key = read_api_key(config.gemini_api_key_env)
        if not key:
            raise TranslationError(tr("err.no_key", variable=config.gemini_api_key_env))
        log.info("Using %s: text %s, dictionary %s, images %s", GEMINI_SERVICE,
                 ", ".join(config.gemini_text_models), ", ".join(config.gemini_dictionary_models),
                 ", ".join(config.gemini_vision_models))
        # Reasoning cannot be switched off for Gemini 3 / Gemma 4, only lowered.
        return Translator(GEMINI_BASE_URL, config.gemini_text_models[0], config.temperature,
                          config.request_timeout, config.disable_reasoning,
                          api_key=key, service=GEMINI_SERVICE, reasoning_effort="minimal",
                          text_models=config.gemini_text_models,
                          vision_models=config.gemini_vision_models,
                          dictionary_models=config.gemini_dictionary_models)
    log.info("Using %s at %s", LOCAL_SERVICE, config.lmstudio_base_url)
    return Translator(config.lmstudio_base_url, config.model_name, config.temperature,
                      config.request_timeout, config.disable_reasoning)
