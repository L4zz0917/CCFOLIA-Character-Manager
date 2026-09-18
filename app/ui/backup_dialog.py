from __future__ import annotations

from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app.services.backup_service import (
    create_backup,
    default_backup_path,
    inspect_backup,
    restore_backup,
)


class BackupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("バックアップ")
        self.resize(520, 270)
        self.setMinimumWidth(440)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        title = QLabel("バックアップ / 復元")
        title.setObjectName("DialogTitle")
        root.addWidget(title)

        description = QLabel(
            "キャラクターデータベース、画像、その他の"
            "app_dataを1つのZIPへ保存します。"
        )
        description.setWordWrap(True)
        description.setObjectName("MutedText")
        root.addWidget(description)

        create_button = QPushButton("バックアップを作成")
        create_button.setObjectName("PrimaryButton")
        create_button.clicked.connect(
            self.create_backup_file
        )

        restore_button = QPushButton("バックアップから復元")
        restore_button.clicked.connect(
            self.restore_backup_file
        )

        root.addWidget(create_button)
        root.addWidget(restore_button)

        warning = QLabel(
            "復元すると現在のデータは選択したバックアップ時点へ戻ります。"
            "復元直前の状態は自動的に別バックアップとして保存されます。"
        )
        warning.setWordWrap(True)
        warning.setObjectName("MutedText")
        root.addWidget(warning)

        root.addStretch(1)

        bottom = QHBoxLayout()
        bottom.addStretch(1)

        close_button = QPushButton("閉じる")
        close_button.clicked.connect(self.accept)

        bottom.addWidget(close_button)
        root.addLayout(bottom)

    def create_backup_file(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "バックアップZIPを保存",
            str(default_backup_path()),
            "ZIPファイル (*.zip)",
        )

        if not path:
            return

        try:
            result = create_backup(path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "バックアップ失敗",
                str(exc),
            )
            return

        QMessageBox.information(
            self,
            "バックアップ完了",
            "バックアップを作成しました。\n\n"
            + result["path"],
        )

    def restore_backup_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "復元するバックアップZIPを選択",
            "",
            "ZIPファイル (*.zip)",
        )

        if not path:
            return

        try:
            info = inspect_backup(path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "バックアップ確認失敗",
                str(exc),
            )
            return

        created_at = info["created_at"] or "不明"

        answer = QMessageBox.question(
            self,
            "バックアップから復元",
            "次のバックアップへ戻します。\n\n"
            f"作成日時: {created_at}\n"
            f"保存ファイル数: {info['asset_count']}\n\n"
            "現在の状態は復元直前バックアップとして"
            "自動保存されます。\n"
            "続行しますか？",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            result = restore_backup(path)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "復元失敗",
                str(exc),
            )
            return

        QMessageBox.information(
            self,
            "復元完了",
            "バックアップを復元しました。\n\n"
            "安全のためアプリを終了します。"
            "もう一度起動してください。\n\n"
            "復元直前バックアップ:\n"
            + result["safety_backup"],
        )

        QApplication.quit()
