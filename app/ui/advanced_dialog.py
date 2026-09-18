from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services.advanced_service import (
    apply_coc6_template,
    generate_coc6_palette,
    get_source_values,
    load_advanced_bundle,
    save_advanced_bundle,
)
from app.services.formula_engine import (
    FormulaError,
    evaluate_formula,
    resolve_value_text,
)
from app.ui.skill_block_editor import SkillBlockEditor


from app.services.settings_service import (
    get_bool_setting,
    get_int_setting,
)
class AdvancedCharacterDialog(QDialog):
    changed = Signal()

    def __init__(self, character_id: str, parent=None):
        super().__init__(parent)

        self.character_id = character_id
        self.loading = True
        self.dirty = False
        self.palette_records = []

        self.autosave_enabled = get_bool_setting(
            "autosave_enabled",
            True,
        )
        self.autosave_delay_ms = get_int_setting(
            "autosave_delay_ms",
            750,
            minimum=250,
            maximum=5000,
        )

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(
            self.autosave_delay_ms
        )
        self.timer.timeout.connect(
            self._autosave_now
        )

        self.setWindowTitle(
            "派生値・技能・チャットパレット"
        )
        self.resize(980, 700)
        self.setMinimumSize(820, 580)

        self._build_ui()
        self._load()
        self.loading = False
        self._set_state("保存済み")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            14, 14, 14, 14
        )
        root.setSpacing(10)

        top = QHBoxLayout()

        title = QLabel(
            "派生値・技能・チャットパレット"
        )
        title.setObjectName("DialogTitle")

        self.state_label = QLabel("")
        self.state_label.setObjectName(
            "SaveState"
        )

        self.template_button = QPushButton(
            "CoC6テンプレート"
        )
        self.template_button.clicked.connect(
            self._apply_coc6
        )

        self.save_button = QPushButton("保存")
        self.save_button.setObjectName(
            "PrimaryButton"
        )
        self.save_button.clicked.connect(
            self.save
        )

        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self.state_label)
        top.addWidget(self.template_button)
        top.addWidget(self.save_button)

        root.addLayout(top)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self._build_derived_tab()
        self._build_skills_tab()
        self._build_palettes_tab()

        bottom = QHBoxLayout()
        bottom.addStretch(1)

        close_button = QPushButton("閉じる")
        close_button.clicked.connect(
            self.close
        )
        bottom.addWidget(close_button)

        root.addLayout(bottom)

    def _configure_table(
        self,
        table: QTableWidget,
    ):
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(
            34
        )
        table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

    def _build_derived_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        note = QLabel(
            "例: [STR]*5 / ceil(([CON]+[SIZ])/2) / db6([STR]+[SIZ])"
        )
        note.setObjectName("MutedText")
        layout.addWidget(note)

        self.derived_table = QTableWidget(
            0, 4
        )
        self.derived_table.setHorizontalHeaderLabels(
            ["名前", "式", "結果", "エラー"]
        )
        self._configure_table(
            self.derived_table
        )

        header = self.derived_table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )

        self.derived_table.itemChanged.connect(
            self._derived_changed
        )

        layout.addWidget(
            self.derived_table,
            1,
        )

        row = QHBoxLayout()
        add_button = QPushButton("行を追加")
        remove_button = QPushButton(
            "選択行を削除"
        )

        add_button.clicked.connect(
            self._add_derived
        )
        remove_button.clicked.connect(
            lambda: self._remove_row(
                self.derived_table
            )
        )

        row.addWidget(add_button)
        row.addWidget(remove_button)
        row.addStretch(1)

        layout.addLayout(row)
        self.tabs.addTab(tab, "派生値")

    def _build_skills_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.skills_editor = SkillBlockEditor()
        self.skills_editor.changed.connect(
            self._skills_changed
        )

        layout.addWidget(
            self.skills_editor,
            1,
        )

        self.tabs.addTab(
            tab,
            "技能",
        )

    def _build_palettes_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(
            0, 0, 0, 0
        )

        self.palette_list = QListWidget()
        self.palette_list.currentRowChanged.connect(
            self._palette_selected
        )

        list_buttons = QHBoxLayout()
        add_button = QPushButton("追加")
        remove_button = QPushButton("削除")

        add_button.clicked.connect(
            self._add_palette
        )
        remove_button.clicked.connect(
            self._remove_palette
        )

        list_buttons.addWidget(add_button)
        list_buttons.addWidget(remove_button)

        left_layout.addWidget(
            self.palette_list,
            1,
        )
        left_layout.addLayout(list_buttons)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(
            0, 0, 0, 0
        )

        name_row = QHBoxLayout()

        self.palette_name = QLineEdit()
        self.palette_name.setPlaceholderText(
            "パレット名"
        )

        self.palette_mode = QComboBox()
        self.palette_mode.addItem(
            "通常",
            "normal",
        )
        self.palette_mode.addItem(
            "KP",
            "kp",
        )

        name_row.addWidget(
            self.palette_name,
            1,
        )
        name_row.addWidget(
            self.palette_mode
        )

        generate_button = QPushButton(
            "CoC6基本パレット生成"
        )
        generate_button.clicked.connect(
            self._generate_palette
        )

        self.palette_content = QTextEdit()
        self.palette_content.setPlaceholderText(
            "チャットパレット本文"
        )

        self.palette_name.textChanged.connect(
            self._palette_edited
        )
        self.palette_mode.currentIndexChanged.connect(
            self._palette_edited
        )
        self.palette_content.textChanged.connect(
            self._palette_edited
        )

        right_layout.addLayout(name_row)
        right_layout.addWidget(
            generate_button
        )
        right_layout.addWidget(
            self.palette_content,
            1,
        )

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([230, 650])

        layout.addWidget(splitter, 1)
        self.tabs.addTab(
            tab,
            "チャットパレット",
        )

    def _load(self):
        bundle = load_advanced_bundle(
            self.character_id
        )

        self.derived_table.blockSignals(True)
        self.derived_table.setRowCount(0)

        for row in bundle["derived"]:
            self._append_derived(
                row["label"],
                row["formula"],
                row["last_value"],
                row["error"],
            )

        self.derived_table.blockSignals(False)

        self.skills_editor.set_skills(
            bundle["skills"]
        )

        self.palette_records = [
            {
                "name": row["name"],
                "mode": row["mode"],
                "content": row["content"],
            }
            for row in bundle["palettes"]
        ]

        self._refresh_palette_list(
            0 if self.palette_records else -1
        )

        self._recalculate_previews()

    def _readonly_item(self, text=""):
        item = QTableWidgetItem(str(text))
        item.setFlags(
            item.flags()
            & ~Qt.ItemFlag.ItemIsEditable
        )
        return item

    def _append_derived(
        self,
        label="",
        formula="",
        result="",
        error="",
    ):
        row = self.derived_table.rowCount()
        self.derived_table.insertRow(row)
        self.derived_table.setRowHeight(
            row, 34
        )

        self.derived_table.setItem(
            row, 0, QTableWidgetItem(label)
        )
        self.derived_table.setItem(
            row, 1, QTableWidgetItem(formula)
        )
        self.derived_table.setItem(
            row, 2, self._readonly_item(result)
        )
        self.derived_table.setItem(
            row, 3, self._readonly_item(error)
        )

    def _append_skill(
        self,
        label="",
        value="",
        preview="",
    ):
        row = self.skills_table.rowCount()
        self.skills_table.insertRow(row)
        self.skills_table.setRowHeight(
            row, 34
        )

        self.skills_table.setItem(
            row, 0, QTableWidgetItem(label)
        )
        self.skills_table.setItem(
            row, 1, QTableWidgetItem(value)
        )
        self.skills_table.setItem(
            row, 2, self._readonly_item(preview)
        )

    def _add_derived(self):
        self.derived_table.blockSignals(True)
        self._append_derived()
        self.derived_table.blockSignals(False)

        row = self.derived_table.rowCount() - 1
        self.derived_table.setCurrentCell(
            row, 0
        )
        self._mark_dirty()

    def _add_skill(self):
        self.skills_table.blockSignals(True)
        self._append_skill()
        self.skills_table.blockSignals(False)

        row = self.skills_table.rowCount() - 1
        self.skills_table.setCurrentCell(
            row, 0
        )
        self._mark_dirty()

    def _remove_row(self, table):
        row = table.currentRow()
        if row < 0:
            return

        table.removeRow(row)
        self._mark_dirty()
        self._recalculate_previews()

    def _derived_changed(self, item):
        if item.column() in (0, 1):
            self._recalculate_previews()
            self._mark_dirty()

    def _skills_changed(self, *args):
        self._recalculate_previews()
        self._mark_dirty()

    def _recalculate_previews(self):
        if self.loading:
            return

        source_values = get_source_values(
            self.character_id
        )

        self.derived_table.blockSignals(True)

        for row in range(
            self.derived_table.rowCount()
        ):
            formula_item = self.derived_table.item(
                row, 1
            )
            formula = (
                formula_item.text()
                if formula_item
                else ""
            )

            result = ""
            error = ""

            if formula.strip():
                try:
                    result = evaluate_formula(
                        formula,
                        source_values,
                    )
                except FormulaError as exc:
                    error = str(exc)

            self.derived_table.item(
                row, 2
            ).setText(result)
            self.derived_table.item(
                row, 3
            ).setText(error)

        self.derived_table.blockSignals(False)

        self.skills_editor.refresh_previews(
            source_values
        )

    def _collect_derived(self):
        output = []

        for row in range(
            self.derived_table.rowCount()
        ):
            label_item = self.derived_table.item(
                row, 0
            )
            formula_item = self.derived_table.item(
                row, 1
            )

            output.append(
                {
                    "label": (
                        label_item.text()
                        if label_item
                        else ""
                    ),
                    "formula": (
                        formula_item.text()
                        if formula_item
                        else ""
                    ),
                }
            )

        return output

    def _collect_skills(self):
        return self.skills_editor.skills()

    def _refresh_palette_list(
        self,
        select_row=-1,
    ):
        self.palette_list.blockSignals(True)
        self.palette_list.clear()

        for palette in self.palette_records:
            name = (
                palette["name"].strip()
                or "無題"
            )
            suffix = (
                " [KP]"
                if palette["mode"] == "kp"
                else ""
            )
            self.palette_list.addItem(
                name + suffix
            )

        self.palette_list.blockSignals(False)

        if (
            0 <= select_row
            < len(self.palette_records)
        ):
            self.palette_list.setCurrentRow(
                select_row
            )
        else:
            self.palette_list.setCurrentRow(
                -1
            )
            self._show_palette(-1)

    def _palette_selected(self, row):
        self._show_palette(row)

    def _show_palette(self, row):
        self.loading = True

        enabled = (
            0 <= row < len(self.palette_records)
        )

        self.palette_name.setEnabled(enabled)
        self.palette_mode.setEnabled(enabled)
        self.palette_content.setEnabled(enabled)

        if enabled:
            palette = self.palette_records[row]

            self.palette_name.setText(
                palette["name"]
            )

            index = self.palette_mode.findData(
                palette["mode"]
            )
            self.palette_mode.setCurrentIndex(
                max(0, index)
            )

            self.palette_content.setPlainText(
                palette["content"]
            )
        else:
            self.palette_name.clear()
            self.palette_mode.setCurrentIndex(0)
            self.palette_content.clear()

        self.loading = False

    def _palette_edited(self):
        if self.loading:
            return

        row = self.palette_list.currentRow()
        if not (
            0 <= row < len(self.palette_records)
        ):
            return

        self.palette_records[row] = {
            "name": self.palette_name.text(),
            "mode": self.palette_mode.currentData(),
            "content": self.palette_content.toPlainText(),
        }

        label = (
            self.palette_name.text().strip()
            or "無題"
        )

        if (
            self.palette_mode.currentData()
            == "kp"
        ):
            label += " [KP]"

        self.palette_list.item(row).setText(
            label
        )

        self._mark_dirty()

    def _add_palette(self):
        self.palette_records.append(
            {
                "name": "通常",
                "mode": "normal",
                "content": "",
            }
        )

        self._refresh_palette_list(
            len(self.palette_records) - 1
        )
        self._mark_dirty()

    def _remove_palette(self):
        row = self.palette_list.currentRow()
        if not (
            0 <= row < len(self.palette_records)
        ):
            return

        del self.palette_records[row]

        next_row = min(
            row,
            len(self.palette_records) - 1,
        )
        self._refresh_palette_list(
            next_row
        )
        self._mark_dirty()

    def _generate_palette(self):
        content = generate_coc6_palette(
            self.character_id
        )

        if not content:
            QMessageBox.information(
                self,
                "生成できません",
                "数値として解決できるCoC6の派生値・技能がありません。\n"
                "能力値を入力してから再度生成してください。",
            )
            return

        row = self.palette_list.currentRow()

        if row < 0:
            self.palette_records.append(
                {
                    "name": "CoC6 基本",
                    "mode": "normal",
                    "content": content,
                }
            )
            self._refresh_palette_list(
                len(self.palette_records) - 1
            )
        else:
            self.palette_content.setPlainText(
                content
            )

        self._mark_dirty()

    def _apply_coc6(self):
        answer = QMessageBox.question(
            self,
            "CoC6テンプレート",
            "CoC6用の能力値・HP/MP/SAN・派生値・主要技能を追加します。\n\n"
            "既存の同名項目は上書きしません。続行しますか？",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        if self.dirty:
            if not self.save():
                return

        apply_coc6_template(
            self.character_id
        )

        self.loading = True
        self._load()
        self.loading = False
        self.dirty = False
        self._set_state("保存済み")
        self.changed.emit()

    def _set_state(self, text):
        self.state_label.setText(text)

    def _mark_dirty(self, *args):
        if self.loading:
            return

        self.dirty = True
        self._set_state("未保存")
        if self.autosave_enabled:
            self.timer.start()

    def _autosave_now(self):
        if self.dirty:
            self.save(show_error=False)

    def save(self, show_error=True):
        self._set_state("保存中…")

        try:
            save_advanced_bundle(
                self.character_id,
                self._collect_derived(),
                self._collect_skills(),
                list(self.palette_records),
            )
        except Exception as exc:
            self._set_state("保存エラー")

            if show_error:
                QMessageBox.warning(
                    self,
                    "保存できません",
                    str(exc),
                )
            return False

        self.dirty = False
        self._set_state("保存済み")
        self.changed.emit()
        return True

    def closeEvent(self, event):
        if not self.dirty:
            event.accept()
            return

        if self.autosave_enabled:
            if self.save(show_error=True):
                event.accept()
            else:
                event.ignore()
            return

        answer = QMessageBox.question(
            self,
            "未保存の変更",
            "変更が保存されていません。",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )

        if answer == QMessageBox.StandardButton.Save:
            if self.save(show_error=True):
                event.accept()
            else:
                event.ignore()
        elif answer == QMessageBox.StandardButton.Discard:
            event.accept()
        else:
            event.ignore()
