"""Language drop-down: the most spoken languages first, then all of them; the open list
never gets taller than the window it belongs to."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QFont, QStandardItemModel
from PySide6.QtWidgets import QComboBox, QWidget

from i18n import language, tr
from languages import TOP_CODES, get_language, sorted_languages


class LanguageCombo(QComboBox):
    """Combo box of languages; item data is the language code ("" = auto-detect).

    Args:
        with_auto: Start the list with an "Auto-detect" item.
    """

    def __init__(self, with_auto: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._with_auto = with_auto
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        # A compact closed box, a wide list; typing the first letters of a name jumps to it.
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setMinimumContentsLength(15)
        self.view().setMinimumWidth(300)
        self.fill()

    def fill(self) -> None:
        """(Re)fill the list in the interface language, keeping the selection."""
        ui = language()
        current = self.currentData()
        self.blockSignals(True)
        self.clear()
        if self._with_auto:
            self.addItem(tr("lang.auto"), "")
        self._add_header(tr("lang.top"))
        for code in TOP_CODES:
            lang = get_language(code)
            self.addItem(lang.display_name(ui), lang.code)
        self._add_header(tr("menu.all_languages"))
        for lang in sorted_languages(ui):
            self.addItem(lang.display_name(ui), lang.code)
        index = self.findData(current) if current is not None else -1
        if index < 0:
            index = 0 if self._with_auto else self._first_language()
        self.setCurrentIndex(index)
        self.blockSignals(False)

    def showPopup(self) -> None:  # noqa: N802 (Qt API)
        """Open the list no taller than the window, and inside its vertical span."""
        area = self._visible_area()
        row = max(self.view().sizeHintForRow(self.count() - 1), 1)
        self.setMaxVisibleItems(max(5, (area.height() - 16) // row))
        super().showPopup()
        popup = self.view().window()
        if popup.height() > area.height():
            popup.resize(popup.width(), area.height())
        y = min(max(popup.y(), area.top()), area.bottom() - popup.height() + 1)
        popup.move(popup.x(), y)

    def _visible_area(self) -> QRect:
        """Screen rectangle of the window's visible part: the outermost widget inside
        the window (a frameless window may have a transparent shadow margin)."""
        window = self.window()
        widget: QWidget = self
        while widget.parentWidget() is not None and widget.parentWidget() is not window:
            widget = widget.parentWidget()
        return QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size())

    def _add_header(self, text: str) -> None:
        """A section title: not selectable, skipped by the keyboard."""
        if self.count():
            self.insertSeparator(self.count())
        self.addItem(text, None)
        model = self.model()
        if isinstance(model, QStandardItemModel):
            item = model.item(self.count() - 1)
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            font = QFont(self.font())
            font.setBold(True)
            font.setPointSizeF(font.pointSizeF() * 0.9)
            item.setFont(font)

    def _first_language(self) -> int:
        return next(i for i in range(self.count()) if self.itemData(i))
