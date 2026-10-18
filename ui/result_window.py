"""Always-on-top window that shows the recognized text and its translation."""

from __future__ import annotations

import logging
import re

from PySide6.QtCore import (QEasingCurve, QEvent, QObject, QPoint, QPropertyAnimation, QRect, QSize,
                            Qt, QTimer, Signal)
from PySide6.QtGui import (QColor, QGuiApplication, QHideEvent, QKeySequence, QMouseEvent, QScreen,
                           QShortcut, QTextCharFormat, QTextCursor)
from PySide6.QtWidgets import (QComboBox, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                               QPlainTextEdit, QProgressBar, QPushButton, QTextEdit,
                               QVBoxLayout, QWidget)

from i18n import language, tr
from languages import get_language
from ui import theme as t
from ui.icon_buttons import CloseButton, GearButton
from ui.language_combo import LanguageCombo
from ui.word_popup import WordPopup

log = logging.getLogger(__name__)

_GAP = 6
# Characters trimmed from a clicked "word": punctuation, quotes, dashes, digits.
_WORD_STRIP = " \t.,;:!?¡¿\"'«»„“”‚‘’()[]{}<>…–—-_/\\|*#@%&+=~^`0123456789"
_SHADOW = 14  # transparent margin around the card that holds the drop shadow
_STYLE = f"""
* {{ font-family: "{t.FONT_FAMILY}"; }}
#card {{ background: {t.BG}; border: 1px solid {t.BORDER}; border-radius: 12px; }}
#header {{ background: transparent; border-bottom: 1px solid {t.BORDER}; }}
QLabel {{ color: {t.TEXT}; background: transparent; }}
#arrow {{ color: {t.TEXT_MUTED}; font-size: 14px; }}
#caption {{ color: {t.TEXT_MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}
#hint {{ color: {t.TEXT_MUTED}; font-size: 11px; }}
#status {{ color: {t.TEXT_DIM}; font-size: 12px; }}
#status[error="true"] {{ color: {t.ERROR}; }}
QPlainTextEdit {{ background: {t.FIELD}; border: 1px solid {t.BORDER}; border-radius: 8px;
                  padding: 6px 8px; selection-background-color: {t.ACCENT};
                  selection-color: white; }}
QPlainTextEdit:focus {{ border-color: {t.BORDER_HOVER}; }}
#original {{ color: {t.TEXT_DIM}; font-size: 13px; }}
#translation {{ color: {t.TEXT}; font-size: 15px; }}
QComboBox {{ background: {t.SURFACE}; color: {t.TEXT}; border: 1px solid {t.BORDER};
             border-radius: 7px; padding: 4px 10px; font-size: 12px; min-width: 130px; }}
QComboBox:hover {{ border-color: {t.BORDER_HOVER}; }}
QComboBox#targetCombo {{ border-color: {t.ACCENT}; }}
QComboBox#targetCombo:hover {{ border-color: {t.ACCENT_HOVER}; }}
QComboBox QAbstractItemView {{ background: {t.SURFACE}; color: {t.TEXT}; border: 1px solid {t.BORDER};
                               selection-background-color: #2d3140; selection-color: {t.TEXT};
                               outline: none; padding: 4px; }}
QToolButton#close {{ background: transparent; border: none; border-radius: 7px; }}
QToolButton#close:hover {{ background: #e5484d; }}
QToolButton#gear {{ background: transparent; border: none; border-radius: 7px; }}
QToolButton#gear:hover {{ background: #3a3e4c; }}
QPushButton {{ background: {t.SURFACE}; color: {t.TEXT}; border: 1px solid {t.BORDER};
               border-radius: 8px; padding: 7px 14px; font-size: 12px; font-weight: 600; }}
QPushButton:hover {{ border-color: {t.BORDER_HOVER}; background: #2a2d36; }}
QPushButton:pressed {{ background: #1f2128; }}
QPushButton#primary {{ background: {t.ACCENT}; color: white; border: 1px solid {t.ACCENT}; }}
QPushButton#primary:hover {{ background: {t.ACCENT_HOVER}; border-color: {t.ACCENT_HOVER}; }}
QPushButton#primary:pressed {{ background: {t.ACCENT_PRESSED}; }}
QPushButton:disabled, QPushButton#primary:disabled {{ color: {t.TEXT_MUTED}; background: {t.SURFACE};
                                                     border-color: {t.BORDER}; }}
QProgressBar {{ border: none; background: {t.SURFACE}; max-height: 3px; border-radius: 1px; }}
QProgressBar::chunk {{ background: {t.ACCENT}; border-radius: 1px; }}
"""


class _Header(QFrame):
    """Title bar that lets the user drag the frameless window."""

    def __init__(self, window: QWidget) -> None:
        super().__init__()
        self.setObjectName("header")
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self._window = window
        self._drag_offset: QPoint | None = None

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self._window.pos()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None:
            self._window.move(event.globalPosition().toPoint() - self._drag_offset)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None


class ResultWindow(QWidget):
    """Shows original text, translation, language pair and target-language selector.

    Two modes: *capture* (text recognized from the screen, read-only) and *manual*
    (the user types or pastes text and presses Translate / Ctrl+Enter).

    Clicking a word (double-clicking while the text is editable) asks for its
    dictionary entry in the word's own language, shown in :attr:`word_popup`.

    Signals:
        source_changed(str): The user picked another source language ("" = auto-detect).
        target_changed(str): The user picked another target language (ISO code).
        translate_requested(str): Manual mode: translate this text.
        quit_requested(): The user pressed ✕: turn the whole program off (Esc only hides).
        settings_requested(): The user pressed the gear button.
        word_clicked(str, str, str, QPoint): (word, surrounding text, language code
            or "" if unknown, global point under the word) for a dictionary lookup.
    """

    source_changed = Signal(str)
    target_changed = Signal(str)
    translate_requested = Signal(str)
    quit_requested = Signal()
    settings_requested = Signal()
    word_clicked = Signal(str, str, str, QPoint)

    def __init__(self) -> None:
        super().__init__(None, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("ScreenTranslator")
        self.setStyleSheet(_STYLE)
        self._source_code = ""
        self._manual = False
        self._build_ui()
        self.word_popup = WordPopup(self)
        self._fade = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade.setDuration(140)
        self._fade.setEasingCurve(QEasingCurve.Type.OutCubic)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, activated=self._on_escape)
        for keys in ("Ctrl+Return", "Ctrl+Enter"):
            QShortcut(QKeySequence(keys), self, activated=self._request_manual_translation)
        for edit in (self._original, self._translation):
            edit.viewport().installEventFilter(self)
        self._idioms: list[tuple[int, int]] = []  # (start, end) of idioms in the original
        self._original.textChanged.connect(self._clear_idioms)

    # ----------------------------------------------------------------- layout
    def _build_ui(self) -> None:
        card = QFrame(self)
        card.setObjectName("card")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(28)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 170))
        card.setGraphicsEffect(shadow)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(_SHADOW, _SHADOW - 4, _SHADOW, _SHADOW + 4)
        outer.addWidget(card)

        header = _Header(self)
        head = QHBoxLayout(header)
        head.setContentsMargins(14, 10, 8, 10)
        head.setSpacing(6)
        self._source = LanguageCombo(with_auto=True)
        arrow = QLabel("→")
        arrow.setObjectName("arrow")
        self._target = LanguageCombo(with_auto=False)
        self._target.setObjectName("targetCombo")
        self._source.currentIndexChanged.connect(self._on_source_index)
        self._target.currentIndexChanged.connect(self._on_target_index)
        self._gear = GearButton()
        self._gear.setObjectName("gear")
        self._gear.clicked.connect(self.settings_requested)
        self._close = CloseButton(size=28, cross=10, hover_color="white")
        self._close.setObjectName("close")
        self._close.clicked.connect(self.quit_requested)
        head.addWidget(self._source)
        head.addWidget(arrow)
        head.addWidget(self._target)
        head.addStretch(1)
        head.addSpacing(2)
        head.addWidget(self._gear)
        head.addWidget(self._close)

        self._original = QPlainTextEdit(readOnly=True)
        self._original.setObjectName("original")
        self._translation = QPlainTextEdit(readOnly=True)
        self._translation.setObjectName("translation")
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        self._status = QLabel()
        self._status.setObjectName("status")
        self._status.setWordWrap(True)
        self._status.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._translate_btn = QPushButton()
        self._translate_btn.setObjectName("primary")
        self._translate_btn.clicked.connect(self._request_manual_translation)
        self._copy_tr = QPushButton()
        self._copy_tr.setObjectName("primary")
        self._copy_tr.clicked.connect(lambda: self._copy(self._translation, self._copy_tr))
        self._copy_or = QPushButton()
        self._copy_or.clicked.connect(lambda: self._copy(self._original, self._copy_or))
        for button in (self._translate_btn, self._copy_tr, self._copy_or):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hint = QLabel()
        self._hint.setObjectName("hint")
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addWidget(self._translate_btn)
        buttons.addWidget(self._copy_tr)
        buttons.addWidget(self._copy_or)
        buttons.addStretch(1)
        buttons.addWidget(self._hint)

        body = QVBoxLayout()
        body.setContentsMargins(14, 12, 14, 14)
        body.setSpacing(6)
        self._original_caption = self._caption("")
        body.addWidget(self._original_caption)
        body.addWidget(self._original, 2)
        body.addSpacing(4)
        self._translation_caption = self._caption("")
        body.addWidget(self._translation_caption)
        body.addWidget(self._translation, 3)
        body.addWidget(self._progress)
        body.addWidget(self._status)
        body.addSpacing(2)
        body.addLayout(buttons)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(header)
        layout.addLayout(body)

        self.retranslate()

    def retranslate(self) -> None:
        """Set every text in the current interface language (also after a switch)."""
        self._fill_languages()
        self._target.setToolTip(tr("win.target_tip"))
        self._gear.setToolTip(tr("win.settings_tip"))
        self._close.setToolTip(tr("win.close_tip"))
        self._translate_btn.setText(tr("win.translate"))
        self._copy_tr.setText(tr("win.copy_translation"))
        self._copy_or.setText(tr("win.copy_original"))
        self._translation_caption.setText(tr("win.caption_translation"))
        self._apply_mode_texts()
        self._update_pair()
        if getattr(self, "_status_key", ""):
            self._status.setText(tr(self._status_key))
        if hasattr(self, "word_popup"):
            self.word_popup.retranslate()

    def _fill_languages(self) -> None:
        """(Re)fill both language lists in the interface language."""
        self._source.fill()
        self._target.fill()

    def _apply_mode_texts(self) -> None:
        manual = self._manual
        self._original.setPlaceholderText(tr("win.placeholder") if manual else "")
        self._original_caption.setText(tr("win.caption_text") if manual
                                       else tr("win.caption_original"))
        self._hint.setText(tr("win.hint_manual") if manual else tr("win.hint_capture"))

    @staticmethod
    def _caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("caption")
        return label

    # ------------------------------------------------------------- public API
    @property
    def target_code(self) -> str:
        """Currently selected target language code."""
        return self._target.currentData()

    @property
    def source_code(self) -> str:
        """Effective source language: chosen by the user or detected; "" if unknown."""
        return self._source_code

    @property
    def source_choice(self) -> str:
        """Source language picked in the dropdown; "" means auto-detect."""
        return self._source.currentData()

    @property
    def original_text(self) -> str:
        """Recognized text currently shown."""
        return self._original.toPlainText()

    @property
    def manual(self) -> bool:
        """True while the window is in manual-input mode."""
        return self._manual

    def start(self, selection: QRect, screen: QScreen, target_code: str,
              source_code: str = "") -> None:
        """Reset the window for a new capture and show it next to ``selection``.

        ``source_code`` preselects the source language ("" = auto-detect).
        """
        self._reset(target_code, source_code, manual=False)
        self.set_busy(tr("status.recognizing"))
        self._place(selection, screen)
        self._appear()

    def start_manual(self, screen: QScreen, target_code: str, source_code: str = "") -> None:
        """Open the window for typed or pasted text, centred on ``screen``."""
        self._reset(target_code, source_code, manual=True)
        self._set_status(tr("win.manual_prompt"), key="win.manual_prompt")
        area = screen.availableGeometry()
        center = QRect(0, 0, 560, 0)
        center.moveCenter(area.center())
        self._place(QRect(center.x(), area.center().y() - 230, 560, 0), screen)
        self._appear()
        self._original.setFocus()

    def set_source(self, source_code: str) -> None:
        """Update only the source language (manual mode keeps the typed text)."""
        self._source_code = source_code
        self._update_pair()

    def set_found_source(self, source_code: str) -> None:
        """Show the source language the translation model found (auto mode only)."""
        if source_code and not self.source_choice:
            self._source_code = source_code
            self._update_pair()

    def set_original(self, text: str, source_code: str) -> None:
        """Show the recognized ``text`` and its source language ("" if unknown)."""
        self._source_code = source_code
        self._original.setPlainText(text)
        self._update_pair()

    def set_idioms(self, idioms: list[str]) -> None:
        """Underline ``idioms`` (phrases as written) in the original; a click on any of
        their words looks up the whole expression."""
        text = self._original.toPlainText()
        spans = []
        for phrase in idioms:
            pattern = r"(?<!\w)" + r"\s+".join(map(re.escape, phrase.split())) + r"(?!\w)"
            spans += [m.span() for m in re.finditer(pattern, text, re.IGNORECASE)]
        spans.sort()
        self._idioms = [s for i, s in enumerate(spans)  # drop overlaps, keep the first
                        if not any(o[0] < s[1] and s[0] < o[1] for o in spans[:i])]
        log.info("Idioms marked: %d of %d", len(self._idioms), len(idioms))
        self.highlight_word(None, None)

    def set_busy(self, message: str = "") -> None:
        """Show the busy indicator with ``message`` (default: "Translating…")."""
        message = message or tr("status.translating")
        self._progress.show()
        self._copy_tr.setEnabled(False)
        self._set_status(message)

    def set_translation(self, text: str) -> None:
        """Show the translated ``text`` and hide the busy indicator."""
        self._translation.setPlainText(text)
        self._progress.hide()
        self._copy_tr.setEnabled(True)
        if self._source_code and self._source_code == self.target_code:
            self._set_status(tr("win.same_language"), key="win.same_language")
        elif not self._source_code:
            self._set_status(tr("win.unsure_language"), key="win.unsure_language")
        else:
            self._set_status("")

    def set_error(self, message: str) -> None:
        """Show an error ``message`` and hide the busy indicator."""
        self._progress.hide()
        self._translation.clear()
        self._copy_tr.setEnabled(False)
        self._set_status(f"⚠  {message}", error=True)

    def highlight_word(self, edit: QPlainTextEdit | None, cursor: QTextCursor | None) -> None:
        """Mark the looked-up word (or clear the mark when ``cursor`` is None).

        Idioms in the original stay marked either way.
        """
        marks: dict[QPlainTextEdit, list[QTextEdit.ExtraSelection]] = {
            self._original: [self._idiom_mark(start, end) for start, end in self._idioms],
            self._translation: [],
        }
        if edit is not None and cursor is not None:
            selection = QTextEdit.ExtraSelection()
            selection.cursor = cursor
            selection.format.setBackground(QColor(91, 140, 255, 70))
            selection.format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)
            selection.format.setUnderlineColor(QColor(t.ACCENT))
            marks[edit].append(selection)
        for e, selections in marks.items():
            e.setExtraSelections(selections)

    def _idiom_mark(self, start: int, end: int) -> QTextEdit.ExtraSelection:
        cursor = QTextCursor(self._original.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        mark = QTextEdit.ExtraSelection()
        mark.cursor = cursor
        mark.format.setBackground(QColor(91, 140, 255, 26))
        mark.format.setUnderlineStyle(QTextCharFormat.UnderlineStyle.DashUnderline)
        mark.format.setUnderlineColor(QColor(t.ACCENT_HOVER))
        return mark

    def _clear_idioms(self) -> None:
        """The text changed (new text or manual editing): the idiom positions are stale."""
        if self._idioms:
            self._idioms = []
            self.highlight_word(None, None)

    def close_word_popup(self) -> None:
        """Hide the dictionary card and the word mark."""
        self.word_popup.hide()
        self.highlight_word(None, None)

    # ------------------------------------------------------------ word lookup
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Turn clicks on words into dictionary lookups."""
        edit = next((e for e in (self._original, self._translation)
                     if e.viewport() is watched), None)
        if edit is None or not isinstance(event, QMouseEvent) \
                or event.button() != Qt.MouseButton.LeftButton:
            return super().eventFilter(watched, event)
        editable = not edit.isReadOnly()
        if event.type() == QEvent.Type.MouseButtonRelease and not editable:
            if not edit.textCursor().hasSelection():  # a click, not a drag-selection
                self._lookup_at(edit, event.position().toPoint())
        elif event.type() == QEvent.Type.MouseButtonDblClick and editable:
            # Editable text needs single clicks for the caret: double-click looks up.
            QTimer.singleShot(0, lambda p=event.position().toPoint(): self._lookup_at(edit, p))
        elif event.type() == QEvent.Type.MouseButtonPress:
            self.close_word_popup()
        return super().eventFilter(watched, event)

    def _lookup_at(self, edit: QPlainTextEdit, pos: QPoint) -> None:
        """Emit :attr:`word_clicked` for the word under ``pos`` in ``edit``, if any."""
        cursor = edit.cursorForPosition(pos)
        cursor.select(QTextCursor.SelectionType.WordUnderCursor)
        raw = cursor.selectedText()
        word = raw.strip(_WORD_STRIP)
        if not any(ch.isalpha() for ch in word) or len(word) > 40:
            return
        # cursorForPosition returns the nearest position even for clicks beside the
        # text; make sure the point really lies on the word.
        start = QTextCursor(cursor)
        start.setPosition(cursor.selectionStart())
        end = QTextCursor(cursor)
        end.setPosition(cursor.selectionEnd())
        left, right = edit.cursorRect(start), edit.cursorRect(end)
        if not (left.left() - 2 <= pos.x() <= right.right() + 2
                and left.top() <= pos.y() <= left.bottom()):
            return
        lead = len(raw) - len(raw.lstrip(_WORD_STRIP))
        cursor.setPosition(cursor.selectionStart() + lead)
        cursor.setPosition(cursor.position() + len(word), QTextCursor.MoveMode.KeepAnchor)
        if edit is self._original:
            idiom = next(((s, e) for s, e in self._idioms
                          if s <= cursor.selectionStart() < e), None)
            if idiom is not None:  # a word of an idiom: look up the whole expression
                cursor.setPosition(idiom[0])
                cursor.setPosition(idiom[1], QTextCursor.MoveMode.KeepAnchor)
                word = " ".join(cursor.selectedText().split())
                start = QTextCursor(cursor)
                start.setPosition(idiom[0])
                left = edit.cursorRect(start)
        self.highlight_word(edit, cursor)

        block = cursor.block()
        context = " ".join(b.text() for b in (block.previous(), block, block.next())
                           if b.isValid() and b.text().strip())
        language = self._source_code if edit is self._original else self.target_code
        anchor = edit.viewport().mapToGlobal(left.bottomLeft())
        self.word_clicked.emit(word, context, language, anchor)

    # -------------------------------------------------------------- internals
    def _reset(self, target_code: str, source_code: str, manual: bool) -> None:
        self.close_word_popup()
        self._manual = manual
        self._set_combo_silently(self._source, source_code)
        self._source_code = self.source_choice
        self._original.clear()
        self._translation.clear()
        self._original.setReadOnly(not manual)
        self._translate_btn.setVisible(manual)
        self._copy_or.setVisible(not manual)
        self._copy_tr.setEnabled(False)
        self._progress.hide()
        self._apply_mode_texts()
        self._set_combo_silently(self._target, target_code)
        self._update_pair()

    def _appear(self) -> None:
        if not self.isVisible():
            self.setWindowOpacity(0.0)
            self.show()
            self._fade.setStartValue(0.0)
            self._fade.setEndValue(1.0)
            self._fade.start()
        self.raise_()
        self.activateWindow()

    def _request_manual_translation(self) -> None:
        text = self._original.toPlainText().strip()
        if not self._manual or not text:
            return
        self.close_word_popup()
        self.set_busy()
        self.translate_requested.emit(text)

    def _on_escape(self) -> None:
        if self.word_popup.isVisible():
            self.close_word_popup()
        else:
            self.close()

    def hideEvent(self, event: QHideEvent) -> None:
        self.close_word_popup()
        super().hideEvent(event)

    def _on_source_index(self, _index: int) -> None:
        self.close_word_popup()
        # A chosen language applies at once; "auto" waits for the next detection.
        self._source_code = self.source_choice
        self._update_pair()
        self.source_changed.emit(self.source_choice)

    def _on_target_index(self, _index: int) -> None:
        self._update_pair()
        self.target_changed.emit(self.target_code)

    @staticmethod
    def _set_combo_silently(combo: QComboBox, code: str) -> None:
        index = combo.findData(code)
        if index >= 0:
            combo.blockSignals(True)
            combo.setCurrentIndex(index)
            combo.blockSignals(False)

    def _update_pair(self) -> None:
        """Show the detected language inside the "auto" item of the source list."""
        if self.source_choice:
            self._source.setItemText(0, tr("lang.auto"))
            self._source.setToolTip(tr("win.source_manual_tip"))
        elif self._source_code:
            lang = get_language(self._source_code)
            self._source.setItemText(0, tr("win.auto_item", label=lang.label))
            self._source.setToolTip(tr("win.source_found_tip", name=lang.display_name(language())))
        else:
            self._source.setItemText(0, tr("lang.auto"))
            self._source.setToolTip(tr("win.source_auto_tip"))

    def _set_status(self, message: str, error: bool = False, key: str = "") -> None:
        """Show ``message``; ``key`` (its i18n key) lets a language switch re-render it."""
        self._status_key = key
        self._status.setText(message)
        self._status.setVisible(bool(message))
        self._status.setProperty("error", error)
        self._status.style().unpolish(self._status)
        self._status.style().polish(self._status)

    def _copy(self, edit: QPlainTextEdit, button: QPushButton) -> None:
        text = edit.toPlainText()
        if not text:
            return
        QGuiApplication.clipboard().setText(text)
        if button.text().startswith("✓"):
            return
        button.setText(tr("win.copied"))
        QTimer.singleShot(1300, self.retranslate)

    def _place(self, selection: QRect, screen: QScreen) -> None:
        """Put the card below, above or beside ``selection`` without leaving the screen.

        The widget is larger than the visible card by the shadow margins, which are
        allowed to extend past the selection and the screen edge.
        """
        area = screen.availableGeometry()
        card = QSize(min(max(selection.width(), 480), 700, area.width() - 2 * _SHADOW),
                     min(420, area.height() - 2 * _SHADOW))
        self.resize(card.width() + 2 * _SHADOW, card.height() + 2 * _SHADOW)
        x = selection.left()
        if selection.bottom() + _GAP + card.height() <= area.bottom():
            y = selection.bottom() + _GAP
        elif selection.top() - _GAP - card.height() >= area.top():
            y = selection.top() - _GAP - card.height()
        else:  # tall selection: put the card to the right or left of it
            y = selection.top()
            if selection.right() + _GAP + card.width() <= area.right():
                x = selection.right() + _GAP
            else:
                x = selection.left() - _GAP - card.width()
        x = max(area.left(), min(x, area.right() - card.width() + 1))
        y = max(area.top(), min(y, area.bottom() - card.height() + 1))
        self.move(x - _SHADOW, y - (_SHADOW - 4))
