from __future__ import annotations

import re

from PySide6.QtCore import (
    Qt,
    Signal,
    QStringListModel,
    QTimer,
)
from PySide6.QtGui import (
    QGuiApplication,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QCompleter,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QWidget,
)


class TagInputLineEdit(QLineEdit):
    copyCardsRequested = Signal()
    pasteCardsRequested = Signal(str)
    commitRequested = Signal()
    completionAccepted = Signal(str)

    def keyPressEvent(self, event):
        if event.matches(
            QKeySequence.StandardKey.Copy
        ):
            if self.hasSelectedText():
                super().keyPressEvent(event)
            else:
                self.copyCardsRequested.emit()
            return

        if event.matches(
            QKeySequence.StandardKey.Paste
        ):
            text = QGuiApplication.clipboard().text()

            if text.strip():
                self.pasteCardsRequested.emit(text)
                event.accept()
                return

        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            completer = self.completer()

            if completer is not None:
                popup = completer.popup()

                if (
                    popup is not None
                    and popup.isVisible()
                ):
                    index = popup.currentIndex()

                    if index.isValid():
                        value = index.data(
                            Qt.ItemDataRole.DisplayRole
                        )

                        if value is not None:
                            self.completionAccepted.emit(
                                str(value)
                            )
                            popup.hide()
                            event.accept()
                            return

            self.commitRequested.emit()
            event.accept()
            return

        super().keyPressEvent(event)


class TagChip(QFrame):
    removeRequested = Signal(str)

    def __init__(self, text: str, parent=None):
        super().__init__(parent)

        self.tag_text = str(text)
        self.setObjectName("TagChip")
        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )
        self.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            8, 3, 3, 3
        )
        layout.setSpacing(4)

        label = QLabel(self.tag_text)
        label.setObjectName(
            "TagChipLabel"
        )

        close_button = QPushButton("×")
        close_button.setObjectName(
            "TagChipClose"
        )
        close_button.setFixedSize(
            18, 18
        )
        close_button.setToolTip(
            f"「{self.tag_text}」を外す"
        )
        close_button.clicked.connect(
            lambda: self.removeRequested.emit(
                self.tag_text
            )
        )

        layout.addWidget(label)
        layout.addWidget(close_button)

    def mousePressEvent(self, event):
        self.setFocus(
            Qt.FocusReason.MouseFocusReason
        )
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.matches(
            QKeySequence.StandardKey.Copy
        ):
            QGuiApplication.clipboard().setText(
                self.tag_text
            )
            event.accept()
            return

        super().keyPressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu(self)

        copy_action = menu.addAction(
            "タグ名をコピー"
        )
        remove_action = menu.addAction(
            "タグを外す"
        )

        selected = menu.exec(
            event.globalPos()
        )

        if selected is copy_action:
            QGuiApplication.clipboard().setText(
                self.tag_text
            )
        elif selected is remove_action:
            self.removeRequested.emit(
                self.tag_text
            )


class TagChipEditor(QFrame):
    tagsChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName(
            "TagEditorFrame"
        )
        self.setMinimumHeight(38)

        self._tags: list[str] = []
        self._available: list[str] = []
        self._updating = False
        self._chips: dict[str, TagChip] = {}

        outer = QHBoxLayout(self)
        outer.setContentsMargins(
            0, 0, 0, 0
        )
        outer.setSpacing(0)

        self.scroll = QScrollArea()
        self.scroll.setObjectName(
            "TagScrollArea"
        )
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.scroll.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.content = QWidget()
        self.content.setObjectName(
            "TagEditorContent"
        )
        self.content.setSizePolicy(
            QSizePolicy.Policy.MinimumExpanding,
            QSizePolicy.Policy.Fixed,
        )

        self.row = QHBoxLayout(
            self.content
        )
        self.row.setContentsMargins(
            6, 4, 6, 4
        )
        self.row.setSpacing(5)

        self.input = TagInputLineEdit()
        self.input.setObjectName(
            "TagInput"
        )
        self.input.setPlaceholderText(
            "タグを入力..."
        )
        self.input.setMinimumWidth(180)
        self.input.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

        self.row.addWidget(
            self.input,
            1,
        )

        self.scroll.setWidget(
            self.content
        )
        outer.addWidget(
            self.scroll,
            1,
        )

        self.model = QStringListModel(
            self
        )
        self.completer = QCompleter(
            self.model,
            self,
        )
        self.completer.setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive
        )
        self.completer.setFilterMode(
            Qt.MatchFlag.MatchContains
        )
        self.completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion
        )

        self.input.setCompleter(
            self.completer
        )

        # Enter は QLineEdit.returnPressed に任せず、
        # TagInputLineEdit 内で完全に消費する。
        self.input.commitRequested.connect(
            self._commit_input
        )
        self.input.completionAccepted.connect(
            self._completion_selected
        )

        # マウスで候補をクリックした場合はこちらが走る。
        self.completer.activated.connect(
            self._completion_selected
        )

        self.input.textEdited.connect(
            self._show_completion
        )
        self.input.textChanged.connect(
            self._handle_delimiters
        )
        self.input.copyCardsRequested.connect(
            self.copy_all_tags
        )
        self.input.pasteCardsRequested.connect(
            self.paste_tags
        )

        self.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.customContextMenuRequested.connect(
            self._show_context_menu
        )

    def set_placeholder(
        self,
        text: str,
    ):
        self.input.setPlaceholderText(
            text
        )

    def set_available_tags(
        self,
        names,
    ):
        cleaned = []
        seen = set()

        for raw in names:
            name = str(raw).strip()
            key = name.casefold()

            if name and key not in seen:
                seen.add(key)
                cleaned.append(name)

        cleaned.sort(
            key=str.casefold
        )

        self._available = cleaned
        self.model.setStringList(
            cleaned
        )

    def set_tags(
        self,
        names,
    ):
        self._updating = True

        for tag in list(
            self._tags
        ):
            self._remove_tag(
                tag,
                emit=False,
            )

        for raw in names:
            self._add_tag(
                str(raw),
                emit=False,
            )

        self.input.clear()
        self._updating = False
        self._scroll_to_input()

    def tags(self):
        return list(
            self._tags
        )

    def copy_all_tags(self):
        if not self._tags:
            return

        QGuiApplication.clipboard().setText(
            "\n".join(
                self._tags
            )
        )

    def paste_tags(
        self,
        text=None,
    ):
        if text is None:
            text = (
                QGuiApplication
                .clipboard()
                .text()
            )

        values = self._split_clipboard_text(
            text
        )

        if not values:
            return

        changed = False

        for value in values:
            if self._add_tag(
                value,
                emit=False,
            ):
                changed = True

        self._clear_input_later()

        if changed:
            self.tagsChanged.emit()

    def focus_input(self):
        self.input.setFocus()
        self._scroll_to_input()

    def mousePressEvent(
        self,
        event,
    ):
        self.focus_input()
        super().mousePressEvent(
            event
        )

    def _split_clipboard_text(
        self,
        text,
    ):
        parts = re.split(
            r"[\r\n\t,、]+",
            str(text),
        )

        return [
            part.strip()
            for part in parts
            if part.strip()
        ]

    def _show_context_menu(
        self,
        pos,
    ):
        menu = QMenu(self)

        copy_action = menu.addAction(
            "すべてのタグをコピー"
        )
        paste_action = menu.addAction(
            "タグを貼り付け"
        )

        copy_action.setEnabled(
            bool(self._tags)
        )

        selected = menu.exec(
            self.mapToGlobal(pos)
        )

        if selected is copy_action:
            self.copy_all_tags()
        elif selected is paste_action:
            self.paste_tags()

    def _show_completion(
        self,
        text,
    ):
        if text.strip():
            self.completer.complete()

    def _handle_delimiters(
        self,
        text,
    ):
        if self._updating:
            return

        if not any(
            delimiter in text
            for delimiter in (
                ",",
                "、",
                "\n",
                "\t",
            )
        ):
            return

        values = (
            self._split_clipboard_text(
                text
            )
        )

        self._updating = True
        self.input.clear()
        self._updating = False

        changed = False

        for value in values:
            if self._add_tag(
                value,
                emit=False,
            ):
                changed = True

        if changed:
            self.tagsChanged.emit()

        self._scroll_to_input()

    def _completion_selected(
        self,
        text,
    ):
        value = str(text).strip()

        if not value:
            return

        self._add_tag(
            value
        )

        # QCompleter は activated 発火後に
        # completion 文字列を QLineEdit へ戻すことがある。
        # イベントループの次のtickで消すことで、
        # カードの後ろに生文字列が残るのを防ぐ。
        self._clear_input_later()

    def _commit_input(self):
        text = (
            self.input
            .text()
            .strip()
        )

        if not text:
            return

        self._add_tag(
            text
        )
        self._clear_input_later()

    def _clear_input_later(self):
        QTimer.singleShot(
            0,
            self._finish_clear_input,
        )

    def _finish_clear_input(self):
        self._updating = True
        self.input.clear()
        self._updating = False

        popup = self.completer.popup()

        if popup is not None:
            popup.hide()

        self.input.setFocus()
        self._scroll_to_input()

    def _add_tag(
        self,
        raw,
        emit=True,
    ):
        tag = str(raw).strip()

        if not tag:
            return False

        if tag.casefold() in {
            item.casefold()
            for item in self._tags
        }:
            return False

        chip = TagChip(
            tag,
            self.content,
        )
        chip.removeRequested.connect(
            self._remove_tag
        )

        self.row.insertWidget(
            self.row.count() - 1,
            chip,
            0,
        )

        self._tags.append(
            tag
        )
        self._chips[
            tag.casefold()
        ] = chip

        if tag.casefold() not in {
            item.casefold()
            for item in self._available
        }:
            self._available.append(
                tag
            )
            self._available.sort(
                key=str.casefold
            )
            self.model.setStringList(
                self._available
            )

        self.content.adjustSize()
        self._scroll_to_input()

        if (
            emit
            and not self._updating
        ):
            self.tagsChanged.emit()

        return True

    def _remove_tag(
        self,
        tag,
        emit=True,
    ):
        key = str(tag).casefold()

        chip = self._chips.pop(
            key,
            None,
        )

        if chip is not None:
            self.row.removeWidget(
                chip
            )
            chip.deleteLater()

        self._tags = [
            item
            for item in self._tags
            if item.casefold() != key
        ]

        self.content.adjustSize()
        self._scroll_to_input()

        if (
            emit
            and not self._updating
        ):
            self.tagsChanged.emit()

    def _scroll_to_input(self):
        self.scroll.ensureWidgetVisible(
            self.input,
            20,
            0,
        )
