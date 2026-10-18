"""Console check of the pipeline without UI: image file -> OCR -> language -> translation.

Usage:
    python test_pipeline.py                      # all images in samples/, target from config
    python test_pipeline.py shot.png -t pl       # one image, translate to Polish
    python test_pipeline.py --no-translate       # OCR and detection only
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from PIL import Image

from backends import make_translator
from config import app_dir, load_config
from lang_detect import LanguageDetector
from languages import LANGUAGES, get_language
from logging_setup import setup_logging
from ocr import OcrEngine, OcrError
from pipeline import recognize_image
from translator import TranslationError


def main() -> int:
    """Run the pipeline on the given images and print the results."""
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("images", nargs="*", type=Path,
                        help="images to process (default: samples/*.png)")
    parser.add_argument("-t", "--target", choices=[lang.code for lang in LANGUAGES],
                        help="target language (default: target_language from config.json)")
    parser.add_argument("-s", "--source", choices=[lang.code for lang in LANGUAGES],
                        help="source language (default: source_language from config.json, "
                             "empty there = auto-detect)")
    parser.add_argument("--tesseract", action="store_true",
                        help="always use Tesseract, even when Gemini could read the image")
    parser.add_argument("--no-translate", action="store_true", help="skip the LLM step")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    setup_logging()
    config = load_config()
    target = get_language(args.target or config.target_language)
    source_code = args.source or config.source_language
    forced = get_language(source_code) if source_code else None
    images = args.images or sorted((app_dir() / "samples").glob("*.png"))
    if not images:
        print("Нет картинок. Запустите: python samples/make_samples.py")
        return 1

    try:
        ocr = OcrEngine(str(config.resolved_tesseract_path()), config.resolved_tessdata_dir(),
                        scale=config.ocr_scale)
    except OcrError as exc:
        print(f"OCR: {exc}")
        return 1
    detector = LanguageDetector(ocr.readable)
    try:
        translator = make_translator(config)
    except TranslationError as exc:
        print(exc)
        return 1

    image_model = (translator if config.cloud_ocr and translator.vision
                   and not args.tesseract else None)
    failures = 0
    for path in images:
        print(f"\n===== {path.name} =====")
        started = time.perf_counter()
        try:
            rec = recognize_image(Image.open(path), ocr, detector, forced, image_model)
        except (OSError, OcrError) as exc:
            print(f"Ошибка OCR: {exc}")
            failures += 1
            continue
        ocr_time = time.perf_counter() - started
        source = rec.detection.language
        print(f"OCR ({rec.engine}) {ocr_time:.1f} s, уверенность {rec.ocr.confidence:.0f}%; "
              f"язык: {source.label if source else '?'} ({rec.detection.confidence:.2f})")
        if rec.ocr.is_empty:
            print("Текст не распознан.")
            continue
        print(f"--- оригинал ---\n{rec.ocr.text}")
        if args.no_translate:
            continue
        started = time.perf_counter()
        try:
            result = translator.translate(rec.ocr.text, source, target)
        except TranslationError as exc:
            print(f"Ошибка перевода: {exc}")
            failures += 1
            continue
        found = result.source
        print(f"--- перевод {found.label if found else '?'} → {target.label} "
              f"({time.perf_counter() - started:.1f} s) ---\n{result.text}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
