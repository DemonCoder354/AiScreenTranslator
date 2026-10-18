"""Screen-area selection overlay and screenshot capture with ``mss``.

All monitors are captured first, then each monitor shows its frozen, dimmed
screenshot in a full-screen overlay. The selected rectangle is cropped from the
physical-pixel screenshot, so Windows display scaling (125%, 150%, mixed DPI)
does not distort the result.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import mss
from PIL import Image
from PySide6.QtCore import QObject, QPoint, QRect, Qt, Signal
from PySide6.QtGui import (QColor, QCursor, QFont, QFontMetrics, QGuiApplication, QImage, QKeyEvent,
                           QMouseEvent, QPainter, QPaintEvent, QPen, QPixmap, QScreen)
from PySide6.QtWidgets import QWidget

from i18n import tr

log = logging.getLogger(__name__)

_MIN_SELECTION = 6  # logical pixels; smaller drags are treated as accidental clicks
_DIM = QColor(8, 9, 12, 150)
_ACCENT = QColor(91, 140, 255)


@dataclass(frozen=True)
class Capture:
    """A captured screen area.

    Attributes:
        image: Cropped screenshot in physical pixels.
        rect: Selected area in global logical (Qt) coordinates.
        screen: Screen the area was selected on.
    """

    image: Image.Image
    rect: QRect
    screen: QScreen


@dataclass
class _ScreenShot:
    screen: QScreen
    image: Image.Image  # physical pixels of the whole monitor


def _grab_all_screens() -> list[_ScreenShot]:
    """Capture every QScreen with mss, matching monitors by their physical origin.

    Qt 6 keeps a screen's top-left corner in native coordinates and scales only
    its size, so ``screen.geometry().topLeft()`` equals the mss monitor origin.
    """
    screens = QGuiApplication.screens()
    shots: list[_ScreenShot] = []
    with mss.mss() as sct:
        monitors = sct.monitors[1:]
        for index, screen in enumerate(screens):
            geo = screen.geometry()
            monitor = next((m for m in monitors
                            if m["left"] == geo.x() and m["top"] == geo.y()), None)
            if monitor is None:
                log.warning("No mss monitor at %s for %s, falling back to index",
                            geo.topLeft(), screen.name())
                monitor = monitors[min(index, len(monitors) - 1)]
            raw = sct.grab(monitor)
            image = Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
            shots.append(_ScreenShot(screen, image))
            log.debug("Captured %s: logical %s, physical %s", screen.name(), geo, raw.size)
    return shots


def _to_pixmap(image: Image.Image) -> QPixmap:
    data = image.tobytes("raw", "RGB")
    qimage = QImage(data, image.width, image.height, image.width * 3, QImage.Format.Format_RGB888)
    return QPixmap.fromImage(qimage.copy())  # copy: detach from the Python buffer


class _Overlay(QWidget):
    """Full-screen overlay on one monitor that lets the user drag a rectangle."""

    selected = Signal(object, QRect)  # (overlay, rect in widget coordinates)
    cancelled = Signal()

    def __init__(self, shot: _ScreenShot) -> None:
        super().__init__(None, Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.shot = shot
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setGeometry(shot.screen.geometry())
        self._pixmap = _to_pixmap(shot.image)
        self._origin: QPoint | None = None
        self._current: QPoint | None = None

    @property
    def scale(self) -> tuple[float, float]:
        """Physical pixels per logical pixel along x and y."""
        return (self.shot.image.width / max(1, self.width()),
                self.shot.image.height / max(1, self.height()))

    def selection(self) -> QRect:
        if self._origin is None or self._current is None:
            return QRect()
        return QRect(self._origin, self._current).normalized()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPixmap(self.rect(), self._pixmap)
        painter.fillRect(self.rect(), _DIM)
        sel = self.selection()
        if sel.isEmpty():
            self._draw_pill(painter, tr("capture.hint"),
                            QPoint(self.width() // 2, 48), 14)
            return
        sx, sy = self.scale
        source = QRect(round(sel.x() * sx), round(sel.y() * sy),
                       round(sel.width() * sx), round(sel.height() * sy))
        painter.drawPixmap(sel, self._pixmap, source)
        painter.setPen(QPen(_ACCENT, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(sel.adjusted(0, 0, -1, -1))
        # Corner handles
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_ACCENT)
        for corner in (sel.topLeft(), sel.topRight(), sel.bottomLeft(), sel.bottomRight()):
            painter.drawEllipse(corner, 4, 4)
        # Size label below the selection (above it near the bottom edge)
        w, h = round(sel.width() * sx), round(sel.height() * sy)
        below = sel.bottom() + 22
        y = below if below + 16 < self.height() else sel.top() - 22
        self._draw_pill(painter, f"{w} × {h}", QPoint(sel.center().x(), y), 11)

    def _draw_pill(self, painter: QPainter, text: str, center: QPoint, size: int) -> None:
        """Draw ``text`` in a rounded dark label centered at ``center``."""
        font = QFont("Segoe UI", size)
        font.setPixelSize(round(size * 1.35))
        painter.setFont(font)
        metrics = QFontMetrics(font)
        pad_x, pad_y = round(size * 1.2), round(size * 0.55)
        rect = QRect(0, 0, metrics.horizontalAdvance(text) + 2 * pad_x,
                     metrics.height() + 2 * pad_y)
        rect.moveCenter(center)
        rect.moveLeft(max(6, min(rect.left(), self.width() - rect.width() - 6)))
        painter.setPen(QPen(QColor(255, 255, 255, 30), 1))
        painter.setBrush(QColor(22, 23, 28, 225))
        painter.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        painter.setPen(QColor(231, 233, 238))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.RightButton:
            self.cancelled.emit()
        elif event.button() == Qt.MouseButton.LeftButton:
            self._origin = self._current = event.position().toPoint()
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._origin is not None:
            self._current = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._origin is None:
            return
        self._current = event.position().toPoint()
        sel = self.selection()
        self._origin = self._current = None
        if sel.width() < _MIN_SELECTION or sel.height() < _MIN_SELECTION:
            self.update()
            return
        self.selected.emit(self, sel)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.cancelled.emit()


class CaptureController(QObject):
    """Shows selection overlays on all monitors and emits the captured area."""

    captured = Signal(object)  # Capture
    cancelled = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._overlays: list[_Overlay] = []

    @property
    def active(self) -> bool:
        """True while overlays are shown."""
        return bool(self._overlays)

    def start(self) -> None:
        """Freeze all screens and let the user select an area. Ignored if already active."""
        if self.active:
            return
        try:
            shots = _grab_all_screens()
        except mss.ScreenShotError as exc:
            log.error("Screen capture failed: %s", exc)
            self.cancelled.emit()
            return
        cursor_screen = QGuiApplication.screenAt(QCursor.pos())
        for shot in shots:
            overlay = _Overlay(shot)
            overlay.selected.connect(self._on_selected)
            overlay.cancelled.connect(self._on_cancelled)
            self._overlays.append(overlay)
            overlay.show()
        focus = next((o for o in self._overlays if o.shot.screen is cursor_screen),
                     self._overlays[0] if self._overlays else None)
        if focus is not None:
            focus.raise_()
            focus.activateWindow()
            focus.setFocus()
            focus.grabKeyboard()  # Esc must work even if Windows refuses activation

    def _close_overlays(self) -> None:
        for overlay in self._overlays:
            overlay.releaseKeyboard()
            overlay.close()
        self._overlays.clear()

    def _on_selected(self, overlay: _Overlay, sel: QRect) -> None:
        sx, sy = overlay.scale
        box = (round(sel.left() * sx), round(sel.top() * sy),
               round((sel.right() + 1) * sx), round((sel.bottom() + 1) * sy))
        image = overlay.shot.image.crop(box)
        rect = QRect(overlay.mapToGlobal(sel.topLeft()), sel.size())
        screen = overlay.shot.screen
        log.info("Selected %s on %s -> %dx%d px", rect, screen.name(), image.width, image.height)
        self._close_overlays()
        self.captured.emit(Capture(image, rect, screen))

    def _on_cancelled(self) -> None:
        log.info("Capture cancelled")
        self._close_overlays()
        self.cancelled.emit()
