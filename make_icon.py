"""Save the tray icon as ``icon.ico`` for desktop and Start-menu shortcuts."""

from __future__ import annotations

import sys

from PySide6.QtCore import QSize
from PySide6.QtGui import QGuiApplication

from config import app_dir
from main import _make_icon


def main() -> None:
    """Render the icon and write ``icon.ico`` next to the program."""
    app = QGuiApplication(sys.argv)  # noqa: F841 - required for QPixmap
    path = app_dir() / "icon.ico"
    pixmap = _make_icon(256).pixmap(QSize(256, 256))
    if not pixmap.save(str(path), "ICO"):
        raise SystemExit(f"Cannot write {path}")
    print(f"Icon written to {path}")


if __name__ == "__main__":
    main()
