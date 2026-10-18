"""Small header buttons whose icons are drawn with QPainter (the "✕" and "⚙" glyphs render blurry)."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QToolButton

from i18n import tr
from ui import theme as t


class _IconButton(QToolButton):
    """Square button: the stylesheet draws its background, :meth:`draw_icon` the icon.

    Args:
        size: Side of the button in pixels.
        icon: Size of the icon in pixels.
        hover_color: Color of the icon while the mouse is over the button.
    """

    def __init__(self, size: int, icon: int, hover_color: str) -> None:
        super().__init__()
        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)
        self._icon = icon
        self._color = QColor(t.TEXT_DIM)
        self._hover_color = QColor(hover_color)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)  # background and hover from the stylesheet
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self._hover_color if self.underMouse() else self._color
        self.draw_icon(painter, QPointF(self.width() / 2, self.height() / 2), self._icon / 2, color)

    def draw_icon(self, painter: QPainter, center: QPointF, half: float, color: QColor) -> None:
        raise NotImplementedError


class CloseButton(_IconButton):
    """Button with an "×"."""

    def __init__(self, size: int = 24, cross: int = 8, hover_color: str = t.TEXT) -> None:
        super().__init__(size, cross, hover_color)
        self.setToolTip(tr("popup.close_tip"))

    def draw_icon(self, painter: QPainter, center: QPointF, half: float, color: QColor) -> None:
        pen = QPen(color, 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(center + QPointF(-half, -half), center + QPointF(half, half))
        painter.drawLine(center + QPointF(-half, half), center + QPointF(half, -half))


class GearButton(_IconButton):
    """Button with a gear (settings)."""

    _TEETH = 8

    def __init__(self, size: int = 28, gear: int = 15, hover_color: str = t.TEXT) -> None:
        super().__init__(size, gear, hover_color)

    def draw_icon(self, painter: QPainter, center: QPointF, half: float, color: QColor) -> None:
        outer, inner, hole = half, half * 0.72, half * 0.34
        step = 2 * math.pi / self._TEETH
        points = []
        for i in range(self._TEETH):
            base = i * step - math.pi / 2
            # Each tooth: up the flank to the outer radius, across, down to the root.
            for angle, radius in ((base - step * 0.30, inner), (base - step * 0.17, outer),
                                  (base + step * 0.17, outer), (base + step * 0.30, inner)):
                points.append(center + QPointF(math.cos(angle) * radius,
                                               math.sin(angle) * radius))
        path = QPainterPath(points[0])
        for point in points[1:]:
            path.lineTo(point)
        path.closeSubpath()
        path.addEllipse(center, hole, hole)  # odd-even fill punches the hole
        path.setFillRule(Qt.FillRule.OddEvenFill)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawPath(path)
