"""Record the README demo GIF and screenshots from the real app.

The "desktop" is drawn here (a page with Spanish text), so nothing from the real
screen ends up in the pictures; the app itself runs normally and translates with
the configured Gemini key. The result window briefly appears on screen.

    .venv\\Scripts\\python.exe docs\\make_media.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt, QTimer  # noqa: E402
from PySide6.QtGui import (QBrush, QColor, QFont, QGuiApplication, QImage,  # noqa: E402
                           QLinearGradient, QPainter, QPainterPath, QPen, QPixmap,
                           QTextCursor)
from PySide6.QtWidgets import QApplication, QTabWidget, QWidget  # noqa: E402

import config  # noqa: E402
import main  # noqa: E402
import speech  # noqa: E402
from capture import Capture  # noqa: E402
from i18n import set_language  # noqa: E402

OUT = ROOT / "docs" / "media"
SCALE = 2  # scene resolution: the OCR image and the screenshots stay crisp
GIF_WIDTH = 960

TITLE = "Notas de viaje"
TEXT = ("Ayer llovía a cántaros, pero no nos quedamos en casa. Mi hermano dijo que "
        "el museo estaba cerrado; pensé que me estaba tomando el pelo. Al final "
        "encontramos un café precioso, y el día valió la pena.")
CLICK_WORD = "cántaros"

# Never write the developer's config: the demo runs on defaults.
config.save_config = speech.save_config = main.save_config = lambda *a, **k: None


def wait_until(app: QApplication, predicate, timeout: float) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        app.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return False


def qimage_to_pil(image: QImage) -> Image.Image:
    image = image.convertToFormat(QImage.Format.Format_RGBA8888)
    data = bytes(image.constBits())[: image.sizeInBytes()]
    return Image.frombuffer("RGBA", (image.width(), image.height()), data, "raw", "RGBA",
                            image.bytesPerLine(), 1).convert("RGB")


class Scene:
    """The drawn desktop: a browser-like page with the Spanish text."""

    def __init__(self, area: QRect) -> None:
        self.area = area
        self.page = QRect(area.left() + 60, area.top() + 40, 640, 300)
        self.selection = QRect(self.page.left() + 28, self.page.top() + 70, 584, 150)
        self.image = QImage(area.width() * SCALE, area.height() * SCALE,
                            QImage.Format.Format_ARGB32_Premultiplied)
        self.image.setDevicePixelRatio(SCALE)
        p = QPainter(self.image)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        grad = QLinearGradient(0, 0, area.width(), area.height())
        grad.setColorAt(0, QColor("#2b3a67"))
        grad.setColorAt(1, QColor("#5b3e7a"))
        p.fillRect(QRect(0, 0, area.width(), area.height()), grad)
        page = self.local(self.page)
        path = QPainterPath()
        path.addRoundedRect(QRectF(page), 12, 12)
        p.fillPath(path, QColor("#fbfaf7"))
        bar = QRectF(page.left(), page.top(), page.width(), 34)
        top = QPainterPath()
        top.addRoundedRect(bar, 12, 12)
        top.addRect(QRectF(bar.left(), bar.top() + 17, bar.width(), 17))
        p.fillPath(top.simplified(), QColor("#e8e6e1"))
        for i, color in enumerate(("#ec6a5e", "#f4bf4f", "#61c554")):
            p.setBrush(QColor(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(page.left() + 18 + i * 18, page.top() + 17), 5.5, 5.5)
        p.setBrush(QColor("#ffffff"))
        p.drawRoundedRect(QRectF(page.left() + 80, page.top() + 8, page.width() - 100, 18), 9, 9)
        p.setPen(QColor("#8a877f"))
        p.setFont(QFont("Segoe UI", 8))
        p.drawText(QRectF(page.left() + 92, page.top() + 8, 300, 18),
                   Qt.AlignmentFlag.AlignVCenter, "blog.example/viajes/lluvia")
        sel = self.local(self.selection)
        p.setPen(QColor("#1d1d1f"))
        p.setFont(QFont("Georgia", 15, QFont.Weight.Bold))
        p.drawText(QRectF(sel.left() + 6, page.top() + 44, sel.width(), 28),
                   Qt.AlignmentFlag.AlignVCenter, TITLE)
        p.setPen(QColor("#2b2b2e"))
        p.setFont(QFont("Georgia", 13))
        p.drawText(QRectF(sel.adjusted(10, 12, -10, -8)),
                   int(Qt.TextFlag.TextWordWrap | Qt.AlignmentFlag.AlignTop), TEXT)
        p.end()

    def local(self, rect: QRect) -> QRect:
        return rect.translated(-self.area.topLeft())

    def selection_image(self) -> Image.Image:
        sel = self.local(self.selection)
        crop = self.image.copy(QRect(sel.left() * SCALE, sel.top() * SCALE,
                                     sel.width() * SCALE, sel.height() * SCALE))
        return qimage_to_pil(crop)


class Recorder:
    def __init__(self, app: QApplication, inst: main.ScreenTranslatorApp, scene: Scene) -> None:
        self.app, self.inst, self.scene = app, inst, scene
        self.frames: list[tuple[Image.Image, int]] = []
        self.crop: QRect | None = None

    def compose(self, *, selection: QRect | None = None, dim: bool = False,
                cursor: QPoint | None = None, popups: tuple[QWidget, ...] = (),
                window: bool = True) -> QImage:
        frame = self.scene.image.copy()
        p = QPainter(frame)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if dim:
            full = QRect(0, 0, self.scene.area.width(), self.scene.area.height())
            shade = QPainterPath()
            shade.addRect(QRectF(full))
            if selection is not None:
                hole = QPainterPath()
                hole.addRect(QRectF(self.scene.local(selection)))
                shade = shade.subtracted(hole)
            p.fillPath(shade, QColor(0, 0, 0, 110))
            if selection is not None:
                p.setPen(QPen(QColor("#6ea8ff"), 2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(self.scene.local(selection))
        widgets = ((self.inst._window,) if window else ()) + popups
        for widget in widgets:
            if widget.isVisible():
                pix: QPixmap = widget.grab()
                p.drawPixmap(widget.frameGeometry().topLeft() - self.scene.area.topLeft(), pix)
        if cursor is not None:
            self.draw_cursor(p, cursor - self.scene.area.topLeft())
        p.end()
        return frame

    @staticmethod
    def draw_cursor(p: QPainter, at: QPoint) -> None:
        pts = [(0, 0), (0, 17), (4.5, 13), (7.5, 20), (10, 19), (7, 12.5), (12.5, 12.5)]
        path = QPainterPath(QPointF(at))
        for x, y in pts[1:]:
            path.lineTo(QPointF(at) + QPointF(x, y))
        path.closeSubpath()
        p.setPen(QPen(QColor("black"), 1.2))
        p.setBrush(QBrush(QColor("white")))
        p.drawPath(path)

    def add(self, image: QImage, ms: int) -> None:
        self.frames.append((image, ms))

    def save_png(self, image: QImage, name: str, rect: QRect) -> None:
        local = self.scene.local(rect)
        image.copy(QRect(local.left() * SCALE, local.top() * SCALE,
                         local.width() * SCALE, local.height() * SCALE)).save(str(OUT / name))
        print("saved", name)

    def save_gif(self, name: str, rect: QRect) -> None:
        local = self.scene.local(rect)
        images = []
        for image, ms in self.frames:
            crop = image.copy(QRect(local.left() * SCALE, local.top() * SCALE,
                                    local.width() * SCALE, local.height() * SCALE))
            pil = qimage_to_pil(crop)
            height = round(pil.height * GIF_WIDTH / pil.width)
            images.append(pil.resize((GIF_WIDTH, height), Image.Resampling.LANCZOS))
        paletted = [im.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
                    for im in images]
        paletted[0].save(OUT / name, save_all=True, append_images=paletted[1:], loop=0,
                         duration=[ms for _, ms in self.frames], optimize=True, disposal=1)
        print("saved", name, f"{(OUT / name).stat().st_size / 1e6:.1f} MB", len(images), "frames")


def run(app: QApplication, inst: main.ScreenTranslatorApp) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    screen = QGuiApplication.primaryScreen()
    area = screen.availableGeometry()
    scene = Scene(area)
    rec = Recorder(app, inst, scene)
    w = inst._window
    sel = scene.selection
    start_cursor = sel.topLeft() + QPoint(-40, -30)

    # 1. The page, then the dimmed screen and a growing selection.
    rec.add(rec.compose(cursor=start_cursor, window=False), 1200)
    rec.add(rec.compose(dim=True, cursor=sel.topLeft(), window=False), 400)
    for i in range(1, 9):
        part = QRect(sel.topLeft(), sel.size() * (i / 8))
        rec.add(rec.compose(dim=True, selection=part, cursor=part.bottomRight(), window=False), 70)
    rec.add(rec.compose(dim=True, selection=sel, cursor=sel.bottomRight(), window=False), 400)

    # 2. The real pipeline: Gemini reads the picture and translates it.
    inst._on_captured(Capture(scene.selection_image(), sel, screen))
    wait_until(app, lambda: w.windowOpacity() > 0.99, 2)
    rec.add(rec.compose(cursor=sel.bottomRight()), 700)
    ok = wait_until(app, lambda: bool(w._translation.toPlainText().strip())
                    and not w._progress.isVisible(), 60)
    print("translated:", ok, repr(w._translation.toPlainText()[:80]))
    rec.add(rec.compose(cursor=sel.bottomRight()), 1600)
    wait_until(app, lambda: bool(w._idioms), 25)
    print("idioms:", len(w._idioms))

    # 3. Click a word of an idiom: the whole expression opens in the dictionary.
    edit = w._original
    index = edit.toPlainText().find(CLICK_WORD)
    cursor = QTextCursor(edit.document())
    cursor.setPosition(index + 2)
    point = edit.cursorRect(cursor).center()
    target = edit.viewport().mapToGlobal(point)
    origin = sel.bottomRight()
    for i in range(1, 9):
        rec.add(rec.compose(cursor=origin + (target - origin) * (i / 8)), 50)
    rec.add(rec.compose(cursor=target), 300)
    w._lookup_at(edit, point)
    popup = w.word_popup
    wait_until(app, lambda: popup.isVisible(), 3)
    rec.add(rec.compose(cursor=target, popups=(popup,)), 600)
    ok = wait_until(app, lambda: not popup._progress.isVisible(), 40)
    wait_until(app, lambda: False, 0.4)  # let the card finish resizing
    print("defined:", ok, repr(popup._lemma.text()))
    card_frame = rec.compose(popups=(popup,))
    rec.add(rec.compose(cursor=target + QPoint(0, -40), popups=(popup,)), 4200)

    # Screenshot: window with the dictionary card.
    bounds = w.frameGeometry().united(popup.frameGeometry()).united(scene.page)
    rec.save_png(card_frame, "translation.png", bounds.adjusted(-20, -20, 20, 20))
    popup.close()
    app.processEvents()

    # 4. Another target language from the list (the most spoken ones are on top).
    combo = w._target
    combo_point = combo.mapToGlobal(combo.rect().center())
    rec.add(rec.compose(cursor=combo_point), 500)
    combo.showPopup()
    wait_until(app, lambda: False, 0.3)
    listing = combo.view()
    french = combo.findData("fr")
    listing.setCurrentIndex(combo.model().index(french, 0))
    list_window = listing.window()
    item = listing.visualRect(combo.model().index(french, 0)).center()
    item_global = listing.viewport().mapToGlobal(item)
    rec.add(rec.compose(cursor=combo_point, popups=(list_window,)), 600)
    rec.add(rec.compose(cursor=item_global, popups=(list_window,)), 900)
    languages_frame = rec.compose(popups=(list_window,))
    rec.save_png(languages_frame, "languages.png",
                 w.frameGeometry().united(list_window.frameGeometry()).adjusted(-20, -20, 20, 20))
    combo.hidePopup()
    combo.setCurrentIndex(french)
    app.processEvents()
    rec.add(rec.compose(cursor=item_global), 500)
    ok = wait_until(app, lambda: not w._progress.isVisible()
                    and bool(w._translation.toPlainText().strip()), 60)
    print("french:", ok, repr(w._translation.toPlainText()[:60]))
    rec.add(rec.compose(cursor=item_global), 3500)

    gif_rect = scene.page.united(w.frameGeometry()).adjusted(-24, -24, 24, 24)
    gif_rect = gif_rect.intersected(area)
    rec.save_gif("demo.gif", gif_rect)

    # 5. Settings and the tray menu.
    inst.show_settings()
    dialog = inst._settings
    wait_until(app, lambda: dialog.isVisible(), 3)
    wait_until(app, lambda: False, 0.5)
    dialog.grab().save(str(OUT / "settings-general.png"))
    tabs = dialog.findChild(QTabWidget)
    tabs.setCurrentIndex(1)
    editor = dialog._models if hasattr(dialog, "_models") else None
    wait_until(app, lambda: False, 0.3)
    if editor is not None:
        wait_until(app, lambda: not editor._loading, 20)
        wait_until(app, lambda: False, 0.3)
    dialog.grab().save(str(OUT / "settings-models.png"))
    print("saved settings")
    dialog.close()

    menu = inst._menu
    menu.popup(area.center())
    wait_until(app, lambda: menu.isVisible(), 2)
    wait_until(app, lambda: False, 0.3)
    menu.grab().save(str(OUT / "tray-menu.png"))
    menu.hide()
    print("saved tray-menu.png")


def main_() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    cfg = config.load_config()
    cfg.ui_language = "en"
    cfg.target_language = "en"
    cfg.source_language = ""
    cfg.provider = config.PROVIDER_GEMINI
    set_language("en")
    inst = main.ScreenTranslatorApp(app, cfg)

    def go() -> None:
        try:
            run(app, inst)
        except Exception:
            import traceback
            traceback.print_exc()
        finally:
            inst._shutdown()
            sys.stdout.flush()
            os._exit(0)

    QTimer.singleShot(1500, go)
    app.exec()


if __name__ == "__main__":
    main_()
