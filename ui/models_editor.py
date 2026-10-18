"""Settings tab: which Gemini models each step uses, and in what order."""

from __future__ import annotations

import threading

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QAbstractItemView, QComboBox, QHBoxLayout, QLabel, QListWidget,
                               QPushButton, QVBoxLayout, QWidget)

from backends import list_gemini_models, read_api_key
from config import AppConfig
from i18n import tr
from translator import TranslationError

# (config field, i18n key of the step name)
STEPS = (("gemini_text_models", "models.step_text"),
         ("gemini_dictionary_models", "models.step_dictionary"),
         ("gemini_vision_models", "models.step_vision"))


class ModelsEditor(QWidget):
    """Ordered model list per step; models come from AI Studio or are typed in.

    Every change is reported at once through :attr:`models_changed`.

    Signals:
        models_changed(str, list): (config field, new model ids in order).
    """

    models_changed = Signal(str, list)
    _catalog_loaded = Signal(list, str)  # (model ids, error) from the loader thread

    def __init__(self, config: AppConfig, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._catalog: list[str] = []
        self._status_text: tuple[str, dict[str, object]] | None = None  # (i18n key, values)
        self._loading = False
        self._catalog_loaded.connect(self._on_catalog)

        self._step_label = QLabel()
        self._step = QComboBox()
        self._step.setCursor(Qt.CursorShape.PointingHandCursor)
        for field, _key in STEPS:
            self._step.addItem("", field)
        self._step.currentIndexChanged.connect(self._show_step)
        self._hint = QLabel()
        self._hint.setObjectName("note")
        self._hint.setWordWrap(True)

        self._list = QListWidget()
        self._list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self._list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._list.model().rowsMoved.connect(self._commit)
        self._list.currentRowChanged.connect(self._update_buttons)
        self._up = self._small_button("↑", lambda: self._move(-1))
        self._down = self._small_button("↓", lambda: self._move(1))
        self._remove = self._small_button("✕", self._remove_current)
        side = QVBoxLayout()
        side.setSpacing(6)
        for button in (self._up, self._down, self._remove):
            side.addWidget(button)
        side.addStretch(1)
        list_row = QHBoxLayout()
        list_row.addWidget(self._list, 1)
        list_row.addLayout(side)

        self._new = QComboBox()
        self._new.setEditable(True)
        self._new.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self._new.lineEdit().returnPressed.connect(self._add)
        self._add_button = QPushButton()
        self._add_button.clicked.connect(self._add)
        add_row = QHBoxLayout()
        add_row.addWidget(self._new, 1)
        add_row.addWidget(self._add_button)

        self._status = QLabel()
        self._status.setObjectName("note")
        self._status.setWordWrap(True)
        self._refresh = QPushButton()
        self._refresh.clicked.connect(self.load_catalog)
        self._reset = QPushButton()
        self._reset.clicked.connect(self._reset_step)
        bottom = QHBoxLayout()
        bottom.addWidget(self._refresh)
        bottom.addWidget(self._reset)
        bottom.addStretch(1)

        step_row = QHBoxLayout()
        step_row.addWidget(self._step_label)
        step_row.addWidget(self._step, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(10)
        layout.addLayout(step_row)
        layout.addWidget(self._hint)
        layout.addLayout(list_row, 1)
        layout.addLayout(add_row)
        layout.addWidget(self._status)
        layout.addLayout(bottom)
        self.retranslate()
        self._show_step()

    # ------------------------------------------------------------- public API
    def retranslate(self) -> None:
        """Set every text in the current interface language."""
        self._step_label.setText(tr("models.step"))
        for index, (_field, key) in enumerate(STEPS):
            self._step.setItemText(index, tr(key))
        self._hint.setText(tr("models.hint"))
        self._up.setToolTip(tr("models.up"))
        self._down.setToolTip(tr("models.down"))
        self._remove.setToolTip(tr("models.remove"))
        self._add_button.setText(tr("models.add"))
        self._new.lineEdit().setPlaceholderText(tr("models.add_placeholder"))
        self._refresh.setText(tr("models.refresh"))
        self._reset.setText(tr("models.reset"))
        if self._status_text is not None:
            key, values = self._status_text
            self._status.setText(tr(key, **values))

    def load_catalog(self) -> None:
        """Fetch the models available with the user's key, in the background."""
        if self._loading:
            return
        key = read_api_key(self._config.gemini_api_key_env)
        if not key:
            self._set_status("models.no_key")
            return
        self._loading = True
        self._refresh.setEnabled(False)
        self._set_status("models.loading")

        def work() -> None:
            try:
                self._catalog_loaded.emit(list_gemini_models(key), "")
            except TranslationError as exc:
                self._catalog_loaded.emit([], str(exc))

        threading.Thread(target=work, name="ModelCatalog", daemon=True).start()

    # -------------------------------------------------------------- internals
    @staticmethod
    def _small_button(text: str, slot: object) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("small")
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.clicked.connect(slot)
        return button

    def _field(self) -> str:
        return self._step.currentData()

    def _models(self) -> list[str]:
        return [self._list.item(i).text() for i in range(self._list.count())]

    def _show_step(self) -> None:
        self._list.clear()
        self._list.addItems(list(getattr(self._config, self._field())))
        self._list.setCurrentRow(0)
        self._fill_suggestions()
        self._update_buttons()

    def _fill_suggestions(self) -> None:
        text = self._new.currentText()
        used = set(self._models())
        self._new.clear()
        self._new.addItems([m for m in self._catalog if m not in used])
        self._new.setEditText(text)

    def _commit(self) -> None:
        self.models_changed.emit(self._field(), self._models())
        self._fill_suggestions()
        self._update_buttons()

    def _move(self, delta: int) -> None:
        row = self._list.currentRow()
        target = row + delta
        if row < 0 or not 0 <= target < self._list.count():
            return
        self._list.insertItem(target, self._list.takeItem(row))
        self._list.setCurrentRow(target)
        self._commit()

    def _remove_current(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        if self._list.count() == 1:
            self._set_status("models.last")
            return
        self._list.takeItem(row)
        self._list.setCurrentRow(min(row, self._list.count() - 1))
        self._commit()

    def _add(self) -> None:
        model = self._new.currentText().strip().removeprefix("models/")
        if not model:
            return
        if model in self._models():
            self._set_status("models.duplicate")
            return
        self._list.addItem(model)
        self._list.setCurrentRow(self._list.count() - 1)
        self._new.setEditText("")
        self._commit()

    def _reset_step(self) -> None:
        self._list.clear()
        self._list.addItems(list(getattr(AppConfig(), self._field())))
        self._list.setCurrentRow(0)
        self._commit()

    def _update_buttons(self) -> None:
        row, count = self._list.currentRow(), self._list.count()
        self._up.setEnabled(row > 0)
        self._down.setEnabled(0 <= row < count - 1)
        self._remove.setEnabled(row >= 0 and count > 1)

    def _on_catalog(self, models: list[str], error: str) -> None:
        self._loading = False
        self._refresh.setEnabled(True)
        if error:
            self._set_status("models.load_failed", error=error)
            return
        self._catalog = models
        self._fill_suggestions()
        self._set_status("models.loaded", count=len(models))

    def _set_status(self, key: str, **values: object) -> None:
        """Show a status line; it is kept as a key, so a language switch re-renders it."""
        self._status_text = (key, values)
        self._status.setText(tr(key, **values))
