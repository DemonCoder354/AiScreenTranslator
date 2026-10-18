"""Global hotkey via Win32 ``RegisterHotKey`` delivered through Qt's native event filter."""

from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray, QCoreApplication, QObject, Signal

from i18n import tr

log = logging.getLogger(__name__)

WM_HOTKEY = 0x0312
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000

_MODIFIERS: dict[str, int] = {
    "ctrl": MOD_CONTROL, "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN, "meta": MOD_WIN,
}
_NAMED_KEYS: dict[str, int] = {
    "space": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09, "esc": 0x1B, "escape": 0x1B,
    "insert": 0x2D, "ins": 0x2D, "delete": 0x2E, "del": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22, "pause": 0x13, "printscreen": 0x2C, "print": 0x2C,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "`": 0xC0, "-": 0xBD, "=": 0xBB, "[": 0xDB, "]": 0xDD, ";": 0xBA, "'": 0xDE,
    ",": 0xBC, ".": 0xBE, "/": 0xBF, "\\": 0xDC,
}
_FIRST_HOTKEY_ID = 0x5354  # arbitrary, "ST"; each GlobalHotkey takes the next id
_next_id = _FIRST_HOTKEY_ID

_user32 = ctypes.windll.user32
_user32.RegisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT)
_user32.RegisterHotKey.restype = wintypes.BOOL
_user32.UnregisterHotKey.argtypes = (wintypes.HWND, ctypes.c_int)
_user32.UnregisterHotKey.restype = wintypes.BOOL


def parse_hotkey(text: str) -> tuple[int, int]:
    """Parse a hotkey such as ``"Ctrl+Alt+T"`` into Win32 ``(modifiers, virtual_key)``.

    Raises:
        ValueError: If the string has no key, several keys or an unknown name.
    """
    modifiers = 0
    vk: int | None = None
    parts = [p.strip() for p in text.split("+")]
    if text.strip().endswith("++"):  # "Ctrl++" means the plus key
        parts = parts[:-2] + ["="]
    for part in parts:
        name = part.lower()
        if not name:
            raise ValueError(tr("hk.empty_part", text=repr(text)))
        if name in _MODIFIERS:
            modifiers |= _MODIFIERS[name]
            continue
        if vk is not None:
            raise ValueError(tr("hk.many_keys", text=repr(text)))
        if len(name) == 1 and name.isascii() and name.isalnum():
            vk = ord(name.upper())
        elif name[0] == "f" and name[1:].isdigit() and 1 <= int(name[1:]) <= 24:
            vk = 0x70 + int(name[1:]) - 1
        elif name in _NAMED_KEYS:
            vk = _NAMED_KEYS[name]
        else:
            raise ValueError(tr("hk.unknown", part=repr(part), text=repr(text)))
    if vk is None:
        raise ValueError(tr("hk.no_main", text=repr(text)))
    return modifiers, vk


class _Filter(QAbstractNativeEventFilter):
    """Forwards ``WM_HOTKEY`` thread messages with one hotkey id to a callback."""

    def __init__(self, hotkey_id: int, callback) -> None:  # noqa: ANN001 - plain callable
        super().__init__()
        self._id = hotkey_id
        self._callback = callback

    def nativeEventFilter(self, event_type: QByteArray | bytes, message: int) -> tuple[bool, int]:
        if bytes(event_type) == b"windows_generic_MSG":
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY and msg.wParam == self._id:
                self._callback()
                return True, 0
        return False, 0


class GlobalHotkey(QObject):
    """A system-wide hotkey that emits :attr:`activated` when pressed.

    Must be created and used in the GUI thread after ``QApplication`` exists.
    """

    activated = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        global _next_id
        self._id = _next_id
        _next_id += 1
        self._filter = _Filter(self._id, self.activated.emit)
        QCoreApplication.instance().installNativeEventFilter(self._filter)
        self._registered = False
        self.hotkey_text = ""

    def register(self, hotkey: str) -> None:
        """Register ``hotkey``, replacing any previously registered one.

        Raises:
            ValueError: If the hotkey cannot be parsed.
            OSError: If Windows refuses the hotkey (usually taken by another program).
        """
        modifiers, vk = parse_hotkey(hotkey)
        self.unregister()
        if not _user32.RegisterHotKey(None, self._id, modifiers | MOD_NOREPEAT, vk):
            raise OSError(tr("hk.taken", hotkey=hotkey))
        self._registered = True
        self.hotkey_text = hotkey
        log.info("Registered hotkey %s", hotkey)

    def unregister(self) -> None:
        """Release the hotkey if registered."""
        if self._registered:
            _user32.UnregisterHotKey(None, self._id)
            self._registered = False
