from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.services.settings_service import (
    apply_ui_font_size,
    load_settings,
    save_settings,
)


class SettingsDialog(QDialog):
    settingsChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("設定")
        self.resize(540, 440)
        self.setMinimumWidth(480)

        self._build_ui()
        self._load()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            16,
            16,
            16,
            16,
        )
        root.setSpacing(14)

        title = QLabel("設定")
        title.setObjectName(
            "DialogTitle"
        )
        root.addWidget(title)

        form = QFormLayout()
        form.setHorizontalSpacing(20)
        form.setVerticalSpacing(12)

        self.autosave_check = QCheckBox(
            "自動保存を有効にする"
        )

        self.autosave_delay = QComboBox()
        self.autosave_delay.addItem("0.3秒", 300)
        self.autosave_delay.addItem("0.75秒", 750)
        self.autosave_delay.addItem("1.5秒", 1500)
        self.autosave_delay.addItem("3秒", 3000)

        self.font_size = QComboBox()
        self.font_size.addItem("小", "small")
        self.font_size.addItem("中", "medium")
        self.font_size.addItem("大", "large")

        self.token_size = QSpinBox()
        self.token_size.setRange(1, 20)
        self.token_size.setSuffix(" マス")

        self.token_active = QCheckBox(
            "駒を盤面に出す"
        )
        self.token_active.setToolTip(
            "ONの場合、ココフォリアへ送信した駒を"
            "盤面に出した状態（active=true）にします。"
            "OFFの場合はしまった状態（active=false）で送信します。"
        )

        self.developer_mode = QCheckBox(
            "デベロッパーモード"
        )
        self.developer_mode.setToolTip(
            "式・CCFOLIA Export ID・式エラーなど、"
            "通常は隠している内部情報を表示します。"
        )

        form.addRow(
            "自動保存",
            self.autosave_check,
        )
        form.addRow(
            "保存までの待ち時間",
            self.autosave_delay,
        )
        form.addRow(
            "文字サイズ",
            self.font_size,
        )
        form.addRow(
            "デフォルト駒サイズ",
            self.token_size,
        )
        form.addRow(
            "ココフォリア送信",
            self.token_active,
        )
        form.addRow(
            "詳細設定",
            self.developer_mode,
        )

        root.addLayout(form)

        note = QLabel(
            "「駒を盤面に出す」は、デスクトップ版・ブラウザパネルの"
            "どちらから送信した場合にも共通で適用されます。\n"
            "デベロッパーモードを変更した場合、"
            "開いているキャラクター画面は一度閉じて開き直すと反映されます。"
        )
        note.setWordWrap(True)
        note.setObjectName(
            "MutedText"
        )
        root.addWidget(note)

        root.addStretch(1)

        buttons = QHBoxLayout()
        buttons.addStretch(1)

        cancel_button = QPushButton(
            "キャンセル"
        )
        save_button = QPushButton(
            "保存"
        )
        save_button.setObjectName(
            "PrimaryButton"
        )

        cancel_button.clicked.connect(
            self.reject
        )
        save_button.clicked.connect(
            self.save
        )

        buttons.addWidget(
            cancel_button
        )
        buttons.addWidget(
            save_button
        )

        root.addLayout(buttons)

    def _load(self):
        settings = load_settings()

        self.autosave_check.setChecked(
            settings["autosave_enabled"]
        )

        delay_index = self.autosave_delay.findData(
            settings["autosave_delay_ms"]
        )
        if delay_index < 0:
            delay_index = self.autosave_delay.findData(750)

        self.autosave_delay.setCurrentIndex(
            max(0, delay_index)
        )

        font_index = self.font_size.findData(
            settings["font_size"]
        )
        self.font_size.setCurrentIndex(
            max(0, font_index)
        )

        self.token_size.setValue(
            settings["default_token_size"]
        )

        self.token_active.setChecked(
            settings.get(
                "cocofolia_token_active",
                True,
            )
        )

        self.developer_mode.setChecked(
            settings.get(
                "developer_mode",
                False,
            )
        )

    def save(self):
        values = {
            "autosave_enabled": (
                self.autosave_check.isChecked()
            ),
            "autosave_delay_ms": (
                self.autosave_delay.currentData()
            ),
            "font_size": (
                self.font_size.currentData()
            ),
            "default_token_size": (
                self.token_size.value()
            ),
            "cocofolia_token_active": (
                self.token_active.isChecked()
            ),
            "developer_mode": (
                self.developer_mode.isChecked()
            ),
        }

        try:
            save_settings(values)
            apply_ui_font_size()
        except Exception as exc:
            QMessageBox.critical(
                self,
                "設定を保存できません",
                str(exc),
            )
            return

        self.settingsChanged.emit()
        self.accept()
