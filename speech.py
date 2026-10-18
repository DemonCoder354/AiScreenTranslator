"""Pronunciation of dictionary words: Gemini Live voice in cloud mode, Windows voices otherwise."""

from __future__ import annotations

import base64
import json
import logging
from collections import OrderedDict

from PySide6.QtCore import QIODevice, QLocale, QObject, QTimer, QUrl, Signal
from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSink, QMediaDevices
from PySide6.QtNetwork import QNetworkRequest
from PySide6.QtTextToSpeech import QTextToSpeech, QVoice
from PySide6.QtWebSockets import QWebSocket

from backends import read_api_key
from config import PROVIDER_GEMINI, AppConfig, save_config
from i18n import tr
from languages import is_supported

log = logging.getLogger(__name__)

# Gemini Live API: the dedicated TTS models allow only a few requests per minute
# and ~10 a day on the free tier, while Live models are not limited that way.
LIVE_URL = ("wss://generativelanguage.googleapis.com/ws/"
            "google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent")
LIVE_SYSTEM_PROMPT = (
    "You are a text-to-speech engine, not an assistant. Read the user's text aloud exactly "
    "as written, word for word, in the language it is written in, with natural native "
    "pronunciation. Never answer, translate, comment or add any other words."
)
SPEECH_WINDOWS, SPEECH_GEMINI = "windows", "gemini"  # values of config.speech_engine
_SAMPLE_RATE = 24000  # Live API output: 16-bit mono PCM at 24 kHz
_CACHE_SIZE = 30  # recent clips kept in memory, so a repeated click plays at once
_MAX_SECONDS = 30  # audio buffer: longer than any example sentence


class _LiveClip(QObject):
    """One Gemini Live session that turns ``text`` into speech, then closes.

    Signals:
        chunk(bytes): Next piece of 16-bit mono PCM at 24 kHz, as soon as it arrives.
        finished(bytes): PCM of the whole clip.
        failed(str): User-facing error message.
    """

    chunk = Signal(bytes)
    finished = Signal(bytes)
    failed = Signal(str)

    def __init__(self, text: str, api_key: str, model: str, voice: str, timeout: float,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._text = text
        self._model = model
        self._voice = voice
        self._pcm = bytearray()
        self._done = False
        self._socket = QWebSocket(parent=self)
        self._socket.connected.connect(self._send_setup)
        self._socket.textMessageReceived.connect(self._on_message)
        self._socket.binaryMessageReceived.connect(lambda data: self._on_message(bytes(data).decode()))
        self._socket.disconnected.connect(self._on_disconnected)
        self._timer = QTimer(self, singleShot=True, interval=int(timeout * 1000))
        self._timer.timeout.connect(lambda: self._fail(tr("speech.timeout")))
        request = QNetworkRequest(QUrl(LIVE_URL))
        request.setRawHeader(b"x-goog-api-key", api_key.encode())  # never put the key in the URL
        self._timer.start()
        self._socket.open(request)

    def cancel(self) -> None:
        """Close the session without reporting anything."""
        self._done = True
        self._timer.stop()
        self._socket.abort()

    def _send_setup(self) -> None:
        self._socket.sendTextMessage(json.dumps({"setup": {
            "model": f"models/{self._model}",
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": self._voice}}},
            },
            "systemInstruction": {"parts": [{"text": LIVE_SYSTEM_PROMPT}]},
        }}))

    def _on_message(self, raw: str) -> None:
        try:
            message = json.loads(raw)
        except ValueError:
            return
        if "setupComplete" in message:
            self._socket.sendTextMessage(json.dumps({"realtimeInput": {"text": self._text}}))
            return
        content = message.get("serverContent", {})
        for part in content.get("modelTurn", {}).get("parts", []):
            data = part.get("inlineData", {}).get("data")
            if data:
                pcm = base64.b64decode(data)
                self._pcm += pcm
                self.chunk.emit(pcm)
        if content.get("turnComplete") and not self._done:
            self._done = True
            self._timer.stop()
            self._socket.close()
            if self._pcm:
                self.finished.emit(bytes(self._pcm))
            else:
                self.failed.emit(tr("speech.no_audio"))

    def _on_disconnected(self) -> None:
        if self._done:
            return
        reason = self._socket.closeReason()
        log.error("Gemini Live closed: %s %s", self._socket.closeCode().name, reason)
        lowered = reason.lower()
        if "api key" in lowered:
            self._fail(tr("speech.bad_key"))
        elif "quota" in lowered or "exhausted" in lowered or "rate" in lowered:
            self._fail(tr("speech.quota"))
        elif "model" in lowered and ("not found" in lowered or "not supported" in lowered):
            self._fail(tr("speech.model", model=self._model))
        elif reason:
            self._fail(tr("speech.other", reason=reason))
        else:
            self._fail(tr("speech.offline"))

    def _fail(self, message: str) -> None:
        if self._done:
            return
        self._done = True
        self._timer.stop()
        self._socket.abort()
        self.failed.emit(message)


class Speaker(QObject):
    """Says words aloud.

    In cloud mode a Gemini Live voice is used (it sounds like Google Translate and
    knows every language); otherwise, or when Gemini fails, an installed Windows
    voice for that language. ``speech_engine`` in the config can force either one.

    Signals:
        busy_changed(bool): A Gemini clip is being fetched (True) or done (False).
        failed(str): User-facing reason why nothing could be played.
    """

    busy_changed = Signal(bool)
    failed = Signal(str)
    volume_changed = Signal(float)

    def __init__(self, config: AppConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._voices = self._find_windows_voices()
        self._engines: dict[str, QTextToSpeech] = {}
        self._cache: OrderedDict[tuple[str, str], bytes] = OrderedDict()
        self._clip: _LiveClip | None = None
        self._format = QAudioFormat()
        self._format.setSampleRate(_SAMPLE_RATE)
        self._format.setChannelCount(1)
        self._format.setSampleFormat(QAudioFormat.SampleFormat.Int16)
        self._sink: QAudioSink | None = None
        self._device: QIODevice | None = None
        self._pending = bytearray()
        self._flush_timer = QTimer(self, interval=20)
        self._flush_timer.timeout.connect(self._flush)
        # Saving the volume waits until the slider stops, not on every step.
        self._save_timer = QTimer(self, singleShot=True, interval=600)
        self._save_timer.timeout.connect(lambda: save_config(self._config))
        log.info("Windows voices: %s", {k: v[1].name() for k, v in self._voices.items()} or "none")

    # ------------------------------------------------------------- public API
    def availability(self, language_code: str) -> str:
        """"" if ``language_code`` can be spoken now, else the reason (for a tooltip)."""
        if self._use_gemini() or self._has_windows_voice(language_code):
            return ""
        if self._config.speech_engine == SPEECH_GEMINI:
            return tr("speech.cloud_only")
        return tr("speech.no_voice")

    def speak(self, text: str, language_code: str) -> None:
        """Say ``text`` (in ``language_code``, "" = unknown), stopping anything playing."""
        text = text.strip()
        if not text:
            return
        self.stop()
        if not self._use_gemini():
            if self._device is None and self._has_windows_voice(language_code):
                self._say_with_windows(text, language_code)
            else:
                self.failed.emit(self.availability(language_code))
            return
        key = (text, language_code)
        if key in self._cache:
            self._cache.move_to_end(key)
            self._start_audio()
            self._feed(self._cache[key])
            return
        api_key = read_api_key(self._config.gemini_api_key_env)
        if not api_key:
            self.failed.emit(tr("speech.no_key"))
            return
        clip = _LiveClip(text, api_key, self._config.gemini_speech_model,
                         self._config.gemini_speech_voice, self._config.request_timeout, self)
        clip.chunk.connect(lambda pcm: self._on_clip_chunk(clip, pcm))
        clip.finished.connect(lambda pcm: self._on_clip_finished(clip, key, pcm))
        clip.failed.connect(lambda message: self._on_clip_failed(clip, key, message))
        self._clip = clip
        self.busy_changed.emit(True)

    @property
    def volume(self) -> float:
        """Pronunciation volume, 0-1."""
        return self._config.speech_volume

    def set_volume(self, volume: float) -> None:
        """Change the volume, also of what is playing now, and remember it in the config."""
        self._config.speech_volume = min(max(volume, 0.0), 1.0)
        if self._sink is not None:
            self._sink.setVolume(self.volume)
        for tts in self._engines.values():
            tts.setVolume(self.volume)
        self._save_timer.start()
        self.volume_changed.emit(self.volume)

    def stop(self) -> None:
        """Stop speaking and drop a clip still being generated."""
        if self._clip is not None:
            self._clip.cancel()
            self._clip.deleteLater()
            self._clip = None
            self.busy_changed.emit(False)
        self._stop_audio()
        for tts in self._engines.values():
            tts.stop()

    # -------------------------------------------------------------- internals
    def _use_gemini(self) -> bool:
        return (self._config.speech_engine != SPEECH_WINDOWS
                and self._config.provider == PROVIDER_GEMINI)

    def _has_windows_voice(self, language_code: str) -> bool:
        return self._config.speech_engine != SPEECH_GEMINI and language_code in self._voices

    def _say_with_windows(self, text: str, language_code: str) -> None:
        engine, voice = self._voices[language_code]
        tts = self._engine(engine)
        tts.setLocale(voice.locale())
        tts.setVoice(voice)
        tts.setVolume(self.volume)
        tts.say(text)

    def _on_clip_chunk(self, clip: _LiveClip, pcm: bytes) -> None:
        """Play audio while the rest is still being generated."""
        if clip is not self._clip:
            return
        if self._device is None:
            self._start_audio()
            self.busy_changed.emit(False)  # sound has started: no more "…"
        self._feed(pcm)

    def _on_clip_finished(self, clip: _LiveClip, key: tuple[str, str], pcm: bytes) -> None:
        if clip is not self._clip:
            return
        self._release(clip)
        self._cache[key] = pcm
        while len(self._cache) > _CACHE_SIZE:
            self._cache.popitem(last=False)

    def _on_clip_failed(self, clip: _LiveClip, key: tuple[str, str], message: str) -> None:
        if clip is not self._clip:
            return
        self._release(clip)
        text, language_code = key
        if self._device is None and self._has_windows_voice(language_code):
            log.warning("Gemini speech failed (%s), using the Windows voice", message)
            self._say_with_windows(text, language_code)
        elif self._device is None:
            self.failed.emit(message)

    def _release(self, clip: _LiveClip) -> None:
        self._clip = None
        clip.deleteLater()
        self.busy_changed.emit(False)

    @staticmethod
    def _find_windows_voices() -> dict[str, tuple[str, QVoice]]:
        """Map each supported language code to an installed voice (engine, voice)."""
        found: dict[str, tuple[str, QVoice]] = {}
        for engine in ("winrt", "sapi"):  # winrt voices sound better: they win
            if engine not in QTextToSpeech.availableEngines():
                continue
            tts = QTextToSpeech(engine)
            for locale in tts.availableLocales():
                code = QLocale.languageToCode(locale.language(),
                                              QLocale.LanguageCodeType.ISO639Part1)
                if not is_supported(code) or code in found:
                    continue
                tts.setLocale(locale)
                voices = tts.availableVoices()
                if voices:
                    found[code] = (engine, voices[0])
        return found

    def _engine(self, name: str) -> QTextToSpeech:
        if name not in self._engines:
            self._engines[name] = QTextToSpeech(name, self)
        return self._engines[name]

    def _start_audio(self) -> None:
        """Open a fresh audio stream on the default output device."""
        self._stop_audio()
        self._sink = QAudioSink(QMediaDevices.defaultAudioOutput(), self._format, self)
        self._sink.setBufferSize(_SAMPLE_RATE * 2 * _MAX_SECONDS)
        self._sink.setVolume(self.volume)
        self._device = self._sink.start()
        # An empty stream reports UnderrunError until data arrives: that is normal.
        if self._device is None or self._sink.error() in (QAudio.Error.OpenError,
                                                          QAudio.Error.FatalError):
            log.error("Audio output failed: %s", self._sink.error())
            self._stop_audio()
            self.failed.emit(tr("speech.no_device"))

    def _feed(self, pcm: bytes) -> None:
        self._pending += pcm
        self._flush()

    def _flush(self) -> None:
        """Write queued audio; whatever the device cannot take yet is retried shortly."""
        if self._device is None:
            self._pending.clear()
            self._flush_timer.stop()
            return
        written = self._device.write(bytes(self._pending)) if self._pending else 0
        if written > 0:
            del self._pending[:written]
        if self._pending:
            self._flush_timer.start()
        else:
            self._flush_timer.stop()

    def _stop_audio(self) -> None:
        self._flush_timer.stop()
        self._pending.clear()
        self._device = None
        if self._sink is not None:
            self._sink.stop()
            self._sink.deleteLater()
            self._sink = None
