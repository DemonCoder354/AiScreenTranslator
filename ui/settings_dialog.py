"""Settings window: volume, interface language, Gemini API key and the models of each step."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QSlider, QTabWidget, QVBoxLayout, QWidget)

from config import AppConfig
from i18n import UI_LANGUAGES, language, tr
from speech import Speaker
from ui import theme as t
from ui.models_editor import ModelsEditor

_STYLE = f"""
* {{ font-family: "{t.FONT_FAMILY}"; }}
QDialog {{ background: {t.BG}; }}
QLabel {{ color: {t.TEXT}; font-size: 13px; }}
QLabel#note {{ color: {t.TEXT_MUTED}; font-size: 11px; }}
QLabel#value {{ color: {t.TEXT_DIM}; font-size: 12px; min-width: 38px; }}
QComboBox {{ background: {t.SURFACE}; color: {t.TEXT}; border: 1px solid {t.BORDER};
             border-radius: 7px; padding: 5px 10px; font-size: 12px; min-width: 150px; }}
QComboBox:hover {{ border-color: {t.BORDER_HOVER}; }}
QComboBox QAbstractItemView {{ background: {t.SURFACE}; color: {t.TEXT};
                               border: 1px solid {t.BORDER}; selection-background-color: #2d3140;
                               outline: none; padding: 4px; }}
QSlider::groove:horizontal {{ height: 4px; background: {t.BORDER_HOVER}; border-radius: 2px; }}
QSlider::sub-page:horizontal {{ background: {t.ACCENT}; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {t.TEXT}; width: 14px; height: 14px; margin: -5px 0;
                              border-radius: 7px; }}
QSlider::handle:horizontal:hover {{ background: white; }}
QPushButton {{ background: {t.SURFACE}; color: {t.TEXT}; border: 1px solid {t.BORDER};
               border-radius: 8px; padding: 7px 16px; font-size: 12px; font-weight: 600; }}
QPushButton:hover {{ border-color: {t.BORDER_HOVER}; }}
QPushButton#small {{ padding: 4px 0; min-width: 30px; font-size: 13px; }}
QPushButton:disabled {{ color: {t.TEXT_MUTED}; }}
QTabWidget::pane {{ border: none; border-top: 1px solid {t.BORDER}; }}
QTabBar::tab {{ background: transparent; color: {t.TEXT_DIM}; padding: 7px 16px; font-size: 12px;
                font-weight: 600; border: none; border-bottom: 2px solid transparent; }}
QTabBar::tab:selected {{ color: {t.TEXT}; border-bottom-color: {t.ACCENT}; }}
QTabBar::tab:hover {{ color: {t.TEXT}; }}
QListWidget {{ background: {t.FIELD}; color: {t.TEXT}; border: 1px solid {t.BORDER};
               border-radius: 8px; padding: 4px; font-size: 13px; outline: none; }}
QListWidget::item {{ padding: 6px 8px; border-radius: 5px; }}
QListWidget::item:selected {{ background: #2d3140; color: {t.TEXT}; }}
QComboBox:editable {{ background: {t.FIELD}; }}
QPushButton#primary {{ background: {t.ACCENT}; color: white; border-color: {t.ACCENT}; }}
QPushButton#primary:hover {{ background: {t.ACCENT_HOVER}; border-color: {t.ACCENT_HOVER}; }}
"""


class SettingsDialog(QDialog):
    """Changes apply at once; the window only has a Close button.

    Signals:
        language_changed(str): The user picked another interface language.
        api_key_requested(): The user wants to enter or replace the Gemini key.
        models_changed(str, list): (config field, model ids in order) for one step.
    """

    language_changed = Signal(str)
    api_key_requested = Signal()
    models_changed = Signal(str, list)

    def __init__(self, speaker: Speaker, config: AppConfig,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.WindowStaysOnTopHint)
        self.setStyleSheet(_STYLE)
        self.setMinimumWidth(480)
        self._speaker = speaker

        self._volume_label = QLabel()
        self._volume = QSlider(Qt.Orientation.Horizontal)
        self._volume.setRange(0, 100)
        self._volume.setValue(round(speaker.volume * 100))
        self._volume.setCursor(Qt.CursorShape.PointingHandCursor)
        self._volume_value = QLabel()
        self._volume_value.setObjectName("value")
        self._volume_value.setAlignment(Qt.AlignmentFlag.AlignRight
                                        | Qt.AlignmentFlag.AlignVCenter)
        self._volume.valueChanged.connect(self._on_volume)
        speaker.volume_changed.connect(self._show_volume)

        self._language_label = QLabel()
        self._language = QComboBox()
        self._language.setCursor(Qt.CursorShape.PointingHandCursor)
        for code, name in UI_LANGUAGES.items():
            self._language.addItem(name, code)
        self._language.setCurrentIndex(max(0, self._language.findData(language())))
        self._language.currentIndexChanged.connect(
            lambda: self.language_changed.emit(self._language.currentData()))

        self._key = QPushButton()
        self._key.clicked.connect(self.api_key_requested)
        self._close = QPushButton()
        self._close.setObjectName("primary")
        self._close.setDefault(True)
        self._close.clicked.connect(self.accept)

        volume_row = QHBoxLayout()
        volume_row.setSpacing(8)
        volume_row.addWidget(self._volume, 1)
        volume_row.addWidget(self._volume_value)
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(14)
        grid.addWidget(self._volume_label, 0, 0)
        grid.addLayout(volume_row, 0, 1)
        grid.addWidget(self._language_label, 1, 0)
        grid.addWidget(self._language, 1, 1, Qt.AlignmentFlag.AlignLeft)
        grid.setColumnStretch(1, 1)
        general = QWidget()
        general_layout = QVBoxLayout(general)
        general_layout.setContentsMargins(0, 14, 0, 0)
        general_layout.setSpacing(18)
        general_layout.addLayout(grid)
        general_layout.addWidget(self._key, 0, Qt.AlignmentFlag.AlignLeft)
        general_layout.addStretch(1)
        self._models = ModelsEditor(config)
        self._models.models_changed.connect(self.models_changed)
        self._tabs = QTabWidget()
        self._tabs.addTab(general, "")
        self._tabs.addTab(self._models, "")
        self._tabs.currentChanged.connect(self._on_tab)
        self._models_loaded = False

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(self._close)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 14, 20, 16)
        layout.setSpacing(14)
        layout.addWidget(self._tabs, 1)
        layout.addLayout(buttons)
        self.resize(520, 460)
        self._show_volume(speaker.volume)
        self.retranslate()

    def retranslate(self) -> None:
        """Set every text in the current interface language."""
        self.setWindowTitle(tr("settings.title"))
        self._volume_label.setText(tr("settings.volume"))
        self._language_label.setText(tr("settings.language"))
        self._key.setText(tr("settings.api_key"))
        self._close.setText(tr("settings.close"))
        self._tabs.setTabText(0, tr("settings.tab_general"))
        self._tabs.setTabText(1, tr("settings.tab_models"))
        self._models.retranslate()

    def _on_tab(self, index: int) -> None:
        """Load the AI Studio model list the first time the Models tab opens."""
        if self._tabs.widget(index) is self._models and not self._models_loaded:
            self._models_loaded = True
            self._models.load_catalog()

    def _on_volume(self, value: int) -> None:
        self._speaker.set_volume(value / 100)

    def _show_volume(self, volume: float) -> None:
        """Follow volume changes, also those made with the slider in the dictionary card."""
        self._volume.blockSignals(True)
        self._volume.setValue(round(volume * 100))
        self._volume.blockSignals(False)
        self._volume_value.setText(f"{round(volume * 100)}%")
