"""ScreenTranslator entry point: tray icon, global hotkey and the capture -> translate flow."""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Callable
from types import TracebackType

from PIL import Image
from PySide6.QtCore import QObject, QPoint, QRect, Qt, QTimer, QUrl, Slot
from PySide6.QtGui import (QAction, QActionGroup, QColor, QCursor, QDesktopServices, QFont,
                           QGuiApplication, QIcon, QLinearGradient, QPainter, QPixmap)
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from backends import read_api_key
from capture import Capture, CaptureController
from config import (PROVIDER_GEMINI, PROVIDER_LOCAL, AppConfig, data_dir, load_config,
                    save_config)
from hotkey import GlobalHotkey
from i18n import language, set_language, tr
from languages import TOP_CODES, get_language, sorted_languages
from logging_setup import setup_logging
from single_instance import InstanceServer, notify_running_instance
from speech import Speaker
from translator import WordInfo
from ui.key_dialog import KeyDialog
from ui.result_window import ResultWindow
from ui.settings_dialog import SettingsDialog
from ui.theme import apply_dark_theme
from worker import PipelineController

log = logging.getLogger("main")


def _make_icon(size: int = 64) -> QIcon:
    """Draw the tray icon (designed on a 64 px grid) so the app needs no image files."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.scale(size / 64, size / 64)
    gradient = QLinearGradient(0, 0, 64, 64)
    gradient.setColorAt(0.0, QColor("#6f9bff"))
    gradient.setColorAt(1.0, QColor("#8a5cff"))
    painter.setBrush(gradient)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRect(2, 2, 60, 60), 16, 16)
    font = QFont("Segoe UI", 1, QFont.Weight.Bold)
    font.setPixelSize(30)
    painter.setFont(font)
    painter.setPen(QColor("white"))
    painter.drawText(QRect(6, 4, 34, 40), Qt.AlignmentFlag.AlignCenter, "A")
    painter.setPen(QColor(255, 255, 255, 190))
    font.setPixelSize(24)
    painter.setFont(font)
    painter.drawText(QRect(26, 24, 34, 36), Qt.AlignmentFlag.AlignCenter, "Я")
    painter.end()
    return QIcon(pixmap)


class ScreenTranslatorApp(QObject):
    """Wires together the hotkey, capture overlay, background pipeline and result window.

    Being a QObject living in the GUI thread is essential: worker signals are then
    delivered through the event queue instead of running UI code in the worker thread.
    """

    def __init__(self, app: QApplication, config: AppConfig) -> None:
        super().__init__()
        self._app = app
        self._config = config
        self._current_request = 0
        self._current_define = 0
        self._request_target = ""
        self._last_image: Image.Image | None = None  # kept to re-run OCR in another language
        self.stopped_cleanly = True

        self._window = ResultWindow()
        self._window.source_changed.connect(self._on_window_source_changed)
        self._window.target_changed.connect(self._on_window_target_changed)
        self._window.translate_requested.connect(self._on_manual_translate)
        self._window.word_clicked.connect(self._on_word_clicked)
        self._window.quit_requested.connect(self._app.quit)
        self._window.settings_requested.connect(self.show_settings)
        self._settings: SettingsDialog | None = None
        self._window.word_popup.closed.connect(self._on_word_popup_closed)
        self._speaker = Speaker(config, self)
        self._window.word_popup.set_speaker(self._speaker)
        self._capture = CaptureController()
        self._capture.captured.connect(self._on_captured)
        self._pipeline = PipelineController(config)
        worker = self._pipeline.worker
        worker.recognized.connect(self._on_recognized)
        worker.translated.connect(self._on_translated)
        worker.failed.connect(self._on_failed)
        worker.defined.connect(self._on_defined)
        worker.define_failed.connect(self._on_define_failed)
        self._pipeline.idioms.found.connect(self._on_idioms_found)
        self._current_idioms = 0
        self._idiom_text = ""

        self._icon = _make_icon()
        app.setWindowIcon(self._icon)
        self._tray = QSystemTrayIcon(self._icon)
        self._tray.setContextMenu(self._build_menu())
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

        self._hotkey = GlobalHotkey()
        self._hotkey.activated.connect(self.start_capture)
        self._manual_hotkey = GlobalHotkey()
        self._manual_hotkey.activated.connect(self.start_manual)
        self._register_hotkeys()
        self._update_tooltip()
        app.aboutToQuit.connect(self._shutdown)

    # -------------------------------------------------------------- tray/menu
    def _build_menu(self) -> QMenu:
        menu = QMenu()
        self._capture_action = QAction(tr("menu.capture"), menu)
        self._capture_action.triggered.connect(self.start_capture)
        menu.addAction(self._capture_action)
        self._manual_action = QAction(tr("menu.manual"), menu)
        self._manual_action.triggered.connect(self.start_manual)
        menu.addAction(self._manual_action)

        provider_menu = menu.addMenu(tr("menu.provider"))
        provider_group = QActionGroup(provider_menu)
        provider_group.setExclusive(True)
        for code, text in ((PROVIDER_LOCAL, tr("menu.provider_local")),
                           (PROVIDER_GEMINI, tr("menu.provider_gemini"))):
            action = QAction(text, provider_menu, checkable=True)
            action.setChecked(code == self._config.provider)
            action.triggered.connect(lambda _=False, c=code: self._set_provider(c))
            provider_group.addAction(action)
            provider_menu.addAction(action)
        menu.addSeparator()

        self._add_language_menu(menu, tr("menu.source"), self._config.source_language,
                                self._set_default_source, with_auto=True)
        self._add_language_menu(menu, tr("menu.target"), self._config.target_language,
                                self._set_default_target, with_auto=False)

        menu.addSeparator()
        settings_action = QAction(tr("menu.settings"), menu)
        settings_action.triggered.connect(self.show_settings)
        menu.addAction(settings_action)
        key_action = QAction(tr("menu.api_key"), menu)
        key_action.triggered.connect(self.ask_api_key)
        menu.addAction(key_action)
        folder_action = QAction(tr("menu.data_folder"), menu)
        folder_action.triggered.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir()))))
        menu.addAction(folder_action)
        menu.addSeparator()
        quit_action = QAction(tr("menu.quit"), menu)
        quit_action.triggered.connect(self._app.quit)
        menu.addAction(quit_action)
        self._menu = menu  # keep a reference: the tray does not own the menu
        return menu

    @staticmethod
    def _add_language_menu(menu: QMenu, title: str, current: str,
                           choose: Callable[[str], None], with_auto: bool) -> None:
        """Language submenu: the most spoken languages, then all of them by first letter."""
        submenu = menu.addMenu(title)
        group = QActionGroup(submenu)
        group.setExclusive(True)
        ui = language()

        def add(target: QMenu, code: str, text: str) -> None:
            action = QAction(text, target, checkable=True)
            action.setChecked(code == current)
            action.triggered.connect(lambda _=False, c=code: choose(c))
            group.addAction(action)
            target.addAction(action)

        if with_auto:
            add(submenu, "", tr("lang.auto"))
            submenu.addSeparator()
        if current and current not in TOP_CODES:
            # The chosen language stays in sight even when it is not among the top ones.
            add(submenu, current, get_language(current).display_name(ui))
            submenu.addSeparator()
        submenu.addSection(tr("lang.top"))
        for code in TOP_CODES:
            add(submenu, code, get_language(code).display_name(ui))
        submenu.addSeparator()
        everything = submenu.addMenu(tr("menu.all_languages"))
        letters: dict[str, QMenu] = {}
        for lang in sorted_languages(ui):
            letter = lang.name(ui)[0].upper()
            if letter not in letters:
                letters[letter] = everything.addMenu(letter)
            add(letters[letter], lang.code, lang.display_name(ui))

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.start_capture()

    def _set_provider(self, provider: str) -> None:
        if provider == self._config.provider:
            return
        self._config.provider = provider
        save_config(self._config)
        self._pipeline.reload_translator()
        self._update_tooltip()
        log.info("Provider set to %s", provider)

    def ask_api_key(self) -> None:
        """Let the user enter or replace the Gemini key, then use it right away."""
        variable = self._config.gemini_api_key_env
        dialog = KeyDialog(variable, read_api_key(variable))
        dialog.activateWindow()
        if dialog.exec():
            self._pipeline.reload_translator()
            self._notify(tr("notify.key_saved"))

    def show_settings(self) -> None:
        """Open the settings window (or bring it forward)."""
        if self._settings is None:
            self._settings = SettingsDialog(self._speaker, self._config)
            self._settings.language_changed.connect(self._set_ui_language)
            self._settings.models_changed.connect(self._set_models)
            self._settings.api_key_requested.connect(self.ask_api_key)
        self._settings.show()
        self._settings.raise_()
        self._settings.activateWindow()

    def _set_models(self, field: str, models: list[str]) -> None:
        """Use the new model order of one step from the next request on."""
        setattr(self._config, field, tuple(models))
        save_config(self._config)
        self._pipeline.reload_translator()
        log.info("%s set to %s", field, ", ".join(models))

    def _set_ui_language(self, code: str) -> None:
        """Switch the interface language at once, without a restart."""
        self._config.ui_language = code
        save_config(self._config)
        set_language(code)
        old_menu = self._menu
        self._tray.setContextMenu(self._build_menu())
        old_menu.deleteLater()
        self._update_tooltip()
        self._window.retranslate()
        if self._settings is not None:
            self._settings.retranslate()
        log.info("Interface language set to %s", code)

    def check_api_key(self) -> None:
        """At startup in cloud mode: without a key nothing works, so ask for it."""
        if (self._config.provider == PROVIDER_GEMINI
                and not read_api_key(self._config.gemini_api_key_env)):
            self.ask_api_key()

    def _set_default_source(self, code: str) -> None:
        self._config.source_language = code
        save_config(self._config)
        log.info("Default source language set to %s", code or "auto")

    def _set_default_target(self, code: str) -> None:
        self._config.target_language = code
        save_config(self._config)
        self._update_tooltip()
        log.info("Default target language set to %s", code)

    def _update_tooltip(self) -> None:
        capture_key = self._hotkey.hotkey_text
        manual_key = self._manual_hotkey.hotkey_text
        target = get_language(self._config.target_language).label
        keys = ", ".join(k for k in (capture_key, manual_key) if k) or tr("tray.no_keys")
        engine = "Gemini" if self._config.provider == PROVIDER_GEMINI else "LM Studio"
        self._tray.setToolTip(tr("tray.tooltip", keys=keys, target=target, engine=engine))
        self._capture_action.setText(tr("menu.capture_key", key=capture_key) if capture_key
                                     else tr("menu.capture"))
        self._manual_action.setText(tr("menu.manual_key", key=manual_key) if manual_key
                                    else tr("menu.manual"))

    def _register_hotkeys(self) -> None:
        errors: list[str] = []
        for hotkey, text in ((self._hotkey, self._config.hotkey),
                             (self._manual_hotkey, self._config.manual_hotkey)):
            try:
                hotkey.register(text)
            except (ValueError, OSError) as exc:
                log.error("Hotkey registration failed: %s", exc)
                errors.append(str(exc))
        if errors:
            self._notify(tr("notify.hotkey_failed", errors="\n".join(errors)), error=True)
        else:
            self._notify(tr("notify.running", capture=self._config.hotkey,
                            manual=self._config.manual_hotkey))

    def _notify(self, message: str, error: bool = False) -> None:
        icon = (QSystemTrayIcon.MessageIcon.Warning if error
                else QSystemTrayIcon.MessageIcon.Information)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray.showMessage("ScreenTranslator", message, icon, 5000)
        elif error:
            QMessageBox.warning(None, "ScreenTranslator", message)

    # ------------------------------------------------------------------- flow
    def start_capture(self) -> None:
        """Start a new screen-area selection (hiding the previous result first)."""
        if self._capture.active:
            return
        if self._window.isVisible():
            self._window.hide()
            QTimer.singleShot(150, self._capture.start)  # let the window vanish from screen
        else:
            self._capture.start()

    def start_manual(self) -> None:
        """Open the result window for typed or pasted text."""
        if self._capture.active:
            return
        self._current_request = 0  # drop results of any capture still in progress
        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        self._window.start_manual(screen, self._config.target_language,
                                  self._config.source_language)

    def show_manual_window(self) -> None:
        """Bring the window forward, or open manual input if it is hidden.

        Used at startup and when the program is launched again, so a double-click
        on the shortcut always shows that the program is running.
        """
        if self._window.isVisible():
            self._window.raise_()
            self._window.activateWindow()
        else:
            self.start_manual()

    def _on_manual_translate(self, text: str) -> None:
        self._request_target = self._window.target_code
        self._current_request = self._pipeline.process_text(text, self._request_target,
                                                            self._window.source_choice)

    def _on_word_clicked(self, word: str, context: str, language: str, anchor: QPoint) -> None:
        label = get_language(language).label if language else "?"
        self._window.word_popup.show_loading(word, label, anchor, language)
        self._current_define = self._pipeline.define(word, context, language,
                                                     self._window.target_code)

    def _on_word_popup_closed(self) -> None:
        self._current_define = 0
        self._pipeline.cancel_define()

    @Slot(int, object)
    def _on_defined(self, request_id: int, info: WordInfo) -> None:
        if request_id == self._current_define and self._window.word_popup.isVisible():
            self._window.word_popup.show_info(info)

    @Slot(int, str)
    def _on_define_failed(self, request_id: int, message: str) -> None:
        if request_id == self._current_define and self._window.word_popup.isVisible():
            self._window.word_popup.show_error(message)

    def _on_captured(self, capture: Capture) -> None:
        target = self._config.target_language
        source = self._config.source_language
        self._request_target = target
        self._last_image = capture.image
        self._current_request = self._pipeline.process(capture.image, target, source)
        self._window.start(capture.rect, capture.screen, target, source)

    @Slot(int, str, str, float)
    def _on_recognized(self, request_id: int, text: str, source: str, _confidence: float) -> None:
        if request_id != self._current_request:
            return
        if self._window.manual:
            self._window.set_source(source)  # keep the text exactly as typed
        else:
            self._window.set_original(text, source)
        self._find_idioms(source)
        if self._window.target_code != self._request_target:
            # The user switched language while OCR was running.
            self._translate_again(self._window.target_code)
        else:
            self._window.set_busy()

    def _find_idioms(self, source: str) -> None:
        """Look for idioms in the shown original; only in cloud mode, where it runs in
        parallel: a local model would make the next lookups wait several seconds."""
        text = self._window.original_text.strip()
        if self._config.provider != PROVIDER_GEMINI or len(text.split()) < 2:
            self._current_idioms = 0
            return
        self._idiom_text = text
        self._current_idioms = self._pipeline.find_idioms(text, source)

    @Slot(int, list)
    def _on_idioms_found(self, request_id: int, idioms: list[str]) -> None:
        # Manual text may have been edited meanwhile: then the positions would be wrong.
        if (request_id == self._current_idioms
                and self._window.original_text.strip() == self._idiom_text):
            self._window.set_idioms(idioms)

    @Slot(int, str, str)
    def _on_translated(self, request_id: int, text: str, source: str) -> None:
        if request_id == self._current_request:
            self._window.set_found_source(source)
            self._window.set_translation(text)

    @Slot(int, str)
    def _on_failed(self, request_id: int, message: str) -> None:
        if request_id == self._current_request:
            self._window.set_error(message)

    def _on_window_target_changed(self, code: str) -> None:
        if not self._window.original_text.strip():
            return
        if self._window.manual:
            # The text may have been edited since the last run: detect its language again.
            self._window.set_busy()
            self._request_target = code
            self._current_request = self._pipeline.process_text(
                self._window.original_text.strip(), code, self._window.source_choice)
        else:
            self._translate_again(code)

    def _on_window_source_changed(self, code: str) -> None:
        """Redo the request with the source language the user picked ("" = auto)."""
        target = self._window.target_code
        if self._window.manual:
            text = self._window.original_text.strip()
            if not text:
                return
            self._window.set_busy()
            self._request_target = target
            self._current_request = self._pipeline.process_text(text, target, code)
        elif self._last_image is not None:
            # OCR quality depends on the language, so recognize the image again.
            self._window.set_busy(tr("status.recognizing"))
            self._request_target = target
            self._current_request = self._pipeline.process(self._last_image, target, code)

    def _translate_again(self, target: str) -> None:
        self._request_target = target
        self._current_request = self._pipeline.translate(
            self._window.original_text, self._window.source_code, target)
        self._window.set_busy()

    def _shutdown(self) -> None:
        log.info("Shutting down")
        self._hotkey.unregister()
        self._manual_hotkey.unregister()
        self._tray.hide()
        self.stopped_cleanly = self._pipeline.shutdown()


def _log_uncaught(exc_type: type[BaseException], exc: BaseException,
                  tb: TracebackType | None) -> None:
    """Log exceptions escaping Qt slots instead of losing them (no console under pythonw)."""
    logging.getLogger("uncaught").critical("Unhandled exception", exc_info=(exc_type, exc, tb))


def main() -> int:
    """Start the tray application.

    Without ``--tray`` the manual-input window opens right away, so the user sees
    that the program started. A second launch only shows the running copy's window.
    """
    setup_logging(console=sys.stderr is not None)
    sys.excepthook = _log_uncaught
    app = QApplication(sys.argv)
    if notify_running_instance():
        log.info("Already running: asked the running copy to show its window")
        return 0
    log.info("Starting ScreenTranslator")
    app.setApplicationName("ScreenTranslator")
    app.setQuitOnLastWindowClosed(False)
    apply_dark_theme(app)
    config = load_config()
    set_language(config.ui_language)
    instance = ScreenTranslatorApp(app, config)
    server = InstanceServer(app)
    server.activated.connect(instance.show_manual_window)
    server.listen()
    if "--tray" not in sys.argv[1:]:
        QTimer.singleShot(0, instance.show_manual_window)
    QTimer.singleShot(300, instance.check_api_key)
    code = app.exec()
    if not getattr(instance, "stopped_cleanly", True):
        # A translation request still blocks the worker thread; don't wait for it.
        logging.shutdown()
        os._exit(code)
    return code


if __name__ == "__main__":
    sys.exit(main())
