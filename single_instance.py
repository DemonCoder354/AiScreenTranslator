"""Keeps one running copy: a second launch asks the first one to show its window."""

from __future__ import annotations

import getpass
import logging
import sys

from PySide6.QtCore import QObject, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket

log = logging.getLogger(__name__)

_MESSAGE = b"show"


def _server_name() -> str:
    # Per user, so two Windows accounts on one PC do not see each other's copy.
    return f"ScreenTranslator-{getpass.getuser()}"


def notify_running_instance() -> bool:
    """Ask an already running copy to show itself; True if one answered."""
    socket = QLocalSocket()
    socket.connectToServer(_server_name())
    if not socket.waitForConnected(500):
        return False
    if sys.platform == "win32":
        import ctypes

        # Let the running copy bring its window to the front: Windows only allows
        # that for the process the user just started (this one).
        ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
    socket.write(_MESSAGE)
    socket.flush()
    socket.waitForBytesWritten(500)
    socket.disconnectFromServer()
    return True


class InstanceServer(QObject):
    """Listens for later launches of the program.

    Signals:
        activated(): Another launch asked this copy to show its window.
    """

    activated = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._server = QLocalServer(self)
        self._server.newConnection.connect(self._on_connection)

    def listen(self) -> bool:
        """Start listening; False if it failed (the program still works without it)."""
        name = _server_name()
        QLocalServer.removeServer(name)  # leftover of a crashed copy
        if not self._server.listen(name):
            log.warning("Single-instance server failed: %s", self._server.errorString())
            return False
        return True

    def _on_connection(self) -> None:
        while self._server.hasPendingConnections():
            socket = self._server.nextPendingConnection()
            socket.readyRead.connect(lambda s=socket: self._on_ready_read(s))
            socket.disconnected.connect(socket.deleteLater)

    def _on_ready_read(self, socket: QLocalSocket) -> None:
        if bytes(socket.readAll()).startswith(_MESSAGE):
            log.info("Another launch asked to show the window")
            self.activated.emit()
