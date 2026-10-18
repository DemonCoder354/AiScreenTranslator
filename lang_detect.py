"""Source language detection restricted to the supported languages."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass

import lingua

from languages import Language

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DetectionResult:
    """Detected language.

    Attributes:
        language: The detected language, or None if detection was not confident.
        confidence: Confidence of the top candidate, 0-1.
    """

    language: Language | None
    confidence: float


class LanguageDetector:
    """Detects which of ``languages`` a text is written in.

    Every lingua model costs about 20 MB of memory, so the detector is given only
    the languages it has to tell apart (those Tesseract can read).

    Args:
        languages: Candidate languages; those lingua does not know are ignored.
        min_confidence: Top candidates below this confidence are reported as unknown.
        min_letters: Texts with fewer letters than this are reported as unknown.
    """

    def __init__(self, languages: Iterable[Language], min_confidence: float = 0.4,
                 min_letters: int = 3) -> None:
        self._to_app: dict[lingua.Language, Language] = {
            getattr(lingua.Language, lang.lingua): lang for lang in languages if lang.lingua
        }
        # lingua needs at least two candidates; with one there is nothing to tell apart.
        self._only = next(iter(self._to_app.values())) if len(self._to_app) == 1 else None
        self._detector = (
            lingua.LanguageDetectorBuilder.from_languages(*self._to_app)
            .with_preloaded_language_models()
            .build()
        ) if len(self._to_app) > 1 else None
        self.min_confidence = min_confidence
        self.min_letters = min_letters

    def detect(self, text: str) -> DetectionResult:
        """Detect the language of ``text``; never raises on empty or odd input."""
        if sum(ch.isalpha() for ch in text) < self.min_letters:
            return DetectionResult(None, 0.0)
        if self._detector is None:
            return DetectionResult(self._only, 1.0 if self._only else 0.0)
        values = self._detector.compute_language_confidence_values(text)
        if not values:
            return DetectionResult(None, 0.0)
        top = values[0]
        language = self._to_app.get(top.language)
        log.info("Detected %s with confidence %.2f", top.language.name, top.value)
        if top.value < self.min_confidence:
            return DetectionResult(None, top.value)
        return DetectionResult(language, top.value)
