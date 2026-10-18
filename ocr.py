"""Image preprocessing and text recognition with Tesseract."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import pytesseract
from PIL import Image, ImageEnhance, ImageFilter, ImageMath, ImageOps, ImageStat

from i18n import tr
from languages import DEFAULT_OCR_CODES, LANGUAGES, Language, get_language

log = logging.getLogger(__name__)

# Blur radius (in screen pixels) used to estimate the background. It must be
# larger than letter strokes, so text does not leak into the estimate.
_BACKGROUND_RADIUS = 20
# Background brightness spread (0-255) below which an image counts as evenly lit.
_EVEN_BACKGROUND = 40


def flatten_background(gray: Image.Image, radius: int = _BACKGROUND_RADIUS) -> Image.Image:
    """Remove uneven lighting and coloured backgrounds from dark-on-light text.

    The background is estimated by erasing the letters (max filter) and blurring
    what is left; every pixel is then divided by it, so shaded or tinted paper
    becomes evenly white and the letters keep their contrast. Images whose
    background is already even (ordinary screenshots) are returned unchanged:
    there the division would only wash out thin details such as umlaut dots.
    """
    step = 4  # estimate on a smaller copy: much faster and just as good
    small = gray.resize((max(1, gray.width // step), max(1, gray.height // step)),
                        Image.Resampling.BOX)
    small = small.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.GaussianBlur(radius / step))
    low, high = ImageStat.Stat(small).extrema[0]
    if high - low < _EVEN_BACKGROUND:
        return gray
    background = small.resize(gray.size, Image.Resampling.BILINEAR)
    flat = ImageMath.lambda_eval(lambda a: a["text"] * 255 / (a["bg"] + 1),
                                 text=gray, bg=background)
    return flat.convert("L")


def ocr_languages(tessdata_dir: Path | None) -> tuple[Language, ...]:
    """Languages whose traineddata is in ``tessdata_dir``; the bundled set if it is unknown."""
    if tessdata_dir is not None and tessdata_dir.is_dir():
        installed = {path.stem for path in tessdata_dir.glob("*.traineddata")}
        found = tuple(lang for lang in LANGUAGES if lang.tesseract in installed)
        if found:
            return found
    return tuple(get_language(code) for code in DEFAULT_OCR_CODES)


class OcrError(Exception):
    """Raised when Tesseract is missing, misconfigured or fails."""


@dataclass(frozen=True)
class OcrResult:
    """Recognized text.

    Attributes:
        text: Text with line breaks preserved and paragraphs separated by a blank line.
        confidence: Mean word confidence reported by Tesseract, 0-100 (0 if no words).
    """

    text: str
    confidence: float

    @property
    def is_empty(self) -> bool:
        """True if no text was recognized."""
        return not self.text.strip()


class OcrEngine:
    """Recognizes text on screenshots using Tesseract.

    Args:
        tesseract_path: Full path to ``tesseract.exe``.
        tessdata_dir: Directory with ``*.traineddata``; None uses Tesseract's default.
        languages: Languages Tesseract can read (their traineddata is installed);
            None takes them from ``tessdata_dir``.
        scale: Upscale factor applied before recognition.
        psm: Tesseract page segmentation mode (3 = automatic layout analysis).
    """

    def __init__(
        self,
        tesseract_path: str,
        tessdata_dir: Path | None = None,
        languages: tuple[Language, ...] | None = None,
        scale: float = 2.0,
        psm: int = 3,
    ) -> None:
        if not Path(tesseract_path).is_file():
            raise OcrError(tr("err.tesseract_missing", path=tesseract_path))
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        if tessdata_dir is not None:
            if not tessdata_dir.is_dir():
                raise OcrError(tr("err.tessdata_missing", path=tessdata_dir))
            # An env var avoids quoting problems with paths in the --tessdata-dir option.
            os.environ["TESSDATA_PREFIX"] = str(tessdata_dir)
        self.readable = languages if languages is not None else ocr_languages(tessdata_dir)
        self.languages = "+".join(lang.tesseract for lang in self.readable)
        self.scale = scale
        self.psm = psm

    def language_string(self, language: Language) -> str | None:
        """Tesseract languages for a text in ``language`` (plus English for embedded
        terms); None if its traineddata is not installed."""
        if language not in self.readable:
            return None
        tess = language.tesseract
        return tess if tess == "eng" else f"{tess}+eng"

    def preprocess(self, image: Image.Image) -> Image.Image:
        """Prepare a screenshot for Tesseract.

        Converts to grayscale, inverts light-on-dark text, evens out the
        background, upscales, boosts contrast slightly and adds a white margin.
        """
        gray = ImageOps.grayscale(image)
        if ImageStat.Stat(gray).mean[0] < 110:
            gray = ImageOps.invert(gray)  # Tesseract works best with dark text on light
        gray = flatten_background(gray)
        if self.scale != 1.0:
            size = (max(1, round(gray.width * self.scale)), max(1, round(gray.height * self.scale)))
            gray = gray.resize(size, Image.Resampling.LANCZOS)
        gray = ImageOps.autocontrast(gray, cutoff=1)
        gray = ImageEnhance.Contrast(gray).enhance(1.3)
        return ImageOps.expand(gray, border=20, fill=255)

    def recognize(self, image: Image.Image, languages: str | None = None) -> OcrResult:
        """Recognize text on ``image``.

        Args:
            image: Screenshot to recognize.
            languages: Tesseract language string overriding the engine default.

        Raises:
            OcrError: If Tesseract cannot be run or language data is missing.
        """
        prepared = self.preprocess(image)
        try:
            data = pytesseract.image_to_data(
                prepared,
                lang=languages or self.languages,
                config=f"--psm {self.psm}",
                output_type=pytesseract.Output.DICT,
            )
        except pytesseract.TesseractNotFoundError as exc:
            raise OcrError(tr("err.tesseract_run")) from exc
        except pytesseract.TesseractError as exc:
            log.error("Tesseract error: %s", exc)
            raise OcrError(tr("err.tesseract", error=exc.message or exc)) from exc
        result = self._assemble(data)
        log.info("OCR: %d chars, confidence %.1f", len(result.text), result.confidence)
        return result

    @staticmethod
    def _assemble(data: dict[str, list]) -> OcrResult:
        """Rebuild text from ``image_to_data`` output, keeping lines and paragraphs."""
        paragraphs: list[list[str]] = []
        current_par: tuple[int, int] | None = None
        current_line: tuple[int, int, int] | None = None
        words: list[str] = []
        confidences: list[float] = []

        def flush_line() -> None:
            if words:
                paragraphs[-1].append(" ".join(words))
                words.clear()

        for i, word in enumerate(data["text"]):
            word = word.strip()
            conf = float(data["conf"][i])
            if not word or conf < 0:
                continue
            par_key = (data["block_num"][i], data["par_num"][i])
            line_key = (*par_key, data["line_num"][i])
            if par_key != current_par:
                flush_line()
                paragraphs.append([])
                current_par = par_key
            elif line_key != current_line:
                flush_line()
            current_line = line_key
            words.append(word)
            confidences.append(conf)
        flush_line()

        text = "\n\n".join("\n".join(lines) for lines in paragraphs if lines)
        mean_conf = sum(confidences) / len(confidences) if confidences else 0.0
        return OcrResult(text=text, confidence=mean_conf)
