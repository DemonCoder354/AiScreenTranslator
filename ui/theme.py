"""Dark theme: color tokens, application palette and shared style helpers."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

# Color tokens
BG = "#1b1c21"          # window background
SURFACE = "#22242b"     # header, buttons
FIELD = "#15161a"       # text areas
BORDER = "#30333c"
BORDER_HOVER = "#454955"
TEXT = "#e7e9ee"
TEXT_DIM = "#a2a7b3"
TEXT_MUTED = "#6f7482"
ACCENT = "#5b8cff"
ACCENT_HOVER = "#7aa2ff"
ACCENT_PRESSED = "#4874e0"
ERROR = "#ff6b6b"
SUCCESS = "#4cd38a"

FONT_FAMILY = "Segoe UI Variable Text, Segoe UI"

MENU_STYLE = f"""
QMenu {{ background: {SURFACE}; color: {TEXT}; border: 1px solid {BORDER};
         border-radius: 8px; padding: 6px; font-family: "{FONT_FAMILY}"; font-size: 13px; }}
QMenu::item {{ padding: 6px 22px 6px 12px; border-radius: 5px; }}
QMenu::item:selected {{ background: #2d3140; }}
QMenu::item:checked {{ color: {ACCENT_HOVER}; font-weight: 600; }}
QMenu::indicator {{ width: 0px; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 5px 8px; }}
"""


def apply_dark_theme(app: QApplication) -> None:
    """Switch the whole application to the Fusion style with a dark palette."""
    app.setStyle("Fusion")
    palette = QPalette()
    colors = {
        QPalette.ColorRole.Window: BG,
        QPalette.ColorRole.WindowText: TEXT,
        QPalette.ColorRole.Base: FIELD,
        QPalette.ColorRole.AlternateBase: SURFACE,
        QPalette.ColorRole.Text: TEXT,
        QPalette.ColorRole.Button: SURFACE,
        QPalette.ColorRole.ButtonText: TEXT,
        QPalette.ColorRole.ToolTipBase: SURFACE,
        QPalette.ColorRole.ToolTipText: TEXT,
        QPalette.ColorRole.Highlight: ACCENT,
        QPalette.ColorRole.HighlightedText: "#ffffff",
        QPalette.ColorRole.PlaceholderText: TEXT_MUTED,
        QPalette.ColorRole.Link: ACCENT_HOVER,
    }
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    for role in (QPalette.ColorRole.WindowText, QPalette.ColorRole.Text,
                 QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(TEXT_MUTED))
    app.setPalette(palette)
    app.setStyleSheet(MENU_STYLE + f"QToolTip {{ background: {SURFACE}; color: {TEXT}; "
                      f"border: 1px solid {BORDER}; padding: 4px 6px; }}")
