"""Dialog for entering the Gemini API key; the key is saved for the current Windows user."""

from __future__ import annotations

import logging
import os
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout,
                               QWidget)

from i18n import tr
from ui import theme as t

log = logging.getLogger(__name__)

KEY_URL = "https://aistudio.google.com/apikey"
_STYLE = f"""
* {{ font-family: "{t.FONT_FAMILY}"; }}
QDialog {{ background: {t.BG}; }}
QLabel {{ color: {t.TEXT}; font-size: 13px; }}
QLabel#note {{ color: {t.TEXT_MUTED}; font-size: 11px; }}
QLabel#error {{ color: {t.ERROR}; font-size: 12px; }}
QLineEdit {{ background: {t.FIELD}; color: {t.TEXT}; border: 1px solid {t.BORDER};
             border-radius: 8px; padding: 7px 9px; font-size: 13px; }}
QLineEdit:focus {{ border-color: {t.ACCENT}; }}
QPushButton {{ background: {t.SURFACE}; color: {t.TEXT}; border: 1px solid {t.BORDER};
               border-radius: 8px; padding: 7px 16px; font-size: 12px; font-weight: 600; }}
QPushButton:hover {{ border-color: {t.BORDER_HOVER}; }}
QPushButton#primary {{ background: {t.ACCENT}; color: white; border-color: {t.ACCENT}; }}
QPushButton#primary:hover {{ background: {t.ACCENT_HOVER}; border-color: {t.ACCENT_HOVER}; }}
"""


def save_api_key(variable: str, key: str) -> None:
    """Store ``key`` in the user's environment variable ``variable`` (like ``setx``).

    The current process gets it at once too, so no restart is needed.

    Raises:
        OSError: If the registry cannot be written.
    """
    if sys.platform == "win32":
        import winreg  # Windows only

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0,
                            winreg.KEY_SET_VALUE) as reg:
            winreg.SetValueEx(reg, variable, 0, winreg.REG_SZ, key)
    os.environ[variable] = key
    log.info("Gemini API key saved to %s", variable)


class KeyDialog(QDialog):
    """Explains how to get a free key and takes it from the user."""

    def __init__(self, variable: str, current: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.WindowStaysOnTopHint)
        self.setWindowTitle(tr("key.title"))
        self.setStyleSheet(_STYLE)
        self.setMinimumWidth(460)
        self._variable = variable

        intro = QLabel(tr("key.intro", url=KEY_URL, color=t.ACCENT_HOVER))
        intro.setOpenExternalLinks(True)
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)
        self._edit = QLineEdit(current)
        self._edit.setPlaceholderText(tr("key.placeholder"))
        self._edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._edit.textChanged.connect(lambda: self._error.hide())
        show = QPushButton(tr("key.show"))
        show.setCheckable(True)
        show.toggled.connect(lambda on: self._edit.setEchoMode(
            QLineEdit.EchoMode.Normal if on else QLineEdit.EchoMode.Password))
        row = QHBoxLayout()
        row.addWidget(self._edit, 1)
        row.addWidget(show)
        self._error = QLabel()
        self._error.setObjectName("error")
        self._error.hide()
        note = QLabel(tr("key.note", variable=variable))
        note.setObjectName("note")
        note.setWordWrap(True)

        save = QPushButton(tr("key.save"))
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self._save)
        cancel = QPushButton(tr("key.cancel"))
        cancel.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(save)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(12)
        layout.addWidget(intro)
        layout.addLayout(row)
        layout.addWidget(self._error)
        layout.addWidget(note)
        layout.addLayout(buttons)

    def _save(self) -> None:
        key = "".join(self._edit.text().split())  # pasted keys often carry spaces or newlines
        if len(key) < 20 or not key.isascii():
            self._show_error(tr("key.invalid"))
            return
        try:
            save_api_key(self._variable, key)
        except OSError as exc:
            log.error("Cannot save the API key: %s", exc)
            self._show_error(tr("key.save_failed", error=exc))
            return
        self.accept()

    def _show_error(self, message: str) -> None:
        self._error.setText(message)
        self._error.show()
