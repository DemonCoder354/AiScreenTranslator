"""UI-independent recognition pipeline.

Tesseract: OCR -> language detection -> refined OCR. With a cloud model that reads
images (Gemini), the model transcribes the screenshot instead and Tesseract is
the fallback. The language shown to the user comes from the translation model,
which knows far more languages than the local detector.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

from PIL import Image

from i18n import tr
from lang_detect import DetectionResult, LanguageDetector
from languages import Language
from ocr import OcrEngine, OcrError, OcrResult
from translator import TranslationError, Translator

log = logging.getLogger(__name__)

# Longest image side sent to the model: enough for a full screen of small text
# while keeping the upload (and the token cost) moderate.
_MAX_UPLOAD_SIDE = 3072


@dataclass(frozen=True)
class Recognition:
    """Result of recognizing a screenshot.

    Attributes:
        ocr: Final OCR result (refined with the detected language when possible).
        detection: Source language: chosen by the user, or found by the local
            detector (Tesseract path only; it knows just the languages Tesseract reads).
        engine: What read the text: "tesseract" or the model's service name.
    """

    ocr: OcrResult
    detection: DetectionResult
    engine: str = "tesseract"


def recognize_image(image: Image.Image, ocr: OcrEngine | None, detector: LanguageDetector,
                    source: Language | None = None,
                    model: Translator | None = None) -> Recognition:
    """Recognize ``image`` with the vision ``model`` if given, else (or if it fails) Tesseract.

    Raises:
        OcrError: If Tesseract is needed but missing or failing.
    """
    if model is not None and model.vision:
        try:
            return recognize_with_model(image, model, source)
        except TranslationError as exc:
            log.warning("%s could not read the image, using Tesseract: %s", model.service, exc)
            if ocr is None:
                raise OcrError(str(exc)) from exc
    if ocr is None:
        raise OcrError(tr("err.no_ocr"))
    return recognize(image, ocr, detector, source)


def recognize_with_model(image: Image.Image, model: Translator,
                         source: Language | None = None) -> Recognition:
    """Let a vision model transcribe ``image``; the translation model names the language.

    Raises:
        TranslationError: If the model or the server fails.
    """
    picture = image.convert("RGB")
    if max(picture.size) > _MAX_UPLOAD_SIDE:
        picture.thumbnail((_MAX_UPLOAD_SIDE, _MAX_UPLOAD_SIDE), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    picture.save(buffer, format="PNG", optimize=True)
    text = model.transcribe(buffer.getvalue(), source).strip()
    # The model reports no confidence; 100 marks "not from Tesseract" in logs.
    result = OcrResult(text, 100.0 if text else 0.0)
    detection = DetectionResult(source, 1.0 if source else 0.0)
    if not text:
        return Recognition(result, detection, model.service)
    return Recognition(result, detection, f"{model.service} ({model.last_model})")


def recognize(image: Image.Image, ocr: OcrEngine, detector: LanguageDetector,
              source: Language | None = None) -> Recognition:
    """Recognize text and its language on ``image``.

    When the user picked ``source`` explicitly, detection is skipped and a single
    pass with that language (plus English) is made, or with every installed
    language if Tesseract cannot read ``source``.

    The first pass uses all supported languages, which lets Tesseract mix up
    look-alike letters (Cyrillic vs Latin) and drop diacritics. Once the language
    is known, a second pass with only that language (plus English for embedded
    terms) gives much cleaner text.

    Raises:
        OcrError: If Tesseract fails.
    """
    if source is not None:
        result = ocr.recognize(image, ocr.language_string(source))
        return Recognition(result, DetectionResult(source, 1.0))

    first = ocr.recognize(image)
    if first.is_empty:
        return Recognition(first, DetectionResult(None, 0.0))
    detection = detector.detect(first.text)
    if detection.language is None:
        return Recognition(first, detection)

    languages = ocr.language_string(detection.language)
    refined = ocr.recognize(image, languages)
    if refined.is_empty:
        return Recognition(first, detection)
    log.info("Refined OCR with %s: confidence %.1f -> %.1f",
             languages, first.confidence, refined.confidence)
    return Recognition(refined, detection)
