"""Background worker that runs OCR, language detection and translation off the GUI thread."""

from __future__ import annotations

import logging

from collections.abc import Callable

from PIL import Image
from PySide6.QtCore import QObject, QThread, Signal, Slot

from backends import make_translator
from config import AppConfig
from i18n import tr
from lang_detect import LanguageDetector
from ocr import ocr_languages
from languages import get_language
from ocr import OcrEngine, OcrError
from pipeline import recognize_image
from translator import TranslationError, Translator

log = logging.getLogger(__name__)


class PipelineWorker(QObject):
    """Lives in its own QThread; requests are processed one at a time in arrival order.

    Every request carries an id that is echoed back, so the UI can drop results
    of requests that were superseded (e.g. the user switched language again).
    """

    # (request_id, text, source code or "" if unknown, detection confidence)
    recognized = Signal(int, str, str, float)
    # (request_id, translated text, source code found by the model or "")
    translated = Signal(int, str, str)
    # (request_id, user-facing message)
    failed = Signal(int, str)
    # (request_id, WordInfo) / (request_id, user-facing message) for word lookups
    defined = Signal(int, object)
    define_failed = Signal(int, str)

    def __init__(self, config: AppConfig, detector: LanguageDetector) -> None:
        super().__init__()
        self._config = config
        self._ocr: OcrEngine | None = None
        self._ocr_error: str | None = None
        self._detector = detector
        self._translator: Translator | None = None
        self._translator_error = ""
        # Id of the only word lookup still wanted; written by the GUI thread.
        self.wanted_define = 0

    @Slot()
    def initialize(self) -> None:
        """Create the remaining engines; called once in the worker thread."""
        cfg = self._config
        try:
            self._ocr = OcrEngine(str(cfg.resolved_tesseract_path()), cfg.resolved_tessdata_dir(),
                                  scale=cfg.ocr_scale)
        except OcrError as exc:
            self._ocr_error = str(exc)
            log.error("OCR init failed: %s", exc)
        self.reload_translator()
        log.info("Worker initialized")

    @Slot()
    def reload_translator(self) -> None:
        """(Re)create the translator for the provider currently set in the config."""
        old, self._translator = self._translator, None
        if old is not None:
            old.close()
        try:
            self._translator = make_translator(self._config)
            self._translator_error = ""
        except TranslationError as exc:
            self._translator_error = str(exc)
            log.error("Translator not available: %s", exc)

    def _image_model(self) -> Translator | None:
        """The cloud model that should read screenshots, or None to use Tesseract."""
        translator = self._translator
        if self._config.cloud_ocr and translator is not None and translator.vision:
            return translator
        return None

    def _require_translator(self) -> Translator:
        if self._translator is None:
            raise TranslationError(self._translator_error or tr("err.no_translator"))
        return self._translator

    @Slot(int, object, str, str)
    def process(self, request_id: int, image: Image.Image, target_code: str,
                source_code: str = "") -> None:
        """Recognize ``image`` and translate the text into ``target_code``.

        ``source_code`` is the language chosen by the user; "" means auto-detect.
        """
        try:
            if self._ocr is None and self._image_model() is None:
                self.failed.emit(request_id, self._ocr_error or tr("err.no_ocr"))
                return
            forced = get_language(source_code) if source_code else None
            rec = recognize_image(image, self._ocr, self._detector, forced, self._image_model())
            log.info("Request %d read by %s", request_id, rec.engine)
            if rec.ocr.is_empty:
                self.failed.emit(request_id, tr("err.no_text"))
                return
            # The local detection only picks Tesseract's language; the translation
            # model names the language (it knows many more).
            self.recognized.emit(request_id, rec.ocr.text, source_code, 1.0 if forced else 0.0)
            self.translate(request_id, rec.ocr.text, source_code, target_code)
        except OcrError as exc:
            self.failed.emit(request_id, str(exc))
        except Exception:  # never let the worker thread die silently
            log.exception("Unexpected error while processing request %d", request_id)
            self.failed.emit(request_id, tr("err.unexpected"))

    @Slot(int, str, str, str)
    def process_text(self, request_id: int, text: str, target_code: str,
                     source_code: str = "") -> None:
        """Translate typed ``text`` into ``target_code``.

        Its language is found by the translation model unless the user chose ``source_code``.
        """
        try:
            self.recognized.emit(request_id, text, source_code, 1.0 if source_code else 0.0)
            self.translate(request_id, text, source_code, target_code)
        except Exception:
            log.exception("Unexpected error while processing text request %d", request_id)
            self.failed.emit(request_id, tr("err.unexpected"))

    @Slot(int, str, str, str, str)
    def define(self, request_id: int, word: str, context: str, language_code: str,
               target_code: str) -> None:
        """Look up ``word`` in its own language; "" lets the model infer the language.

        The entry also carries the word's translation into ``target_code``.

        A queued lookup is skipped when another word was clicked or the card was
        closed before it started (:attr:`wanted_define` changed).
        """
        if request_id != self.wanted_define:
            log.info("Lookup %d skipped: no longer needed", request_id)
            return
        try:
            language = get_language(language_code) if language_code else None
            target = get_language(target_code) if target_code else None
            self.defined.emit(request_id, self._require_translator().define(
                word, context, language, target))
        except TranslationError as exc:
            log.warning("Definition failed: %s", exc)
            self.define_failed.emit(request_id, str(exc))
        except Exception:
            log.exception("Unexpected error while defining request %d", request_id)
            self.define_failed.emit(request_id, tr("err.unexpected"))

    @Slot(int, str, str, str)
    def translate(self, request_id: int, text: str, source_code: str, target_code: str) -> None:
        """Translate ``text``; an empty ``source_code`` lets the model detect the language."""
        try:
            source = get_language(source_code) if source_code else None
            result = self._require_translator().translate(text, source,
                                                          get_language(target_code))
            self.translated.emit(request_id, result.text,
                                 result.source.code if result.source else "")
        except TranslationError as exc:
            log.warning("Translation failed: %s", exc)
            self.failed.emit(request_id, str(exc))
        except Exception:
            log.exception("Unexpected error while translating request %d", request_id)
            self.failed.emit(request_id, tr("err.unexpected"))


class IdiomWorker(QObject):
    """Finds idioms in its own thread, so the search never delays a translation or lookup.

    Signals:
        found(int, list): (request_id, idioms as written in the text).
    """

    found = Signal(int, list)

    def __init__(self, translator: Callable[[], Translator | None]) -> None:
        super().__init__()
        self._translator = translator
        # Id of the only search still wanted; written by the GUI thread.
        self.wanted = 0

    @Slot(int, str, str)
    def find(self, request_id: int, text: str, language_code: str) -> None:
        """Search ``text`` unless a newer text arrived meanwhile; failures are only logged."""
        translator = self._translator()
        if request_id != self.wanted or translator is None:
            return
        try:
            language = get_language(language_code) if language_code else None
            self.found.emit(request_id, translator.find_idioms(text, language))
        except TranslationError as exc:
            log.warning("Idiom search failed: %s", exc)
        except Exception:
            log.exception("Unexpected error while looking for idioms")


class PipelineController(QObject):
    """Owns the worker thread and exposes thread-safe request methods to the GUI."""

    _process_requested = Signal(int, object, str, str)
    _process_text_requested = Signal(int, str, str, str)
    _translate_requested = Signal(int, str, str, str)
    _define_requested = Signal(int, str, str, str, str)
    _idioms_requested = Signal(int, str, str)
    _reload_requested = Signal()

    def __init__(self, config: AppConfig, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._next_id = 0
        self._thread = QThread()
        self._thread.setObjectName("PipelineThread")
        # lingua's native extension loads its language models here, before any other
        # thread of ours runs: a load overlapping with startup work once aborted the
        # whole process (0xc0000409 inside lingua.pyd). It takes about half a second.
        self.worker = PipelineWorker(
            config, LanguageDetector(ocr_languages(config.resolved_tessdata_dir())))
        self.worker.moveToThread(self._thread)
        self._thread.started.connect(self.worker.initialize)
        self._process_requested.connect(self.worker.process)
        self._process_text_requested.connect(self.worker.process_text)
        self._translate_requested.connect(self.worker.translate)
        self._define_requested.connect(self.worker.define)
        self._reload_requested.connect(self.worker.reload_translator)
        self._thread.start()
        self._idiom_thread = QThread()
        self._idiom_thread.setObjectName("IdiomThread")
        self.idioms = IdiomWorker(lambda: self.worker._translator)
        self.idioms.moveToThread(self._idiom_thread)
        self._idioms_requested.connect(self.idioms.find)
        self._idiom_thread.start()

    def _new_id(self) -> int:
        self._next_id += 1
        return self._next_id

    def process(self, image: Image.Image, target_code: str, source_code: str = "") -> int:
        """Queue OCR + translation of ``image`` ("" source = auto); returns the request id."""
        request_id = self._new_id()
        self._process_requested.emit(request_id, image, target_code, source_code)
        return request_id

    def process_text(self, text: str, target_code: str, source_code: str = "") -> int:
        """Queue translation of typed text ("" source = auto); returns the request id."""
        request_id = self._new_id()
        self._process_text_requested.emit(request_id, text, target_code, source_code)
        return request_id

    def translate(self, text: str, source_code: str, target_code: str) -> int:
        """Queue translation only; returns the request id."""
        request_id = self._new_id()
        self._translate_requested.emit(request_id, text, source_code, target_code)
        return request_id

    def define(self, word: str, context: str, language_code: str, target_code: str = "") -> int:
        """Queue a lookup of ``word`` (translated into ``target_code``); returns the id."""
        request_id = self._new_id()
        self.worker.wanted_define = request_id  # older queued lookups are skipped
        self._define_requested.emit(request_id, word, context, language_code, target_code)
        return request_id

    def find_idioms(self, text: str, language_code: str) -> int:
        """Queue an idiom search in ``text``; returns the request id."""
        request_id = self._new_id()
        self.idioms.wanted = request_id  # older queued searches are skipped
        self._idioms_requested.emit(request_id, text, language_code)
        return request_id

    def reload_translator(self) -> None:
        """Switch to the provider now set in the config (after queued requests)."""
        self._reload_requested.emit()

    def cancel_define(self) -> None:
        """Skip the queued word lookup, if any (the card was closed)."""
        self.worker.wanted_define = 0

    def shutdown(self) -> bool:
        """Stop the worker thread, waiting briefly for the current request.

        Returns:
            True if the thread stopped, False if it is still busy (e.g. a long LLM request).
        """
        self.idioms.wanted = 0
        self._idiom_thread.quit()
        self._thread.quit()
        if self._thread.wait(1000) and self._idiom_thread.wait(1000):
            return True
        # Most likely waiting for LM Studio: closing the client aborts the request.
        translator = self.worker._translator
        if translator is not None:
            translator.close()
        if not (self._thread.wait(3000) and self._idiom_thread.wait(1000)):
            log.warning("Worker thread did not stop in time")
            return False
        return True
