"""Generate sample screenshots with text in every supported language."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SAMPLES: dict[str, str] = {
    "pl": "Dzień dobry! Dziękuję za szybką odpowiedź.\n"
          "Spotkanie zostało przełożone na przyszły czwartek.\n\n"
          "Proszę potwierdzić, czy ten termin Państwu odpowiada.",
    "ru": "Добрый день! Спасибо за быстрый ответ.\n"
          "Встреча перенесена на следующий четверг.\n\n"
          "Пожалуйста, подтвердите, подходит ли вам это время.",
    "en": "Good afternoon! Thank you for the quick reply.\n"
          "The meeting has been moved to next Thursday.\n\n"
          "Please confirm whether this time works for you.",
    "fr": "Bonjour ! Merci pour votre réponse rapide.\n"
          "La réunion a été reportée à jeudi prochain.\n\n"
          "Veuillez confirmer si cet horaire vous convient.",
    "es": "¡Buenas tardes! Gracias por la rápida respuesta.\n"
          "La reunión se ha trasladado al próximo jueves.\n\n"
          "Por favor, confirme si este horario le conviene.",
    "de": "Guten Tag! Vielen Dank für die schnelle Antwort.\n"
          "Das Treffen wurde auf nächsten Donnerstag verschoben.\n\n"
          "Bitte bestätigen Sie, ob Ihnen dieser Termin passt.",
}


def render(text: str, path: Path, dark: bool = False) -> None:
    """Render ``text`` like a typical 15px UI screenshot and save it to ``path``."""
    font = ImageFont.truetype("segoeui.ttf", 15)
    bg, fg = ((32, 33, 36), (230, 230, 230)) if dark else ((255, 255, 255), (20, 20, 20))
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    left, top, right, bottom = probe.multiline_textbbox((0, 0), text, font=font, spacing=6)
    image = Image.new("RGB", (right + 24, bottom + 24), bg)
    ImageDraw.Draw(image).multiline_text((12, 12), text, font=font, fill=fg, spacing=6)
    image.save(path)


def main() -> None:
    """Write ``<code>.png`` for every language plus one dark-theme sample."""
    out = Path(__file__).resolve().parent
    for code, text in SAMPLES.items():
        render(text, out / f"{code}.png")
    render(SAMPLES["pl"], out / "pl_dark.png", dark=True)
    print(f"Samples written to {out}")


if __name__ == "__main__":
    main()
