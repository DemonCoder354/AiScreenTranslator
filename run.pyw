"""Console-less launcher: run with ``pythonw.exe run.pyw`` (or double-click)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import main  # noqa: E402

main()
