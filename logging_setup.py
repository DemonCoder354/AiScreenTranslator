"""Application-wide logging to ``logs/app.log`` in the data directory."""

from __future__ import annotations

import faulthandler
import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import TextIO

from config import data_dir

_crash_file: TextIO | None = None


def setup_logging(console: bool = False) -> None:
    """Configure root logging to a rotating file and optionally to stderr."""
    log_dir = data_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        RotatingFileHandler(log_dir / "app.log", maxBytes=1_000_000, backupCount=3,
                            encoding="utf-8"),
    ]
    if console and sys.stderr is not None:  # pythonw has no stderr
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
    # Native crashes (access violations in Qt or extension modules) bypass logging;
    # faulthandler writes their Python stack here. pythonw has no stderr to fall back on.
    global _crash_file
    _crash_file = open(log_dir / "crash.log", "a", encoding="utf-8")  # noqa: SIM115 - kept open
    faulthandler.enable(_crash_file)
    # Keep HTTP client chatter out of the log.
    for noisy in ("httpx", "httpx2", "httpcore", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
