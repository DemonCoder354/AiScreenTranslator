"""Build dist/ScreenTranslator.zip: the program as a folder with ScreenTranslator.exe.

The recipient needs nothing installed: Python, Qt and Tesseract are inside. Run with
the project's Python (PyInstaller from requirements-build.txt must be installed):

    .venv\\Scripts\\python.exe build.py
"""

from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path

import PyInstaller.__main__

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
APP = DIST / "ScreenTranslator"
TESSERACT = Path(r"C:\Program Files\Tesseract-OCR")
# Tesseract's own runtime: the training tools, docs and Java viewer are not needed.
TESSERACT_SKIP = {".html", ".jar"}

README_EN = """ScreenTranslator: translate text on your screen
==============================================

Getting started
  1. Unzip the archive into any folder (for example Documents\\ScreenTranslator).
     It does not run from inside the zip.
  2. Run ScreenTranslator.exe.
     If Windows shows "Windows protected your PC", click "More info" ->
     "Run anyway". The program is not signed with a certificate, so Windows
     does not recognize it.
  3. On first start the program asks for a free Google Gemini API key:
     open https://aistudio.google.com/apikey, sign in with a Google account,
     click "Create API key", copy the key and paste it into the program.
     The key stays on your computer only. Do not share it with anyone.

How to use
  Ctrl+Alt+T  select an area of the screen with text: the translation appears.
  Ctrl+Alt+R  a window to type or paste text.
  Click a word in the translation window to open the dictionary: pronunciation,
  meaning, example, synonyms, audio. Idioms are underlined and open as a whole.
  Esc hides the window (the program stays in the tray, next to the clock).
  The cross in the top-right corner of the window, or Quit in the tray menu,
  turns the program off.

Settings (gear button next to the cross, or the tray menu)
  General: pronunciation volume, interface language (English / Russian),
  Gemini API key.
  Models: which Gemini models translate, explain words and read images, and in
  what order. When a model is out of quota, the next one answers. Add models
  from the AI Studio list or type your own model ID.

Good to know
  Translation needs the internet: the text and the selected screen area are
  sent to the Google Gemini API. Do not translate passwords or other secrets.
  Settings and log: %APPDATA%\\ScreenTranslator (config.json, logs).
  A free key is usually enough for hundreds of translations a day.

To start the program with Windows, put a shortcut to ScreenTranslator.exe into
the startup folder (Win+R -> shell:startup) and add " --tray" to the shortcut
target, so the window does not open at startup.
"""

README_RU = """ScreenTranslator: переводчик текста с экрана
============================================

Запуск
  1. Распакуйте архив в любую папку (например, Документы\\ScreenTranslator).
     Запускать прямо из архива нельзя.
  2. Запустите ScreenTranslator.exe.
     Если Windows покажет «Система Windows защитила ваш компьютер», нажмите
     «Подробнее» -> «Выполнить в любом случае». Программа не подписана сертификатом,
     поэтому Windows её не узнаёт.
  3. При первом запуске программа попросит бесплатный ключ Google Gemini API:
     откройте https://aistudio.google.com/apikey, войдите в Google-аккаунт, нажмите
     «Create API key», скопируйте ключ и вставьте его в окно программы.
     Ключ хранится только на вашем компьютере. Никому его не передавайте.

Как пользоваться
  Ctrl+Alt+T  выделите мышью область экрана с текстом: появится перевод.
  Ctrl+Alt+R  окно для ввода или вставки текста.
  Клик по слову в окне перевода открывает словарь: транскрипция, значение,
  пример, синонимы, озвучка. Идиомы подчёркнуты и открываются целиком.
  Esc прячет окно (программа остаётся в трее, у часов).
  Крестик в правом верхнем углу окна или «Выход» в меню трея выключают программу.

Настройки (шестерёнка рядом с крестиком или меню трея)
  Основные: громкость озвучки, язык интерфейса (английский / русский), ключ
  Gemini API. Интерфейс по умолчанию на английском.
  Модели: какие модели Gemini переводят, объясняют слова и читают картинки, и в
  каком порядке. Если у модели кончился лимит, отвечает следующая. Модели можно
  добавлять из списка AI Studio или вписывать свой ID модели.

Важно знать
  Для перевода нужен интернет: текст и снимок выделенной области отправляются
  в Google Gemini API. Не переводите так пароли и другие секретные данные.
  Настройки и журнал: %APPDATA%\\ScreenTranslator (config.json, logs).
  Бесплатного ключа обычно хватает на сотни переводов в день.

Чтобы программа запускалась вместе с Windows, положите ярлык на
ScreenTranslator.exe в папку автозагрузки (Win+R -> shell:startup) и в свойствах
ярлыка допишите к пути объекта " --tray" (тогда окно не будет открываться).
"""

THIRD_PARTY = """Third-party components in this build
====================================

Qt / PySide6          LGPL-3.0     https://www.qt.io/licensing, https://code.qt.io
                      The Qt libraries are separate DLLs in the _internal folder
                      and can be replaced with a compatible version.
Tesseract OCR         Apache-2.0   https://github.com/tesseract-ocr/tesseract
                      (tesseract folder, license: tesseract\\LICENSE)
Tesseract tessdata    Apache-2.0   https://github.com/tesseract-ocr/tessdata
Lingua                Apache-2.0   https://github.com/pemistahl/lingua-py
OpenAI Python SDK     Apache-2.0   https://github.com/openai/openai-python
Pillow                MIT-CMU      https://python-pillow.org
mss                   MIT          https://github.com/BoboTiG/python-mss
pytesseract           Apache-2.0   https://github.com/madmaze/pytesseract
Python                PSF-2.0      https://www.python.org
The libraries bundled with Tesseract (Leptonica, ICU, libpng, libtiff and others)
are distributed under their own free licenses, see
https://github.com/UB-Mannheim/tesseract
"""


def build_exe() -> None:
    PyInstaller.__main__.run([
        str(ROOT / "run.pyw"),
        "--name", "ScreenTranslator",
        "--windowed",
        "--icon", str(ROOT / "icon.ico"),
        "--noconfirm",
        "--clean",
        "--distpath", str(DIST),
        "--workpath", str(ROOT / "build"),
        "--specpath", str(ROOT / "build"),
        "--collect-all", "lingua",  # native module plus its language models
        "--exclude-module", "tkinter",
    ])


def copy_tesseract() -> None:
    if not (TESSERACT / "tesseract.exe").is_file():
        sys.exit(f"Tesseract not found in {TESSERACT}: install it to build.")
    target = APP / "tesseract"
    target.mkdir()
    for path in TESSERACT.iterdir():
        is_runtime = path.name == "tesseract.exe" or path.suffix.lower() == ".dll"
        if path.is_file() and is_runtime and path.suffix.lower() not in TESSERACT_SKIP:
            shutil.copy2(path, target)
    shutil.copy2(TESSERACT / "doc" / "LICENSE", target / "LICENSE")
    # Language data used by the program, plus the output configs (tsv) Tesseract needs.
    tessdata = APP / "tessdata"
    shutil.copytree(ROOT / "tessdata", tessdata)
    for folder in ("configs", "tessconfigs"):
        shutil.copytree(TESSERACT / "tessdata" / folder, tessdata / folder)


def write_docs() -> None:
    (APP / "Read me.txt").write_text(README_EN, encoding="utf-8-sig")
    (APP / "Прочти меня.txt").write_text(README_RU, encoding="utf-8-sig")
    (APP / "Third-party licenses.txt").write_text(THIRD_PARTY, encoding="utf-8-sig")


def make_zip() -> Path:
    archive = DIST / "ScreenTranslator.zip"
    archive.unlink(missing_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(APP.rglob("*")):
            zf.write(path, Path("ScreenTranslator") / path.relative_to(APP))
    return archive


def main() -> None:
    build_exe()
    copy_tesseract()
    write_docs()
    archive = make_zip()
    size = sum(p.stat().st_size for p in APP.rglob("*") if p.is_file())
    print(f"\nFolder: {APP} ({size / 2**20:.0f} MB)")
    print(f"Archive: {archive} ({archive.stat().st_size / 2**20:.0f} MB)")


if __name__ == "__main__":
    main()
