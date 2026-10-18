"""Small dictionary card shown next to a clicked word: pronunciation, meaning, example, synonyms."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QHideEvent, QMouseEvent
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                               QProgressBar, QSlider, QToolButton, QVBoxLayout, QWidget)

from i18n import tr
from speech import Speaker
from translator import WordInfo
from ui import theme as t
from ui.icon_buttons import CloseButton
from ui.flow_layout import FlowLayout

_SHADOW = 12
_WIDTH = 340
_STYLE = f"""
* {{ font-family: "{t.FONT_FAMILY}"; }}
#card {{ background: {t.SURFACE}; border: 1px solid {t.BORDER_HOVER}; border-radius: 10px; }}
QLabel {{ background: transparent; color: {t.TEXT}; }}
#lemma {{ font-size: 16px; font-weight: 700; }}
#translation {{ color: {t.ACCENT_HOVER}; font-size: 15px; font-weight: 600; }}
#lang {{ color: {t.TEXT_MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}
#pos {{ color: {t.ACCENT_HOVER}; font-size: 12px; font-style: italic; }}
#ipa {{ color: {t.TEXT_DIM}; font-family: "Cambria", "Lucida Sans Unicode"; font-size: 15px; }}
#example {{ color: {t.TEXT_DIM}; font-size: 12px; font-style: italic; }}
QToolButton#speak {{ color: {t.ACCENT_HOVER}; font-size: 14px; min-width: 26px; min-height: 24px; }}
QToolButton#speakSmall {{ color: {t.TEXT_MUTED}; font-size: 12px; min-width: 22px; min-height: 20px; }}
QToolButton#speak:hover, QToolButton#speakSmall:hover {{ color: {t.TEXT}; }}
#definition {{ color: {t.TEXT}; font-size: 13px; }}
#caption {{ color: {t.TEXT_MUTED}; font-size: 10px; font-weight: 700; letter-spacing: 1px; }}
#chip {{ background: #2d3140; color: {t.TEXT}; border: 1px solid {t.BORDER_HOVER};
         border-radius: 10px; padding: 2px 9px; font-size: 12px; }}
#message {{ color: {t.TEXT_DIM}; font-size: 12px; }}
#message[error="true"] {{ color: {t.ERROR}; }}
QToolButton {{ background: transparent; color: {t.TEXT_DIM}; border: none; border-radius: 6px;
               font-size: 12px; min-width: 22px; min-height: 22px; }}
QToolButton:hover {{ background: #3a3e4c; color: {t.TEXT}; }}
#volumeIcon {{ color: {t.TEXT_MUTED}; font-size: 11px; }}
QSlider::groove:horizontal {{ height: 3px; background: {t.BORDER_HOVER}; border-radius: 1px; }}
QSlider::sub-page:horizontal {{ background: {t.ACCENT}; border-radius: 1px; }}
QSlider::handle:horizontal {{ background: {t.TEXT}; width: 10px; height: 10px; margin: -4px 0;
                              border-radius: 5px; }}
QSlider::handle:horizontal:hover {{ background: white; }}
QProgressBar {{ border: none; background: {t.BG}; max-height: 3px; border-radius: 1px; }}
QProgressBar::chunk {{ background: {t.ACCENT}; border-radius: 1px; }}
"""


class WordPopup(QWidget):
    """Frameless card with a word's meaning, shown on top of the result window.

    It does not grab the mouse, so the user can click the next word right away. A
    click anywhere else, or switching to another program, closes it.

    Signals:
        closed(): The card was hidden (lets the app cancel a lookup in progress).
    """

    closed = Signal()

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
                         | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(_STYLE)
        self._anchor = QPoint()
        self._language_code = ""
        self._speaker: Speaker | None = None
        self._speaking: QToolButton | None = None
        self._language_label = ""
        self._build_ui()
        self.retranslate()
        QGuiApplication.instance().installEventFilter(self)
        QGuiApplication.instance().applicationStateChanged.connect(self._on_app_state)

    def _build_ui(self) -> None:
        card = QFrame(self)
        card.setObjectName("card")
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 170))
        card.setGraphicsEffect(shadow)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(_SHADOW, _SHADOW - 4, _SHADOW, _SHADOW + 4)
        outer.addWidget(card)

        self._lang = QLabel()
        self._lang.setObjectName("lang")
        self._close = close = CloseButton()
        close.clicked.connect(self.hide)
        self._volume_icon = QLabel("🔈")
        self._volume_icon.setObjectName("volumeIcon")
        self._volume = QSlider(Qt.Orientation.Horizontal)
        self._volume.setRange(0, 100)
        self._volume.setFixedWidth(72)
        self._volume.setCursor(Qt.CursorShape.PointingHandCursor)
        self._volume.valueChanged.connect(self._on_volume)
        for widget in (self._volume_icon, self._volume):
            widget.hide()
        top = QHBoxLayout()
        top.setSpacing(4)
        top.addWidget(self._lang)
        top.addStretch(1)
        top.addWidget(self._volume_icon)
        top.addWidget(self._volume)
        top.addSpacing(6)
        top.addWidget(close)

        self._lemma = QLabel()
        self._lemma.setObjectName("lemma")
        self._lemma.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._speak_word = self._speak_button("speak")
        self._speak_word.clicked.connect(
            lambda: self._speak(self._lemma.text(), self._speak_word))
        # The translation sits right of the speaker; when it does not fit there (an
        # idiom), it moves to its own line under the word.
        self._translation = self._translation_label()
        self._translation_below = self._translation_label()
        self._translation_below.setWordWrap(True)
        title = self._title = QHBoxLayout()
        title.setSpacing(4)
        title.addWidget(self._lemma)
        title.addWidget(self._speak_word)
        title.addSpacing(4)
        title.addWidget(self._translation, 1)
        self._ipa = QLabel()
        self._ipa.setObjectName("ipa")
        self._ipa.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._pos = QLabel()
        self._pos.setObjectName("pos")
        subtitle = QHBoxLayout()
        subtitle.setSpacing(8)
        subtitle.addWidget(self._ipa)
        subtitle.addWidget(self._pos)
        subtitle.addStretch(1)

        self._definition = QLabel()
        self._definition.setObjectName("definition")
        self._definition.setWordWrap(True)
        self._definition.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self._example = QLabel()
        self._example.setObjectName("example")
        self._example.setWordWrap(True)
        self._example.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._speak_example = self._speak_button("speakSmall")
        self._speak_example.clicked.connect(
            lambda: self._speak(self._example_text, self._speak_example))
        self._example_text = ""
        self._example_row = QWidget()
        example_layout = QHBoxLayout(self._example_row)
        example_layout.setContentsMargins(0, 0, 0, 0)
        example_layout.setSpacing(2)
        example_layout.addWidget(self._speak_example, 0, Qt.AlignmentFlag.AlignTop)
        example_layout.addWidget(self._example, 1)

        self._syn_caption = QLabel()
        self._syn_caption.setObjectName("caption")
        self._chips_box = QWidget()
        self._chips = FlowLayout(self._chips_box, spacing=6)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setTextVisible(False)
        self._message = QLabel()
        self._message.setObjectName("message")
        self._message.setWordWrap(True)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 8, 8, 14)
        layout.setSpacing(6)
        layout.addLayout(top)
        body = QVBoxLayout()
        body.setContentsMargins(0, 0, 6, 0)
        body.setSpacing(6)
        body.addLayout(title)
        body.addWidget(self._translation_below)
        body.addLayout(subtitle)
        body.addWidget(self._definition)
        body.addWidget(self._example_row)
        body.addSpacing(2)
        body.addWidget(self._syn_caption)
        body.addWidget(self._chips_box)
        body.addWidget(self._progress)
        body.addWidget(self._message)
        layout.addLayout(body)
        self.setFixedWidth(_WIDTH + 2 * _SHADOW)

    @staticmethod
    def _translation_label() -> QLabel:
        label = QLabel()
        label.setObjectName("translation")
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    @staticmethod
    def _speak_button(name: str) -> QToolButton:
        button = QToolButton()
        button.setObjectName(name)
        button.setText("🔊")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        return button

    # ------------------------------------------------------------- public API
    def set_speaker(self, speaker: Speaker) -> None:
        """Enable the pronunciation buttons."""
        self._speaker = speaker
        self._volume.setValue(round(speaker.volume * 100))
        speaker.volume_changed.connect(self._show_volume)
        self._volume_icon.show()
        self._volume.show()
        speaker.busy_changed.connect(self._on_speech_busy)
        speaker.failed.connect(self._on_speech_failed)

    def show_loading(self, word: str, language_label: str, anchor: QPoint,
                     language_code: str = "") -> None:
        """Show ``word`` with a busy indicator below the global point ``anchor``.

        ``language_code`` is the word's language for pronunciation ("" = unknown).
        """
        self._anchor = anchor
        self._language_code = language_code
        self._language_label = language_label
        self._lang.setText(tr("popup.title", lang=language_label))
        self._set_title(word, "")
        self._ipa.clear()
        self._ipa.hide()
        self._pos.clear()
        self._definition.hide()
        self._example_row.hide()
        self._update_speak_buttons()
        self._set_synonyms(())
        self._progress.show()
        self._set_message(tr("popup.looking_up"))
        self._reposition()
        self.show()
        self.raise_()

    def show_info(self, info: WordInfo) -> None:
        """Fill the card with a dictionary entry."""
        self._progress.hide()
        self._set_message("")
        self._set_title(info.lemma or info.word, info.translation)
        self._ipa.setText(f"/{info.ipa}/" if info.ipa else "")
        self._ipa.setVisible(bool(info.ipa))
        self._pos.setText(info.part_of_speech)
        self._definition.setText(info.definition)
        self._definition.show()
        self._example_text = info.example
        self._example.setText(tr("popup.example", text=info.example) if info.example else "")
        self._example_row.setVisible(bool(info.example))
        self._set_synonyms(info.synonyms)
        self._reposition()

    def show_error(self, message: str) -> None:
        """Show an error instead of the definition."""
        self._progress.hide()
        self._set_message(message, error=True)
        self._reposition()

    # -------------------------------------------------------------- internals
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        """Close the card on a mouse press anywhere outside it."""
        if (event.type() == QEvent.Type.MouseButtonPress and self.isVisible()
                and isinstance(event, QMouseEvent)
                and not self.geometry().contains(event.globalPosition().toPoint())):
            self.hide()
        return False

    def _on_app_state(self, state: Qt.ApplicationState) -> None:
        """Clicks in other programs never reach us: close when the app loses focus."""
        if state != Qt.ApplicationState.ApplicationActive:
            self.hide()

    def hideEvent(self, event: QHideEvent) -> None:
        super().hideEvent(event)
        if self._speaker is not None:
            self._speaker.stop()
        self._on_speech_busy(False)
        self.closed.emit()

    def _set_title(self, lemma: str, translation: str) -> None:
        """Show the word and its translation: on one line if both fit, else on two."""
        self._lemma.setText(lemma)
        text = f"→ {translation}" if translation else ""
        for label in (self._lemma, self._translation):
            label.ensurePolished()  # fonts from the stylesheet, for measuring
        room = _WIDTH - 40 - self._speak_word.sizeHint().width()  # card padding and spacing
        lemma_width = self._lemma.fontMetrics().horizontalAdvance(lemma)
        wrap = lemma_width > room  # only a very long expression wraps, using the full width
        self._lemma.setWordWrap(wrap)
        self._title.setStretchFactor(self._lemma, 1 if wrap else 0)
        self._title.setStretchFactor(self._translation, 0 if wrap else 1)
        inline = lemma_width + self._translation.fontMetrics().horizontalAdvance(text) <= room
        self._translation.setText(text if inline else "")
        self._translation_below.setText("" if inline else text)
        self._translation_below.setVisible(bool(text) and not inline)

    def _update_speak_buttons(self) -> None:
        reason = self._speaker.availability(self._language_code) if self._speaker else "—"
        for button in (self._speak_word, self._speak_example):
            button.setVisible(self._speaker is not None)
            button.setToolTip(reason or (tr("popup.speak_word") if button is self._speak_word
                                         else tr("popup.speak_example")))

    def _speak(self, text: str, button: QToolButton) -> None:
        if self._speaker is None or not text:
            return
        self._set_message("")
        self._speaking = button
        self._speaker.speak(text, self._language_code)
        self._reposition()

    def retranslate(self) -> None:
        """Set every text in the current interface language."""
        self._close.setToolTip(tr("popup.close_tip"))
        for widget in (self._volume_icon, self._volume):
            widget.setToolTip(tr("popup.volume_tip"))
        for label in (self._translation, self._translation_below):
            label.setToolTip(tr("popup.translation_tip"))
        self._syn_caption.setText(tr("popup.synonyms"))
        self._lang.setText(tr("popup.title", lang=self._language_label))
        self._update_speak_buttons()

    def _show_volume(self, volume: float) -> None:
        """Follow volume changes made in the settings window."""
        self._volume.blockSignals(True)
        self._volume.setValue(round(volume * 100))
        self._volume.blockSignals(False)
        self._update_volume_icon(self._volume.value())

    def _update_volume_icon(self, value: int) -> None:
        self._volume_icon.setText("🔇" if value == 0 else "🔈" if value < 50 else "🔊")

    def _on_volume(self, value: int) -> None:
        self._update_volume_icon(value)
        if self._speaker is not None:
            self._speaker.set_volume(value / 100)

    def _on_speech_busy(self, busy: bool) -> None:
        for button in (self._speak_word, self._speak_example):
            button.setText("…" if busy and button is self._speaking else "🔊")

    def _on_speech_failed(self, message: str) -> None:
        if self.isVisible():
            self._set_message(message, error=True)
            self._reposition()

    def _set_synonyms(self, synonyms: tuple[str, ...]) -> None:
        while self._chips.count():
            chip = self._chips.takeAt(0).widget()
            if chip is not None:
                # deleteLater alone would leave the old chip painted until the next loop.
                chip.hide()
                chip.setParent(None)
                chip.deleteLater()
        for synonym in synonyms:
            chip = QLabel(synonym)
            chip.setObjectName("chip")
            chip.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self._chips.addWidget(chip)
        visible = bool(synonyms)
        self._syn_caption.setVisible(visible)
        self._chips_box.setVisible(visible)

    def _set_message(self, message: str, error: bool = False) -> None:
        self._message.setText(message)
        self._message.setVisible(bool(message))
        self._message.setProperty("error", error)
        self._message.style().unpolish(self._message)
        self._message.style().polish(self._message)

    def _reposition(self) -> None:
        """Place the card under the anchor, flipping above it near the screen bottom."""
        layout = self.layout()
        layout.activate()
        height = layout.totalHeightForWidth(self.width())
        self.resize(self.width(), height if height > 0 else self.sizeHint().height())
        screen = QGuiApplication.screenAt(self._anchor) or QGuiApplication.primaryScreen()
        area = screen.availableGeometry()
        x = self._anchor.x() - _SHADOW
        y = self._anchor.y() - (_SHADOW - 4) + 4
        if y + self.height() > area.bottom():
            y = self._anchor.y() - self.height() - 22 + _SHADOW
        x = max(area.left() - _SHADOW, min(x, area.right() - self.width() + _SHADOW))
        y = max(area.top() - _SHADOW, y)
        self.move(x, y)
