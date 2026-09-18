from __future__ import annotations

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.services.character_lifecycle_service import (
    list_deleted_characters,
    permanently_delete_all_deleted_characters,
    permanently_delete_character,
    restore_character,
)


class TrashDialog(QDialog):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("ゴミ箱")
        self.resize(560, 460)
        self.setMinimumSize(440, 340)

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            14, 14, 14, 14
        )
        root.setSpacing(10)

        title = QLabel("ゴミ箱")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        note = QLabel(
            "ゴミ箱内のキャラクターはメイン一覧には表示されません。"
        )
        note.setObjectName("MutedText")
        root.addWidget(note)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName(
            "TrashCharacterList"
        )
        self.list_widget.itemDoubleClicked.connect(
            lambda item: self.restore_selected()
        )

        root.addWidget(
            self.list_widget,
            1,
        )

        buttons = QHBoxLayout()

        self.restore_button = QPushButton(
            "復元"
        )
        self.delete_button = QPushButton(
            "完全に削除"
        )
        self.delete_button.setObjectName(
            "DangerButton"
        )

        self.delete_all_button = QPushButton(
            "すべて完全削除"
        )
        self.delete_all_button.setObjectName(
            "DangerButton"
        )
        self.delete_all_button.setToolTip(
            "ゴミ箱内のキャラクターをすべて完全に削除します。"
        )

        close_button = QPushButton(
            "閉じる"
        )

        self.restore_button.clicked.connect(
            self.restore_selected
        )
        self.delete_button.clicked.connect(
            self.delete_selected
        )
        self.delete_all_button.clicked.connect(
            self.delete_all
        )
        close_button.clicked.connect(
            self.accept
        )

        buttons.addWidget(
            self.restore_button
        )
        buttons.addWidget(
            self.delete_button
        )
        buttons.addWidget(
            self.delete_all_button
        )
        buttons.addStretch(1)
        buttons.addWidget(
            close_button
        )

        root.addLayout(
            buttons
        )

    def refresh(self):
        self.list_widget.clear()

        rows = list_deleted_characters()

        for row in rows:
            deleted_at = str(
                row["deleted_at"]
                or ""
            )

            text = row["name"]

            if deleted_at:
                text += (
                    f"    削除: {deleted_at}"
                )

            item = QListWidgetItem(
                text
            )
            item.setData(
                Qt.ItemDataRole.UserRole,
                row["id"],
            )

            self.list_widget.addItem(
                item
            )

        has_items = bool(rows)
        self.restore_button.setEnabled(
            has_items
        )
        self.delete_button.setEnabled(
            has_items
        )
        self.delete_all_button.setEnabled(
            has_items
        )

    def _selected_id(self):
        item = (
            self.list_widget
            .currentItem()
        )

        if item is None:
            return None

        return item.data(
            Qt.ItemDataRole.UserRole
        )

    def restore_selected(self):
        character_id = (
            self._selected_id()
        )

        if not character_id:
            return

        try:
            restore_character(
                character_id
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "復元失敗",
                str(exc),
            )
            return

        self.refresh()
        self.changed.emit()

    def delete_all(self):
        rows = list_deleted_characters()
        count = len(rows)

        if count == 0:
            return

        answer = QMessageBox.warning(
            self,
            "ゴミ箱を空にする",
            (
                f"ゴミ箱内の{count}件を"
                "すべて完全に削除しますか？\n\n"
                "キャラクターデータと画像を削除します。\n"
                "この操作は元に戻せません。"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:
            deleted_count = (
                permanently_delete_all_deleted_characters()
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "一括完全削除失敗",
                str(exc),
            )
            return

        self.refresh()
        self.changed.emit()

        QMessageBox.information(
            self,
            "ゴミ箱を空にしました",
            f"{deleted_count}件を完全に削除しました。",
        )

    def delete_selected(self):
        character_id = (
            self._selected_id()
        )

        if not character_id:
            return

        item = (
            self.list_widget
            .currentItem()
        )
        name = (
            item.text()
            if item
            else "このキャラクター"
        )

        answer = QMessageBox.question(
            self,
            "完全削除",
            f"{name}\n\n"
            "このキャラクターを完全に削除しますか？\n"
            "画像を含め、元に戻せません。",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:
            permanently_delete_character(
                character_id
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "完全削除失敗",
                str(exc),
            )
            return

        self.refresh()
        self.changed.emit()
