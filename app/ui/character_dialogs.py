from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal, QSize
from PySide6.QtGui import QColor, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QColorDialog,
    QCompleter,
    QDialog,
    QFrame,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.paths import PROJECT_ROOT
from app.services.advanced_service import (
    apply_coc6_template,
    generate_coc6_palette,
    load_advanced_bundle,
    save_advanced_bundle,
)
from app.services.formula_engine import (
    FormulaError,
    evaluate_formula,
)
from app.ui.skill_block_editor import SkillBlockEditor
from app.ui.advanced_dialog import AdvancedCharacterDialog
from app.ui.tag_chip_editor import TagChipEditor
from app.services.character_service import (
    copy_image_for_character,
    get_bool_setting,
    get_character_bundle,
    get_setting,
    list_groups,
    list_tags,
    save_character_bundle,
    set_setting,
)


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


class ImageListWidget(QListWidget):
    orderChanged = Signal()
    filesDropped = Signal(list, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        mime = event.mimeData()

        if mime.hasUrls():
            paths = [
                Path(url.toLocalFile())
                for url in mime.urls()
                if url.isLocalFile()
            ]
            if any(
                path.is_file()
                and path.suffix.lower() in IMAGE_EXTENSIONS
                for path in paths
            ):
                event.acceptProposedAction()
                return

        super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            return

        super().dragMoveEvent(event)

    def dropEvent(self, event):
        mime = event.mimeData()

        if mime.hasUrls():
            paths = [
                str(Path(url.toLocalFile()))
                for url in mime.urls()
                if url.isLocalFile()
                and Path(url.toLocalFile()).is_file()
                and Path(url.toLocalFile()).suffix.lower()
                in IMAGE_EXTENSIONS
            ]

            if paths:
                index = self.indexAt(event.position().toPoint())
                insert_at = (
                    self.count()
                    if not index.isValid()
                    else index.row()
                )

                self.filesDropped.emit(paths, insert_at)
                event.acceptProposedAction()
                return

        super().dropEvent(event)
        self.orderChanged.emit()


class CharacterEditorDialog(QDialog):
    saved = Signal()

    def __init__(self, character_id: str, parent=None):
        super().__init__(parent)
        self.character_id = character_id
        self.loading = True
        self.dirty = False
        self.memo_records = []

        self.autosave_enabled = get_bool_setting(
            "autosave_enabled",
            True,
        )
        delay_text = get_setting("autosave_delay_ms", "750")
        try:
            delay = int(delay_text)
        except ValueError:
            delay = 750

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setSingleShot(True)
        self.autosave_timer.setInterval(max(250, delay))
        self.autosave_timer.timeout.connect(self._autosave_now)

        self.setWindowTitle("キャラクター編集")
        self.resize(980, 720)
        self.setMinimumSize(820, 600)

        self._build_ui()
        self._load()
        self.loading = False
        self._set_save_state("保存済み")

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        top = QHBoxLayout()

        title = QLabel("キャラクター編集")
        title.setObjectName("DialogTitle")

        self.save_state = QLabel("")
        self.save_state.setObjectName("SaveState")

        self.autosave_check = QCheckBox("自動保存")
        self.autosave_check.setChecked(self.autosave_enabled)
        self.autosave_check.toggled.connect(
            self._autosave_setting_changed
        )

        self.advanced_button = QPushButton("派生・技能・パレット")
        self.advanced_button.clicked.connect(
            self._open_advanced
        )

        self.save_button = QPushButton("保存")
        self.save_button.setObjectName("PrimaryButton")
        self.save_button.clicked.connect(self.save)

        top.addWidget(title)
        top.addStretch(1)
        top.addWidget(self.save_state)
        top.addSpacing(8)
        top.addWidget(self.autosave_check)
        top.addWidget(self.advanced_button)
        top.addWidget(self.save_button)

        root.addLayout(top)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self._build_basic_tab()
        self._build_images_tab()
        self._build_status_tab()
        self._build_params_tab()
        self._build_memos_tab()
        self._build_classification_tab()

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        close_button = QPushButton("閉じる")
        close_button.clicked.connect(self.close)
        close_row.addWidget(close_button)
        root.addLayout(close_row)

    def _open_advanced(self):
        if self.dirty:
            if not self.save(show_error=True):
                return

        dialog = AdvancedCharacterDialog(
            self.character_id,
            self,
        )
        dialog.changed.connect(self.saved.emit)
        dialog.exec()

        self.loading = True
        self._load()
        self.loading = False

    def _build_basic_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        form = QFormLayout()
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self.name_edit = QLineEdit()
        self.player_edit = QLineEdit()
        self.initiative_edit = QLineEdit()
        self.external_url_edit = QLineEdit()

        color_row = QHBoxLayout()
        self.color_edit = QLineEdit()
        self.color_button = QPushButton("色を選択")
        self.color_button.clicked.connect(self._choose_color)
        color_row.addWidget(self.color_edit, 1)
        color_row.addWidget(self.color_button)

        color_widget = QWidget()
        color_widget.setLayout(color_row)

        self.secret_check = QCheckBox("シークレット")
        self.invisible_check = QCheckBox("盤面で非表示")
        self.hide_status_check = QCheckBox("ステータスを隠す")

        flags = QHBoxLayout()
        flags.addWidget(self.secret_check)
        flags.addWidget(self.invisible_check)
        flags.addWidget(self.hide_status_check)
        flags.addStretch(1)

        flags_widget = QWidget()
        flags_widget.setLayout(flags)

        self.export_id_edit = QLineEdit()
        self.export_id_edit.setReadOnly(True)

        form.addRow("名前", self.name_edit)
        form.addRow("プレイヤー名", self.player_edit)
        form.addRow("イニシアティブ", self.initiative_edit)
        form.addRow("外部URL", self.external_url_edit)
        form.addRow("色", color_widget)
        form.addRow("ココフォリア設定", flags_widget)
        form.addRow("CCFOLIA Export ID", self.export_id_edit)

        layout.addLayout(form)
        layout.addStretch(1)

        for widget in (
            self.name_edit,
            self.player_edit,
            self.initiative_edit,
            self.external_url_edit,
            self.color_edit,
        ):
            widget.textChanged.connect(self._mark_dirty)

        for widget in (
            self.secret_check,
            self.invisible_check,
            self.hide_status_check,
        ):
            widget.toggled.connect(self._mark_dirty)

        self.tabs.addTab(tab, "基本情報")

    def _build_images_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        note = QLabel(
            "先頭の画像がメイン画像です。エクスプローラーから画像を直接ドロップできます。"
        )
        note.setObjectName("MutedText")
        layout.addWidget(note)

        self.image_list = ImageListWidget()
        self.image_list.setIconSize(QSize(72, 72))
        self.image_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self.image_list.setDefaultDropAction(
            Qt.DropAction.MoveAction
        )
        self.image_list.orderChanged.connect(self._mark_dirty)
        self.image_list.filesDropped.connect(
            self._external_images_dropped
        )

        layout.addWidget(self.image_list, 1)

        buttons = QHBoxLayout()
        add_button = QPushButton("画像を追加")
        remove_button = QPushButton("選択画像を削除")
        add_button.clicked.connect(self._add_images)
        remove_button.clicked.connect(self._remove_selected_image)

        buttons.addWidget(add_button)
        buttons.addWidget(remove_button)
        buttons.addStretch(1)

        layout.addLayout(buttons)
        self.tabs.addTab(tab, "画像")

    def _configure_table(self, table: QTableWidget):
        table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        table.verticalHeader().setVisible(False)
        table.verticalHeader().setDefaultSectionSize(34)
        table.horizontalHeader().setStretchLastSection(True)

    def _build_status_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.status_table = QTableWidget(0, 3)
        self.status_table.setHorizontalHeaderLabels(
            ["名前", "現在値", "最大値"]
        )
        self._configure_table(self.status_table)
        self.status_table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        self.status_table.itemChanged.connect(self._mark_dirty)

        layout.addWidget(self.status_table, 1)

        row = QHBoxLayout()
        add_button = QPushButton("行を追加")
        remove_button = QPushButton("選択行を削除")
        add_button.clicked.connect(
            lambda: self._add_table_row(self.status_table, 3)
        )
        remove_button.clicked.connect(
            lambda: self._remove_table_row(self.status_table)
        )
        row.addWidget(add_button)
        row.addWidget(remove_button)
        row.addStretch(1)

        layout.addLayout(row)
        self.tabs.addTab(tab, "ステータス")

    def _build_params_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        self.params_table = QTableWidget(0, 2)
        self.params_table.setHorizontalHeaderLabels(
            ["名前", "値"]
        )
        self._configure_table(self.params_table)
        self.params_table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        self.params_table.horizontalHeader().setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        self.params_table.itemChanged.connect(self._mark_dirty)

        layout.addWidget(self.params_table, 1)

        row = QHBoxLayout()
        add_button = QPushButton("行を追加")
        remove_button = QPushButton("選択行を削除")
        add_button.clicked.connect(
            lambda: self._add_table_row(self.params_table, 2)
        )
        remove_button.clicked.connect(
            lambda: self._remove_table_row(self.params_table)
        )
        row.addWidget(add_button)
        row.addWidget(remove_button)
        row.addStretch(1)

        layout.addLayout(row)
        self.tabs.addTab(tab, "パラメータ")

    def _build_memos_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        self.memo_list = QListWidget()
        self.memo_list.currentRowChanged.connect(
            self._memo_selection_changed
        )

        left_buttons = QHBoxLayout()
        add_button = QPushButton("追加")
        remove_button = QPushButton("削除")
        add_button.clicked.connect(self._add_memo)
        remove_button.clicked.connect(self._remove_memo)
        left_buttons.addWidget(add_button)
        left_buttons.addWidget(remove_button)

        left_layout.addWidget(self.memo_list, 1)
        left_layout.addLayout(left_buttons)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)

        self.memo_title = QLineEdit()
        self.memo_title.setPlaceholderText("メモのタイトル")

        self.memo_private = QCheckBox("非公開メモ")

        self.memo_body = QTextEdit()
        self.memo_body.setPlaceholderText("メモ本文")

        right_layout.addWidget(self.memo_title)
        right_layout.addWidget(self.memo_private)
        right_layout.addWidget(self.memo_body, 1)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([230, 650])

        layout.addWidget(splitter, 1)

        self.memo_title.textChanged.connect(self._memo_edited)
        self.memo_private.toggled.connect(self._memo_edited)
        self.memo_body.textChanged.connect(self._memo_edited)

        self.tabs.addTab(tab, "メモ")

    def _build_classification_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        tag_label = QLabel("タグ")
        tag_label.setObjectName("SectionTitle")

        self.tags_edit = TagChipEditor()
        self.tags_edit.tagsChanged.connect(
            self._mark_dirty
        )

        note = QLabel(
            "文字を入力すると既存タグを予測表示します。候補を選ぶかEnterでタグカードになります。"
        )
        note.setObjectName("MutedText")

        group_label = QLabel("所属グループ")
        group_label.setObjectName("SectionTitle")

        self.group_tree = QTreeWidget()
        self.group_tree.setHeaderHidden(True)
        self.group_tree.setIndentation(18)
        self.group_tree.itemChanged.connect(
            self._group_check_changed
        )

        layout.addWidget(tag_label)
        layout.addWidget(self.tags_edit)
        layout.addWidget(note)
        layout.addSpacing(8)
        layout.addWidget(group_label)
        layout.addWidget(self.group_tree, 1)

        self.tabs.addTab(tab, "分類")

    def _load(self):
        bundle = get_character_bundle(self.character_id)
        c = bundle["character"]

        self.name_edit.setText(c["name"])
        self.player_edit.setText(c["player_name"])
        self.initiative_edit.setText(str(c["initiative"]))
        self.external_url_edit.setText(c["external_url"])
        self.color_edit.setText(c["color"])
        self.secret_check.setChecked(bool(c["secret"]))
        self.invisible_check.setChecked(bool(c["invisible"]))
        self.hide_status_check.setChecked(bool(c["hide_status"]))
        self.export_id_edit.setText(c["cocofolia_export_id"])

        self.image_list.clear()
        for image in bundle["images"]:
            self._append_image_item(image)

        self.status_table.setRowCount(0)
        for status in bundle["statuses"]:
            self._append_table_values(
                self.status_table,
                [
                    status["label"],
                    "" if status["current_value"] is None else str(status["current_value"]),
                    "" if status["max_value"] is None else str(status["max_value"]),
                ],
            )

        self.params_table.setRowCount(0)
        for param in bundle["params"]:
            self._append_table_values(
                self.params_table,
                [param["label"], param["value"]],
            )

        self.memo_records = [
            {
                "title": memo["title"],
                "body": memo["body"],
                "private": bool(memo["is_private"]),
            }
            for memo in bundle["memos"]
        ]
        self._refresh_memo_list(
            select_row=0 if self.memo_records else -1
        )

        self._setup_tag_completer()
        self.tags_edit.set_tags(
            [tag["name"] for tag in bundle["tags"]]
        )
        self._load_group_tree(set(bundle["group_ids"]))

    def _setup_tag_completer(self):
        names = [
            row["name"]
            for row in list_tags()
        ]
        self.tags_edit.set_available_tags(
            names
        )

    def _load_group_tree(self, selected_ids: set[str]):
        self.group_tree.blockSignals(True)
        self.group_tree.clear()

        rows = list_groups()
        item_map = {}

        for row in rows:
            item = QTreeWidgetItem([row["name"]])
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                row["id"],
            )
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(
                0,
                Qt.CheckState.Checked
                if row["id"] in selected_ids
                else Qt.CheckState.Unchecked,
            )
            item_map[row["id"]] = item

        for row in rows:
            item = item_map[row["id"]]
            parent_id = row["parent_group_id"]
            if parent_id and parent_id in item_map:
                item_map[parent_id].addChild(item)
            else:
                self.group_tree.addTopLevelItem(item)

        self.group_tree.expandAll()
        self.group_tree.blockSignals(False)

    def _group_check_changed(self, item, column):
        self._mark_dirty()

    def _append_image_item(self, image: dict):
        path = PROJECT_ROOT / image["relative_path"]
        label = image.get("label") or path.name

        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, dict(image))

        if path.exists():
            item.setIcon(QIcon(str(path)))

        self.image_list.addItem(item)

    def _insert_image_item(self, image: dict, index: int):
        path = PROJECT_ROOT / image["relative_path"]
        label = image.get("label") or path.name

        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, dict(image))

        if path.exists():
            item.setIcon(QIcon(str(path)))

        self.image_list.insertItem(index, item)

    def _external_images_dropped(self, paths: list[str], insert_at: int):
        added = 0
        try:
            for offset, path in enumerate(paths):
                image = copy_image_for_character(
                    self.character_id,
                    path,
                )
                self._insert_image_item(
                    image,
                    min(insert_at + offset, self.image_list.count()),
                )
                added += 1
        except Exception as exc:
            QMessageBox.warning(
                self,
                "画像追加",
                f"{added}件追加したところでエラーが発生しました。\n\n{exc}",
            )

        if added:
            self._mark_dirty()

    def _add_images(self):
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "画像を追加",
            "",
            "画像ファイル (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        if not paths:
            return

        try:
            for path in paths:
                image = copy_image_for_character(
                    self.character_id,
                    path,
                )
                self._append_image_item(image)
        except Exception as exc:
            QMessageBox.critical(self, "画像追加失敗", str(exc))
            return

        self._mark_dirty()

    def _remove_selected_image(self):
        row = self.image_list.currentRow()
        if row < 0:
            return
        self.image_list.takeItem(row)
        self._mark_dirty()

    def _choose_color(self):
        initial = QColor(self.color_edit.text())
        color = QColorDialog.getColor(
            initial if initial.isValid() else QColor("#888888"),
            self,
            "キャラクター色",
        )
        if color.isValid():
            self.color_edit.setText(color.name())

    def _add_table_row(self, table: QTableWidget, columns: int):
        row = table.rowCount()
        table.insertRow(row)
        table.setRowHeight(row, 34)
        for column in range(columns):
            table.setItem(row, column, QTableWidgetItem(""))
        table.setCurrentCell(row, 0)
        self._mark_dirty()

    def _append_table_values(self, table: QTableWidget, values: list[str]):
        row = table.rowCount()
        table.insertRow(row)
        table.setRowHeight(row, 34)
        for column, value in enumerate(values):
            table.setItem(row, column, QTableWidgetItem(value))

    def _remove_table_row(self, table: QTableWidget):
        row = table.currentRow()
        if row >= 0:
            table.removeRow(row)
            self._mark_dirty()

    def _table_rows(self, table: QTableWidget) -> list[list[str]]:
        output = []
        for row in range(table.rowCount()):
            values = []
            for column in range(table.columnCount()):
                item = table.item(row, column)
                values.append("" if item is None else item.text())
            output.append(values)
        return output

    def _refresh_memo_list(self, select_row: int = -1):
        self.memo_list.blockSignals(True)
        self.memo_list.clear()

        for memo in self.memo_records:
            title = memo["title"].strip() or "無題"
            if memo["private"]:
                title = f"🔒 {title}"
            self.memo_list.addItem(title)

        self.memo_list.blockSignals(False)

        if 0 <= select_row < len(self.memo_records):
            self.memo_list.setCurrentRow(select_row)
        else:
            self.memo_list.setCurrentRow(-1)
            self._show_memo(-1)

    def _memo_selection_changed(self, row: int):
        self._show_memo(row)

    def _show_memo(self, row: int):
        self.loading = True
        enabled = 0 <= row < len(self.memo_records)

        self.memo_title.setEnabled(enabled)
        self.memo_private.setEnabled(enabled)
        self.memo_body.setEnabled(enabled)

        if enabled:
            memo = self.memo_records[row]
            self.memo_title.setText(memo["title"])
            self.memo_private.setChecked(memo["private"])
            self.memo_body.setPlainText(memo["body"])
        else:
            self.memo_title.clear()
            self.memo_private.setChecked(False)
            self.memo_body.clear()

        self.loading = False

    def _memo_edited(self):
        if self.loading:
            return

        row = self.memo_list.currentRow()
        if not (0 <= row < len(self.memo_records)):
            return

        self.memo_records[row] = {
            "title": self.memo_title.text(),
            "body": self.memo_body.toPlainText(),
            "private": self.memo_private.isChecked(),
        }

        label = self.memo_title.text().strip() or "無題"
        if self.memo_private.isChecked():
            label = f"🔒 {label}"
        self.memo_list.item(row).setText(label)

        self._mark_dirty()

    def _add_memo(self):
        self.memo_records.append(
            {
                "title": "新しいメモ",
                "body": "",
                "private": False,
            }
        )
        self._refresh_memo_list(
            select_row=len(self.memo_records) - 1
        )
        self._mark_dirty()

    def _remove_memo(self):
        row = self.memo_list.currentRow()
        if not (0 <= row < len(self.memo_records)):
            return

        del self.memo_records[row]

        next_row = min(row, len(self.memo_records) - 1)
        self._refresh_memo_list(select_row=next_row)
        self._mark_dirty()

    def _autosave_setting_changed(self, checked: bool):
        self.autosave_enabled = checked
        set_setting(
            "autosave_enabled",
            "1" if checked else "0",
        )

        if checked and self.dirty:
            self.autosave_timer.start()

    def _set_save_state(self, text: str):
        self.save_state.setText(text)

    def _mark_dirty(self, *args):
        if self.loading:
            return

        self.dirty = True
        self._set_save_state("未保存")

        if self.autosave_enabled:
            self.autosave_timer.start()

    def _collect_images(self):
        images = []
        for index in range(self.image_list.count()):
            item = self.image_list.item(index)
            data = dict(item.data(Qt.ItemDataRole.UserRole))
            data["sort_order"] = index
            images.append(data)
        return images

    def _collect_statuses(self):
        rows = []
        for values in self._table_rows(self.status_table):
            rows.append(
                {
                    "label": values[0],
                    "current": values[1],
                    "max": values[2],
                }
            )
        return rows

    def _collect_params(self):
        rows = []
        for values in self._table_rows(self.params_table):
            rows.append(
                {
                    "label": values[0],
                    "value": values[1],
                }
            )
        return rows

    def _collect_tag_names(self) -> list[str]:
        return self.tags_edit.tags()

    def _collect_group_ids(self) -> list[str]:
        output = []

        def walk(item: QTreeWidgetItem):
            group_id = item.data(
                0,
                Qt.ItemDataRole.UserRole,
            )
            if (
                group_id
                and item.checkState(0) == Qt.CheckState.Checked
            ):
                output.append(group_id)

            for index in range(item.childCount()):
                walk(item.child(index))

        for index in range(self.group_tree.topLevelItemCount()):
            walk(self.group_tree.topLevelItem(index))

        return output

    def _autosave_now(self):
        if not self.dirty:
            return
        self.save(show_error=False)

    def save(self, show_error: bool = True) -> bool:
        self._set_save_state("保存中…")

        try:
            save_character_bundle(
                self.character_id,
                {
                    "name": self.name_edit.text(),
                    "player_name": self.player_edit.text(),
                    "initiative": self.initiative_edit.text(),
                    "external_url": self.external_url_edit.text(),
                    "color": self.color_edit.text().strip() or "#888888",
                    "secret": self.secret_check.isChecked(),
                    "invisible": self.invisible_check.isChecked(),
                    "hide_status": self.hide_status_check.isChecked(),
                },
                self._collect_images(),
                self._collect_statuses(),
                self._collect_params(),
                list(self.memo_records),
                self._collect_tag_names(),
                self._collect_group_ids(),
            )
        except Exception as exc:
            self._set_save_state("保存エラー")
            if show_error:
                QMessageBox.warning(
                    self,
                    "保存できません",
                    str(exc),
                )
            return False

        self.dirty = False
        self._set_save_state("保存済み")
        self.saved.emit()
        self._setup_tag_completer()
        return True

    def closeEvent(self, event):
        if not self.dirty:
            event.accept()
            return

        if self.autosave_enabled:
            if self.save(show_error=True):
                event.accept()
                return

            choice = QMessageBox.question(
                self,
                "保存できていません",
                "入力にエラーがあるため自動保存できませんでした。\n"
                "保存せず閉じますか？",
                QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Cancel,
            )

            if choice == QMessageBox.StandardButton.Discard:
                event.accept()
            else:
                event.ignore()
            return

        box = QMessageBox(self)
        box.setWindowTitle("未保存の変更")
        box.setText("変更内容を保存しますか？")
        save_button = box.addButton(
            "保存",
            QMessageBox.ButtonRole.AcceptRole,
        )
        discard_button = box.addButton(
            "保存しない",
            QMessageBox.ButtonRole.DestructiveRole,
        )
        box.addButton(
            "キャンセル",
            QMessageBox.ButtonRole.RejectRole,
        )
        box.exec()

        clicked = box.clickedButton()

        if clicked is save_button:
            if self.save(show_error=True):
                event.accept()
            else:
                event.ignore()
        elif clicked is discard_button:
            event.accept()
        else:
            event.ignore()


class CharacterViewDialog(QDialog):
    changed = Signal()

    def __init__(self, character_id: str, parent=None):
        super().__init__(parent)
        self.character_id = character_id

        self.setWindowTitle("キャラクター")
        self.resize(900, 680)
        self.setMinimumSize(760, 560)

        self._build_ui()
        self.reload()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        header = QHBoxLayout()

        self.icon_label = QLabel()
        self.icon_label.setFixedSize(96, 96)
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_label.setObjectName("CharacterPortrait")

        title_block = QVBoxLayout()
        self.name_label = QLabel("")
        self.name_label.setObjectName("CharacterName")

        self.player_label = QLabel("")
        self.player_label.setObjectName("MutedText")

        self.tags_label = QLabel("")
        self.tags_label.setObjectName("MutedText")
        self.tags_label.setWordWrap(True)

        title_block.addWidget(self.name_label)
        title_block.addWidget(self.player_label)
        title_block.addWidget(self.tags_label)
        title_block.addStretch(1)

        self.edit_button = QPushButton("編集")
        self.edit_button.setObjectName("PrimaryButton")
        self.edit_button.clicked.connect(self._edit)

        header.addWidget(self.icon_label)
        header.addLayout(title_block, 1)
        header.addWidget(self.edit_button)

        root.addLayout(header)

        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)

        self.basic_text = QLabel()
        self.basic_text.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.basic_text.setWordWrap(True)
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        basic_layout.addWidget(self.basic_text)
        basic_layout.addStretch(1)
        self.tabs.addTab(basic_tab, "基本情報")

        self.status_table = QTableWidget(0, 3)
        self.status_table.setHorizontalHeaderLabels(
            ["名前", "現在値", "最大値"]
        )
        self.status_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.status_table.verticalHeader().setVisible(False)
        self.status_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.tabs.addTab(self.status_table, "ステータス")

        self.params_table = QTableWidget(0, 2)
        self.params_table.setHorizontalHeaderLabels(["名前", "値"])
        self.params_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.params_table.verticalHeader().setVisible(False)
        self.params_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.tabs.addTab(self.params_table, "パラメータ")

        self.memo_tabs = QTabWidget()
        self.tabs.addTab(self.memo_tabs, "メモ")

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close_button = QPushButton("閉じる")
        close_button.clicked.connect(self.accept)
        bottom.addWidget(close_button)
        root.addLayout(bottom)

    def reload(self):
        bundle = get_character_bundle(self.character_id)
        c = bundle["character"]

        self.name_label.setText(c["name"])
        self.player_label.setText(
            f"Player: {c['player_name']}" if c["player_name"] else ""
        )

        tag_text = ", ".join(
            tag["name"] for tag in bundle["tags"]
        )
        self.tags_label.setText(
            f"Tags: {tag_text}" if tag_text else ""
        )

        self.icon_label.clear()
        self.icon_label.setText("NO IMAGE")

        if bundle["images"]:
            path = PROJECT_ROOT / bundle["images"][0]["relative_path"]
            if path.exists():
                pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    pixmap = pixmap.scaled(
                        self.icon_label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                    self.icon_label.setPixmap(pixmap)

        flags = []
        if c["secret"]:
            flags.append("Secret")
        if c["invisible"]:
            flags.append("Invisible")
        if c["hide_status"]:
            flags.append("HideStatus")
        flag_text = ", ".join(flags) if flags else "なし"

        self.basic_text.setText(
            f"イニシアティブ: {c['initiative']}\n"
            f"外部URL: {c['external_url'] or '—'}\n"
            f"色: {c['color']}\n"
            f"ココフォリア設定: {flag_text}\n\n"
            f"CCFOLIA Export ID:\n{c['cocofolia_export_id']}"
        )

        self._fill_table(
            self.status_table,
            [
                [
                    row["label"],
                    "" if row["current_value"] is None else str(row["current_value"]),
                    "" if row["max_value"] is None else str(row["max_value"]),
                ]
                for row in bundle["statuses"]
            ],
        )

        self._fill_table(
            self.params_table,
            [
                [row["label"], row["value"]]
                for row in bundle["params"]
            ],
        )

        self.memo_tabs.clear()
        for memo in bundle["memos"]:
            text = QTextEdit()
            text.setReadOnly(True)
            text.setPlainText(memo["body"])
            title = memo["title"] or "メモ"
            if memo["is_private"]:
                title = f"🔒 {title}"
            self.memo_tabs.addTab(text, title)

    def _fill_table(self, table: QTableWidget, rows: list[list[str]]):
        table.setRowCount(0)
        for values in rows:
            row = table.rowCount()
            table.insertRow(row)
            for column, value in enumerate(values):
                table.setItem(row, column, QTableWidgetItem(value))

    def _edit(self):
        dialog = CharacterEditorDialog(
            self.character_id,
            self,
        )
        dialog.saved.connect(self._editor_saved)
        dialog.exec()
        self.reload()

    def _editor_saved(self):
        self.changed.emit()


# ---------------------------------------------------------------------------
# Phase 19: unified character view / editor
# ---------------------------------------------------------------------------

_LegacyCharacterEditorDialog = CharacterEditorDialog


class UnifiedCharacterDialog(_LegacyCharacterEditorDialog):
    changed = Signal()

    def __init__(
        self,
        character_id: str,
        parent=None,
        start_edit: bool = False,
    ):
        self._start_edit = start_edit
        self.palette_records = []
        self._edit_mode = False
        super().__init__(
            character_id,
            parent,
        )

        self.setWindowTitle("キャラクター")
        self.resize(1500, 980)
        self.setMinimumSize(1220, 820)
        self.set_edit_mode(
            start_edit
        )
        self._recalculate_advanced_previews()

    def _card(
        self,
        title: str,
    ):
        frame = QFrame()
        frame.setObjectName(
            "CharacterSectionCard"
        )

        layout = QVBoxLayout(
            frame
        )
        layout.setContentsMargins(
            12, 12, 12, 12
        )
        layout.setSpacing(8)

        label = QLabel(
            title
        )
        label.setObjectName(
            "CharacterCardTitle"
        )
        layout.addWidget(
            label
        )

        return frame, layout

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(
            14, 14, 14, 14
        )
        root.setSpacing(10)

        self.main_splitter = QSplitter(
            Qt.Orientation.Vertical
        )
        self.main_splitter.setObjectName(
            "CharacterMainSplitter"
        )
        root.addWidget(
            self.main_splitter,
            1,
        )

        # ----- top 1/3: portrait + identity -----
        hero = QFrame()
        hero.setObjectName(
            "CharacterHero"
        )
        hero_layout = QHBoxLayout(
            hero
        )
        hero_layout.setContentsMargins(
            16, 14, 16, 14
        )
        hero_layout.setSpacing(16)

        image_column = QVBoxLayout()
        image_column.setSpacing(8)

        self.portrait_label = QLabel(
            "NO IMAGE"
        )
        self.portrait_label.setObjectName(
            "CharacterLargePortrait"
        )
        self.portrait_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.portrait_label.setFixedSize(
            360, 320
        )
        image_column.addWidget(
            self.portrait_label,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )

        self.image_list = ImageListWidget()
        self.image_list.setObjectName(
            "CharacterImageStrip"
        )
        self.image_list.setIconSize(
            QSize(64, 64)
        )
        self.image_list.setViewMode(
            QListView.ViewMode.IconMode
        )
        self.image_list.setFlow(
            QListView.Flow.LeftToRight
        )
        self.image_list.setWrapping(
            False
        )
        self.image_list.setSpacing(
            5
        )
        self.image_list.setFixedHeight(
            0
        )
        self.image_list.setVisible(
            False
        )
        self.image_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self.image_list.setDefaultDropAction(
            Qt.DropAction.MoveAction
        )
        self.image_list.orderChanged.connect(
            self._image_order_changed
        )
        self.image_list.filesDropped.connect(
            self._external_images_dropped
        )
        self.image_list.currentRowChanged.connect(
            self._preview_image_row
        )
        image_column.addWidget(
            self.image_list
        )

        image_select_row = QHBoxLayout()
        image_select_row.setSpacing(8)
        image_select_label = QLabel("表示画像")
        image_select_label.setObjectName("MutedText")
        self.image_combo = QComboBox()
        self.image_combo.setObjectName("CharacterImageCombo")
        self.image_combo.setMinimumWidth(250)
        self.image_combo.currentIndexChanged.connect(
            self._image_combo_changed
        )
        image_select_row.addWidget(image_select_label)
        image_select_row.addWidget(self.image_combo, 1)
        image_column.addLayout(image_select_row)

        image_buttons = QHBoxLayout()
        self.image_add_button = QPushButton(
            "画像を追加"
        )
        self.image_remove_button = QPushButton(
            "削除"
        )
        self.image_up_button = QPushButton("↑")
        self.image_up_button.setToolTip(
            "画像を前へ移動します。先頭画像がMAINです。"
        )
        self.image_down_button = QPushButton("↓")
        self.image_down_button.setToolTip(
            "画像を後ろへ移動します。"
        )
        self.image_add_button.clicked.connect(
            self._add_images_and_preview
        )
        self.image_remove_button.clicked.connect(
            self._remove_image_and_preview
        )
        self.image_up_button.clicked.connect(
            lambda: self._move_image_row(-1)
        )
        self.image_down_button.clicked.connect(
            lambda: self._move_image_row(1)
        )
        image_buttons.addWidget(self.image_add_button)
        image_buttons.addWidget(self.image_remove_button)
        image_buttons.addSpacing(8)
        image_buttons.addWidget(self.image_up_button)
        image_buttons.addWidget(self.image_down_button)
        image_buttons.addStretch(1)
        image_column.addLayout(
            image_buttons
        )

        hero_layout.addLayout(
            image_column
        )

        identity = QVBoxLayout()
        identity.setSpacing(10)

        identity_top = QHBoxLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setObjectName(
            "CharacterNameEdit"
        )
        self.name_edit.setPlaceholderText(
            "キャラクター名"
        )
        self.name_edit.textChanged.connect(
            self._mark_dirty
        )
        identity_top.addWidget(
            self.name_edit,
            1,
        )

        self.mode_switch = QFrame()
        self.mode_switch.setObjectName(
            "CharacterModeSwitch"
        )
        mode_layout = QHBoxLayout(
            self.mode_switch
        )
        mode_layout.setContentsMargins(
            2, 2, 2, 2
        )
        mode_layout.setSpacing(0)

        self.view_mode_button = QPushButton(
            "閲覧"
        )
        self.edit_mode_button = QPushButton(
            "編集"
        )

        for button in (
            self.view_mode_button,
            self.edit_mode_button,
        ):
            button.setObjectName(
                "CharacterModeButton"
            )
            button.setCheckable(
                True
            )
            mode_layout.addWidget(
                button
            )

        self.mode_group = QButtonGroup(
            self
        )
        self.mode_group.setExclusive(
            True
        )
        self.mode_group.addButton(
            self.view_mode_button
        )
        self.mode_group.addButton(
            self.edit_mode_button
        )

        self.view_mode_button.clicked.connect(
            lambda: self.set_edit_mode(False)
        )
        self.edit_mode_button.clicked.connect(
            lambda: self.set_edit_mode(True)
        )

        identity_top.addWidget(
            self.mode_switch
        )
        identity.addLayout(
            identity_top
        )

        player_row = QHBoxLayout()
        player_label = QLabel(
            "Player"
        )
        player_label.setObjectName(
            "MutedText"
        )
        self.player_edit = QLineEdit()
        self.player_edit.setPlaceholderText(
            "プレイヤー名"
        )
        self.player_edit.textChanged.connect(
            self._mark_dirty
        )
        player_row.addWidget(
            player_label
        )
        player_row.addWidget(
            self.player_edit,
            1,
        )
        identity.addLayout(
            player_row
        )

        tag_label = QLabel(
            "タグ"
        )
        tag_label.setObjectName(
            "MutedText"
        )
        identity.addWidget(
            tag_label
        )

        self.tags_edit = TagChipEditor()
        self.tags_edit.tagsChanged.connect(
            self._mark_dirty
        )
        identity.addWidget(
            self.tags_edit
        )

        color_row = QHBoxLayout()
        color_label = QLabel(
            "名前の色"
        )
        color_label.setObjectName(
            "MutedText"
        )
        self.color_edit = QLineEdit()
        self.color_edit.setMaximumWidth(
            120
        )
        self.color_edit.textChanged.connect(
            self._color_changed
        )
        self.color_button = QPushButton(
            "色を選択"
        )
        self.color_button.clicked.connect(
            self._choose_color
        )
        color_row.addWidget(
            color_label
        )
        color_row.addWidget(
            self.color_edit
        )
        color_row.addWidget(
            self.color_button
        )
        color_row.addStretch(1)
        identity.addLayout(
            color_row
        )

        state_row = QHBoxLayout()
        self.save_state = QLabel(
            ""
        )
        self.save_state.setObjectName(
            "SaveState"
        )
        self.autosave_check = QCheckBox(
            "自動保存"
        )
        self.autosave_check.setChecked(
            self.autosave_enabled
        )
        self.autosave_check.toggled.connect(
            self._autosave_setting_changed
        )
        self.save_button = QPushButton(
            "保存"
        )
        self.save_button.setObjectName(
            "PrimaryButton"
        )
        self.save_button.clicked.connect(
            self.save
        )
        state_row.addWidget(
            self.save_state
        )
        state_row.addStretch(1)
        state_row.addWidget(
            self.autosave_check
        )
        state_row.addWidget(
            self.save_button
        )
        identity.addStretch(1)
        identity.addLayout(
            state_row
        )

        hero_layout.addLayout(
            identity,
            1,
        )

        self.main_splitter.addWidget(
            hero
        )

        # ----- lower 2/3: information -----
        lower = QWidget()
        lower_layout = QVBoxLayout(
            lower
        )
        lower_layout.setContentsMargins(
            0, 0, 0, 0
        )
        lower_layout.setSpacing(10)

        overview_grid = QGridLayout()
        overview_grid.setContentsMargins(
            0, 0, 0, 0
        )
        overview_grid.setHorizontalSpacing(
            10
        )
        overview_grid.setVerticalSpacing(
            10
        )

        # Basic information card
        basic_card, basic_layout = self._card(
            "基本情報"
        )
        basic_form = QFormLayout()
        basic_form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        self.initiative_edit = QLineEdit()
        self.external_url_edit = QLineEdit()
        self.export_id_edit = QLineEdit()
        self.export_id_edit.setReadOnly(
            True
        )

        self.secret_check = QCheckBox(
            "シークレット"
        )
        self.invisible_check = QCheckBox(
            "盤面で非表示"
        )
        self.hide_status_check = QCheckBox(
            "ステータスを隠す"
        )

        self.initiative_edit.textChanged.connect(
            self._mark_dirty
        )
        self.external_url_edit.textChanged.connect(
            self._mark_dirty
        )
        self.secret_check.toggled.connect(
            self._mark_dirty
        )
        self.invisible_check.toggled.connect(
            self._mark_dirty
        )
        self.hide_status_check.toggled.connect(
            self._mark_dirty
        )

        flags = QWidget()
        flags_layout = QVBoxLayout(
            flags
        )
        flags_layout.setContentsMargins(
            0, 0, 0, 0
        )
        flags_layout.setSpacing(2)
        flags_layout.addWidget(
            self.secret_check
        )
        flags_layout.addWidget(
            self.invisible_check
        )
        flags_layout.addWidget(
            self.hide_status_check
        )

        basic_form.addRow(
            "イニシアティブ",
            self.initiative_edit,
        )
        basic_form.addRow(
            "外部URL",
            self.external_url_edit,
        )
        basic_form.addRow(
            "CCFOLIA",
            flags,
        )
        basic_form.addRow(
            "Export ID",
            self.export_id_edit,
        )
        basic_layout.addLayout(
            basic_form
        )

        self.template_button = QPushButton(
            "CoC6テンプレートを補完"
        )
        self.template_button.clicked.connect(
            self._apply_coc6_inline
        )
        basic_layout.addWidget(
            self.template_button
        )
        basic_layout.addStretch(1)

        # Status card
        status_card, status_layout = self._card(
            "ステータス"
        )
        self.status_table = QTableWidget(
            0, 3
        )
        self.status_table.setHorizontalHeaderLabels(
            ["名前", "現在", "最大"]
        )
        self._configure_table(
            self.status_table
        )
        self.status_table.setMinimumHeight(215)
        self.status_table.verticalHeader().setDefaultSectionSize(34)
        self.status_table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        self.status_table.itemChanged.connect(
            self._source_table_changed
        )
        status_layout.addWidget(
            self.status_table,
            1,
        )
        status_buttons = QHBoxLayout()
        self.status_add_button = QPushButton(
            "+"
        )
        self.status_remove_button = QPushButton(
            "−"
        )
        self.status_add_button.clicked.connect(
            lambda: self._add_table_row(
                self.status_table,
                3,
            )
        )
        self.status_remove_button.clicked.connect(
            lambda: self._remove_table_row(
                self.status_table
            )
        )
        status_buttons.addWidget(
            self.status_add_button
        )
        status_buttons.addWidget(
            self.status_remove_button
        )
        status_buttons.addStretch(1)
        status_layout.addLayout(
            status_buttons
        )

        # Params card
        params_card, params_layout = self._card(
            "パラメータ"
        )
        self.params_table = QTableWidget(
            0, 2
        )
        self.params_table.setHorizontalHeaderLabels(
            ["名前", "値"]
        )
        self._configure_table(
            self.params_table
        )
        self.params_table.setMinimumHeight(215)
        self.params_table.verticalHeader().setDefaultSectionSize(34)
        self.params_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.params_table.itemChanged.connect(
            self._source_table_changed
        )
        params_layout.addWidget(
            self.params_table,
            1,
        )
        params_buttons = QHBoxLayout()
        self.params_add_button = QPushButton(
            "+"
        )
        self.params_remove_button = QPushButton(
            "−"
        )
        self.params_add_button.clicked.connect(
            lambda: self._add_table_row(
                self.params_table,
                2,
            )
        )
        self.params_remove_button.clicked.connect(
            lambda: self._remove_table_row(
                self.params_table
            )
        )
        params_buttons.addWidget(
            self.params_add_button
        )
        params_buttons.addWidget(
            self.params_remove_button
        )
        params_buttons.addStretch(1)
        params_layout.addLayout(
            params_buttons
        )

        # Derived card
        derived_card, derived_layout = self._card(
            "派生ステータス"
        )
        self.derived_table = QTableWidget(
            0, 4
        )
        self.derived_table.setHorizontalHeaderLabels(
            ["名前", "式", "結果", "エラー"]
        )
        self._configure_table(
            self.derived_table
        )
        self.derived_table.setMinimumHeight(215)
        self.derived_table.verticalHeader().setDefaultSectionSize(34)
        derived_header = self.derived_table.horizontalHeader()
        derived_header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        derived_header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        derived_header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        derived_header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        self.derived_table.itemChanged.connect(
            self._derived_changed_inline
        )
        derived_layout.addWidget(
            self.derived_table,
            1,
        )
        derived_buttons = QHBoxLayout()
        self.derived_add_button = QPushButton(
            "+"
        )
        self.derived_remove_button = QPushButton(
            "−"
        )
        self.derived_add_button.clicked.connect(
            self._add_derived_inline
        )
        self.derived_remove_button.clicked.connect(
            self._remove_derived_inline
        )
        derived_buttons.addWidget(
            self.derived_add_button
        )
        derived_buttons.addWidget(
            self.derived_remove_button
        )
        derived_buttons.addStretch(1)
        derived_layout.addLayout(
            derived_buttons
        )

        basic_card.setMinimumWidth(260)
        status_card.setMinimumWidth(280)
        params_card.setMinimumWidth(260)
        derived_card.setMinimumWidth(350)

        self.overview_splitter = QSplitter(
            Qt.Orientation.Horizontal
        )
        self.overview_splitter.setObjectName(
            "CharacterOverviewSplitter"
        )
        self.overview_splitter.setChildrenCollapsible(False)
        self.overview_splitter.setMinimumHeight(315)
        self.overview_splitter.addWidget(basic_card)
        self.overview_splitter.addWidget(status_card)
        self.overview_splitter.addWidget(params_card)
        self.overview_splitter.addWidget(derived_card)
        self.overview_splitter.setSizes([300, 340, 300, 430])

        lower_layout.addWidget(self.overview_splitter, 3)

        self.detail_tabs = QTabWidget()
        self.detail_tabs.setObjectName(
            "CharacterDetailTabs"
        )
        self.detail_tabs.setMinimumHeight(300)
        lower_layout.addWidget(
            self.detail_tabs,
            2,
        )
        # PHASE21_FIX2_RUNTIME
        # Export ID は同じCCFOLIA駒を更新するための内部識別子。
        # 普段のキャラクター編集では表示しない。
        try:
            basic_form.setRowVisible(
                self.export_id_edit,
                False,
            )
        except Exception:
            label = basic_form.labelForField(
                self.export_id_edit
            )
            if label is not None:
                label.setVisible(False)
            self.export_id_edit.setVisible(False)

        # 概要は少しコンパクトにし、技能・メモ等へ高さを回す。
        self.overview_splitter.setMinimumHeight(205)

        for table in (
            self.status_table,
            self.params_table,
            self.derived_table,
        ):
            table.setMinimumHeight(140)

        self.detail_tabs.setMinimumHeight(360)

        # 既存の個別配置を外して、概要と詳細を縦Splitterへまとめる。
        lower_layout.removeWidget(
            self.overview_splitter
        )
        lower_layout.removeWidget(
            self.detail_tabs
        )

        self.lower_splitter = QSplitter(
            Qt.Orientation.Vertical
        )
        self.lower_splitter.setObjectName(
            "CharacterLowerSplitter"
        )
        self.lower_splitter.setChildrenCollapsible(False)

        self.lower_splitter.addWidget(
            self.overview_splitter
        )
        self.lower_splitter.addWidget(
            self.detail_tabs
        )
        self.lower_splitter.setSizes(
            [220, 455]
        )

        lower_layout.addWidget(
            self.lower_splitter,
            1,
        )

        self.main_splitter.setSizes(
            [380, 700]
        )


        # Skills
        skills_tab = QWidget()
        skills_layout = QVBoxLayout(
            skills_tab
        )
        self.skills_editor = SkillBlockEditor()
        self.skills_editor.changed.connect(
            self._skills_changed_inline
        )
        skills_layout.addWidget(
            self.skills_editor
        )
        self.detail_tabs.addTab(
            skills_tab,
            "技能",
        )

        # Memo
        memo_tab = QWidget()
        memo_layout = QHBoxLayout(
            memo_tab
        )
        memo_splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        memo_left = QWidget()
        memo_left_layout = QVBoxLayout(
            memo_left
        )
        memo_left_layout.setContentsMargins(
            0, 0, 0, 0
        )
        self.memo_list = QListWidget()
        self.memo_list.currentRowChanged.connect(
            self._memo_selection_changed
        )
        memo_left_layout.addWidget(
            self.memo_list
        )
        memo_buttons = QHBoxLayout()
        self.memo_add_button = QPushButton(
            "追加"
        )
        self.memo_remove_button = QPushButton(
            "削除"
        )
        self.memo_add_button.clicked.connect(
            self._add_memo
        )
        self.memo_remove_button.clicked.connect(
            self._remove_memo
        )
        memo_buttons.addWidget(
            self.memo_add_button
        )
        memo_buttons.addWidget(
            self.memo_remove_button
        )
        memo_left_layout.addLayout(
            memo_buttons
        )

        memo_right = QWidget()
        memo_right_layout = QVBoxLayout(
            memo_right
        )
        memo_right_layout.setContentsMargins(
            0, 0, 0, 0
        )
        self.memo_title = QLineEdit()
        self.memo_title.setPlaceholderText(
            "メモのタイトル"
        )
        self.memo_private = QCheckBox(
            "ココフォリアへ出力"
        )
        self.memo_body = QTextEdit()
        self.memo_body.setPlaceholderText(
            "メモ本文"
        )
        self.memo_title.textChanged.connect(
            self._memo_edited
        )
        self.memo_private.toggled.connect(
            self._memo_edited
        )
        self.memo_body.textChanged.connect(
            self._memo_edited
        )
        memo_right_layout.addWidget(
            self.memo_title
        )
        memo_right_layout.addWidget(
            self.memo_private
        )
        memo_right_layout.addWidget(
            self.memo_body
        )

        memo_splitter.addWidget(
            memo_left
        )
        memo_splitter.addWidget(
            memo_right
        )
        memo_splitter.setSizes(
            [240, 700]
        )
        memo_layout.addWidget(
            memo_splitter
        )
        self.detail_tabs.addTab(
            memo_tab,
            "メモ",
        )

        # Chat palette
        palette_tab = QWidget()
        palette_layout = QHBoxLayout(
            palette_tab
        )
        palette_splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        palette_left = QWidget()
        palette_left_layout = QVBoxLayout(
            palette_left
        )
        palette_left_layout.setContentsMargins(
            0, 0, 0, 0
        )
        self.palette_list = QListWidget()
        self.palette_list.currentRowChanged.connect(
            self._palette_selected_inline
        )
        palette_left_layout.addWidget(
            self.palette_list
        )
        palette_buttons = QHBoxLayout()
        self.palette_add_button = QPushButton(
            "追加"
        )
        self.palette_remove_button = QPushButton(
            "削除"
        )
        self.palette_add_button.clicked.connect(
            self._add_palette_inline
        )
        self.palette_remove_button.clicked.connect(
            self._remove_palette_inline
        )
        palette_buttons.addWidget(
            self.palette_add_button
        )
        palette_buttons.addWidget(
            self.palette_remove_button
        )
        palette_left_layout.addLayout(
            palette_buttons
        )

        palette_right = QWidget()
        palette_right_layout = QVBoxLayout(
            palette_right
        )
        palette_right_layout.setContentsMargins(
            0, 0, 0, 0
        )
        palette_name_row = QHBoxLayout()
        self.palette_name = QLineEdit()
        self.palette_name.setPlaceholderText(
            "パレット名"
        )
        self.palette_mode = QComboBox()
        self.palette_mode.addItem(
            "通常", "normal"
        )
        self.palette_mode.addItem(
            "KP", "kp"
        )
        self.palette_generate_button = QPushButton(
            "CoC6基本パレット生成"
        )
        self.palette_generate_button.clicked.connect(
            self._generate_palette_inline
        )
        palette_name_row.addWidget(
            self.palette_name, 1
        )
        palette_name_row.addWidget(
            self.palette_mode
        )
        palette_name_row.addWidget(
            self.palette_generate_button
        )
        self.palette_content = QTextEdit()
        self.palette_content.setPlaceholderText(
            "チャットパレット本文"
        )
        self.palette_name.textChanged.connect(
            self._palette_edited_inline
        )
        self.palette_mode.currentIndexChanged.connect(
            self._palette_edited_inline
        )
        self.palette_content.textChanged.connect(
            self._palette_edited_inline
        )
        palette_right_layout.addLayout(
            palette_name_row
        )
        palette_right_layout.addWidget(
            self.palette_content
        )

        palette_splitter.addWidget(
            palette_left
        )
        palette_splitter.addWidget(
            palette_right
        )
        palette_splitter.setSizes(
            [240, 700]
        )
        palette_layout.addWidget(
            palette_splitter
        )
        self.detail_tabs.addTab(
            palette_tab,
            "チャットパレット",
        )

        # Classification
        class_tab = QWidget()
        class_layout = QVBoxLayout(
            class_tab
        )
        class_note = QLabel(
            "タグは画面上部で編集できます。ここでは所属グループを管理します。"
        )
        class_note.setObjectName(
            "MutedText"
        )
        self.group_tree = QTreeWidget()
        self.group_tree.setHeaderHidden(
            True
        )
        self.group_tree.setIndentation(
            18
        )
        self.group_tree.itemChanged.connect(
            self._group_check_changed
        )
        class_layout.addWidget(
            class_note
        )
        class_layout.addWidget(
            self.group_tree
        )
        self.detail_tabs.addTab(
            class_tab,
            "分類",
        )

        self.main_splitter.addWidget(
            lower
        )
        self.main_splitter.setSizes(
            [400, 610]
        )
        self.main_splitter.setStretchFactor(
            0, 0
        )
        self.main_splitter.setStretchFactor(
            1, 1
        )

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        close_button = QPushButton(
            "閉じる"
        )
        close_button.clicked.connect(
            self.close
        )
        bottom.addWidget(
            close_button
        )
        root.addLayout(
            bottom
        )

    def _load(self):
        _LegacyCharacterEditorDialog._load(
            self
        )

        advanced = load_advanced_bundle(
            self.character_id
        )

        self.derived_table.blockSignals(
            True
        )
        self.derived_table.setRowCount(
            0
        )

        for row in advanced[
            "derived"
        ]:
            self._append_derived_inline(
                row["label"],
                row["formula"],
                row["last_value"],
                row["error"],
            )

        self.derived_table.blockSignals(
            False
        )

        self.skills_editor.set_skills(
            advanced["skills"]
        )

        self.palette_records = [
            {
                "name": row["name"],
                "mode": row["mode"],
                "content": row["content"],
            }
            for row in advanced[
                "palettes"
            ]
        ]
        self._refresh_palette_list_inline(
            0
            if self.palette_records
            else -1
        )

        if self.image_list.count():
            self.image_list.setCurrentRow(0)
            self._refresh_image_combo(0)
        else:
            self._refresh_image_combo(-1)
            self._preview_image_row(-1)

        self._apply_name_color()
        self._recalculate_advanced_previews()

    def _color_changed(self, *args):
        self._apply_name_color()
        self._mark_dirty()

    def _apply_name_color(self):
        color = QColor(
            self.color_edit.text().strip()
        )

        if not color.isValid():
            color = QColor(
                "#e8e8ec"
            )

        self.name_edit.setStyleSheet(
            f"color: {color.name()};"
        )

    def _refresh_image_combo(
        self,
        selected_row: int | None = None,
    ):
        if not hasattr(self, "image_combo"):
            return

        if selected_row is None:
            selected_row = self.image_list.currentRow()

        self.image_combo.blockSignals(True)
        self.image_combo.clear()

        for row in range(self.image_list.count()):
            item = self.image_list.item(row)
            data = item.data(
                Qt.ItemDataRole.UserRole
            ) or {}

            label = str(
                data.get("label", "")
                or ""
            ).strip()

            if row == 0:
                display = (
                    f"MAIN · {label}"
                    if label
                    else "MAIN"
                )
            else:
                display = (
                    f"差分 {row + 1} · {label}"
                    if label
                    else f"差分 {row + 1}"
                )

            self.image_combo.addItem(
                display,
                row,
            )

        if self.image_combo.count():
            selected_row = max(
                0,
                min(
                    selected_row,
                    self.image_combo.count() - 1,
                ),
            )
            self.image_combo.setCurrentIndex(
                selected_row
            )

        self.image_combo.blockSignals(False)

        if hasattr(
            self,
            "_update_image_move_buttons",
        ):
            self._update_image_move_buttons()

    def _image_combo_changed(
        self,
        index: int,
    ):
        if not (
            0 <= index < self.image_list.count()
        ):
            self._preview_image_row(-1)
            self._update_image_move_buttons()
            return

        self.image_list.setCurrentRow(index)
        self._preview_image_row(index)
        self._update_image_move_buttons()

    def _update_image_move_buttons(self):
        if not hasattr(self, "image_up_button"):
            return

        row = (
            self.image_combo.currentIndex()
            if hasattr(self, "image_combo")
            else -1
        )
        count = self.image_list.count()

        self.image_up_button.setEnabled(
            self._edit_mode
            and 0 < row < count
        )
        self.image_down_button.setEnabled(
            self._edit_mode
            and 0 <= row < count - 1
        )

    def _move_image_row(
        self,
        delta: int,
    ):
        if not self._edit_mode:
            return

        row = self.image_combo.currentIndex()
        target = row + delta

        if not (
            0 <= row < self.image_list.count()
            and 0 <= target < self.image_list.count()
        ):
            return

        item = self.image_list.takeItem(row)
        self.image_list.insertItem(
            target,
            item,
        )
        self.image_list.setCurrentRow(
            target
        )

        self._refresh_image_combo(target)
        self._preview_image_row(target)
        self._mark_dirty()

    def _preview_image_row(
        self,
        row: int,
    ):
        self.portrait_label.clear()

        if not (
            0 <= row < self.image_list.count()
        ):
            self.portrait_label.setText(
                "NO IMAGE"
            )
            return

        item = self.image_list.item(
            row
        )
        data = item.data(
            Qt.ItemDataRole.UserRole
        )

        if not data:
            self.portrait_label.setText(
                "NO IMAGE"
            )
            return

        path = PROJECT_ROOT / data[
            "relative_path"
        ]

        if not path.exists():
            self.portrait_label.setText(
                "NO IMAGE"
            )
            return

        pixmap = QPixmap(
            str(path)
        )

        if pixmap.isNull():
            self.portrait_label.setText(
                "NO IMAGE"
            )
            return

        self.portrait_label.setPixmap(
            pixmap.scaled(
                self.portrait_label.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )

    def _image_order_changed(self):
        row = self.image_list.currentRow()
        self._mark_dirty()
        self._refresh_image_combo(row)
        self._preview_image_row(row)

    def _add_images_and_preview(self):
        before = self.image_list.count()
        self._add_images()

        if self.image_list.count() > before:
            row = self.image_list.count() - 1
            self.image_list.setCurrentRow(row)
            self._refresh_image_combo(row)
            self._preview_image_row(row)

    def _remove_image_and_preview(self):
        self._remove_selected_image()
        row = min(
            self.image_list.currentRow(),
            self.image_list.count() - 1,
        )

        if self.image_list.count():
            row = max(0, row)
            self.image_list.setCurrentRow(row)
            self._refresh_image_combo(row)
            self._preview_image_row(row)
        else:
            self._refresh_image_combo(-1)
            self._preview_image_row(-1)

    def _readonly_item_inline(
        self,
        text="",
    ):
        item = QTableWidgetItem(
            str(text)
        )
        item.setFlags(
            item.flags()
            & ~Qt.ItemFlag.ItemIsEditable
        )
        return item

    def _append_derived_inline(
        self,
        label="",
        formula="",
        result="",
        error="",
    ):
        row = self.derived_table.rowCount()
        self.derived_table.insertRow(
            row
        )
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
            row, 2, self._readonly_item_inline(result)
        )
        self.derived_table.setItem(
            row, 3, self._readonly_item_inline(error)
        )

    def _add_derived_inline(self):
        self.derived_table.blockSignals(
            True
        )
        self._append_derived_inline()
        self.derived_table.blockSignals(
            False
        )
        row = self.derived_table.rowCount() - 1
        self.derived_table.setCurrentCell(
            row, 0
        )
        self._mark_dirty()

    def _remove_derived_inline(self):
        row = self.derived_table.currentRow()

        if row < 0:
            return

        self.derived_table.removeRow(
            row
        )
        self._mark_dirty()
        self._recalculate_advanced_previews()

    def _derived_changed_inline(
        self,
        item,
    ):
        if self.loading:
            return

        if item.column() in (0, 1):
            self._recalculate_advanced_previews()
            self._mark_dirty()

    def _source_table_changed(
        self,
        *args,
    ):
        if self.loading:
            return

        self._recalculate_advanced_previews()
        self._mark_dirty()

    def _skills_changed_inline(
        self,
        *args,
    ):
        if self.loading:
            return

        self._recalculate_advanced_previews()
        self._mark_dirty()

    def _current_source_values(self):
        output = {}

        for values in self._table_rows(
            self.params_table
        ):
            label = values[0].strip()

            if label:
                output[label] = values[1]

        for values in self._table_rows(
            self.status_table
        ):
            label = values[0].strip()

            if (
                label
                and label not in output
            ):
                output[label] = values[1]

        return output

    def _recalculate_advanced_previews(self):
        if self.loading:
            return

        source_values = self._current_source_values()

        self.derived_table.blockSignals(
            True
        )

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

            result_item = self.derived_table.item(
                row, 2
            )
            error_item = self.derived_table.item(
                row, 3
            )

            if result_item is None:
                result_item = self._readonly_item_inline()
                self.derived_table.setItem(
                    row, 2, result_item
                )

            if error_item is None:
                error_item = self._readonly_item_inline()
                self.derived_table.setItem(
                    row, 3, error_item
                )

            result_item.setText(
                str(result)
            )
            error_item.setText(
                error
            )

        self.derived_table.blockSignals(
            False
        )

        self.skills_editor.refresh_previews(
            source_values
        )

    def _collect_derived_inline(self):
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

    def _refresh_palette_list_inline(
        self,
        select_row=-1,
    ):
        self.palette_list.blockSignals(
            True
        )
        self.palette_list.clear()

        for record in self.palette_records:
            name = record[
                "name"
            ].strip() or "無題"
            mode = record.get(
                "mode",
                "normal",
            )

            if mode == "kp":
                name = f"KP: {name}"

            self.palette_list.addItem(
                name
            )

        self.palette_list.blockSignals(
            False
        )

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
            self._show_palette_inline(
                -1
            )

    def _palette_selected_inline(
        self,
        row,
    ):
        self._show_palette_inline(
            row
        )

    def _show_palette_inline(
        self,
        row,
    ):
        old_loading = self.loading
        self.loading = True
        enabled = (
            0 <= row
            < len(self.palette_records)
        )

        if enabled:
            record = self.palette_records[
                row
            ]
            self.palette_name.setText(
                record["name"]
            )
            index = self.palette_mode.findData(
                record.get(
                    "mode",
                    "normal",
                )
            )
            self.palette_mode.setCurrentIndex(
                max(0, index)
            )
            self.palette_content.setPlainText(
                record["content"]
            )
        else:
            self.palette_name.clear()
            self.palette_mode.setCurrentIndex(
                0
            )
            self.palette_content.clear()

        self.loading = old_loading
        self._apply_edit_mode_to_palette()

    def _palette_edited_inline(
        self,
        *args,
    ):
        if self.loading:
            return

        row = self.palette_list.currentRow()

        if not (
            0 <= row
            < len(self.palette_records)
        ):
            return

        self.palette_records[row] = {
            "name": self.palette_name.text(),
            "mode": self.palette_mode.currentData()
            or "normal",
            "content": self.palette_content.toPlainText(),
        }

        label = (
            self.palette_name.text().strip()
            or "無題"
        )

        if self.palette_mode.currentData() == "kp":
            label = f"KP: {label}"

        self.palette_list.item(
            row
        ).setText(
            label
        )
        self._mark_dirty()

    def _add_palette_inline(self):
        self.palette_records.append(
            {
                "name": "新しいパレット",
                "mode": "normal",
                "content": "",
            }
        )
        self._refresh_palette_list_inline(
            len(self.palette_records) - 1
        )
        self._mark_dirty()

    def _remove_palette_inline(self):
        row = self.palette_list.currentRow()

        if not (
            0 <= row
            < len(self.palette_records)
        ):
            return

        del self.palette_records[row]
        next_row = min(
            row,
            len(self.palette_records) - 1,
        )
        self._refresh_palette_list_inline(
            next_row
        )
        self._mark_dirty()

    def _generate_palette_inline(self):
        if self.dirty:
            if not self.save(
                show_error=True
            ):
                return

        content = generate_coc6_palette(
            self.character_id
        )

        self.palette_records.append(
            {
                "name": "CoC6基本",
                "mode": "normal",
                "content": content,
            }
        )
        self._refresh_palette_list_inline(
            len(self.palette_records) - 1
        )
        self._mark_dirty()

    def _apply_coc6_inline(self):
        if self.dirty:
            if not self.save(
                show_error=True
            ):
                return

        try:
            apply_coc6_template(
                self.character_id
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "CoC6テンプレート",
                str(exc),
            )
            return

        self.loading = True
        self._load()
        self.loading = False
        self._recalculate_advanced_previews()
        self._set_save_state(
            "保存済み"
        )
        self.saved.emit()
        self.changed.emit()

    def _refresh_memo_list(
        self,
        select_row: int = -1,
    ):
        self.memo_list.blockSignals(
            True
        )
        self.memo_list.clear()

        for memo in self.memo_records:
            title = (
                memo["title"].strip()
                or "無題"
            )

            if memo["private"]:
                title = f"{title}  [管理用]"

            self.memo_list.addItem(
                title
            )

        self.memo_list.blockSignals(
            False
        )

        if (
            0 <= select_row
            < len(self.memo_records)
        ):
            self.memo_list.setCurrentRow(
                select_row
            )
        else:
            self.memo_list.setCurrentRow(
                -1
            )
            self._show_memo(
                -1
            )

    def _show_memo(
        self,
        row: int,
    ):
        old_loading = self.loading
        self.loading = True
        enabled = (
            0 <= row
            < len(self.memo_records)
        )

        if enabled:
            memo = self.memo_records[
                row
            ]
            self.memo_title.setText(
                memo["title"]
            )
            self.memo_private.setChecked(
                not memo["private"]
            )
            self.memo_body.setPlainText(
                memo["body"]
            )
        else:
            self.memo_title.clear()
            self.memo_private.setChecked(
                False
            )
            self.memo_body.clear()

        self.loading = old_loading
        self._apply_edit_mode_to_memo()

    def _memo_edited(self):
        if self.loading:
            return

        row = self.memo_list.currentRow()

        if not (
            0 <= row
            < len(self.memo_records)
        ):
            return

        self.memo_records[row] = {
            "title": self.memo_title.text(),
            "body": self.memo_body.toPlainText(),
            "private": not self.memo_private.isChecked(),
        }

        label = (
            self.memo_title.text().strip()
            or "無題"
        )

        if not self.memo_private.isChecked():
            label = f"{label}  [管理用]"

        self.memo_list.item(
            row
        ).setText(
            label
        )
        self._mark_dirty()

    def _apply_edit_mode_to_memo(self):
        has_memo = (
            0 <= self.memo_list.currentRow()
            < len(self.memo_records)
        )
        editable = (
            self._edit_mode
            and has_memo
        )
        self.memo_title.setReadOnly(
            not editable
        )
        self.memo_private.setEnabled(
            editable
        )
        self.memo_body.setReadOnly(
            not editable
        )

    def _apply_edit_mode_to_palette(self):
        has_palette = (
            0 <= self.palette_list.currentRow()
            < len(self.palette_records)
        )
        editable = (
            self._edit_mode
            and has_palette
        )
        self.palette_name.setReadOnly(
            not editable
        )
        self.palette_mode.setEnabled(
            editable
        )
        self.palette_content.setReadOnly(
            not editable
        )

    def set_edit_mode(
        self,
        edit_mode: bool,
    ):
        self._edit_mode = bool(
            edit_mode
        )

        self.view_mode_button.blockSignals(
            True
        )
        self.edit_mode_button.blockSignals(
            True
        )
        self.view_mode_button.setChecked(
            not self._edit_mode
        )
        self.edit_mode_button.setChecked(
            self._edit_mode
        )
        self.view_mode_button.blockSignals(
            False
        )
        self.edit_mode_button.blockSignals(
            False
        )

        for widget in (
            self.name_edit,
            self.player_edit,
            self.initiative_edit,
            self.external_url_edit,
            self.color_edit,
        ):
            widget.setReadOnly(
                not self._edit_mode
            )

        for widget in (
            self.secret_check,
            self.invisible_check,
            self.hide_status_check,
            self.autosave_check,
        ):
            widget.setEnabled(
                self._edit_mode
            )

        self.tags_edit.setEnabled(
            self._edit_mode
        )
        self.group_tree.setEnabled(
            self._edit_mode
        )

        for table in (
            self.status_table,
            self.params_table,
            self.derived_table,
        ):
            table.setEditTriggers(
                QAbstractItemView.EditTrigger.AllEditTriggers
                if self._edit_mode
                else QAbstractItemView.EditTrigger.NoEditTriggers
            )

        self.skills_editor.setEnabled(
            self._edit_mode
        )

        self.image_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
            if self._edit_mode
            else QAbstractItemView.DragDropMode.NoDragDrop
        )
        self.image_list.setAcceptDrops(
            self._edit_mode
        )

        for widget in (
            self.color_button,
            self.image_add_button,
            self.image_remove_button,
            self.image_up_button,
            self.image_down_button,
            self.status_add_button,
            self.status_remove_button,
            self.params_add_button,
            self.params_remove_button,
            self.derived_add_button,
            self.derived_remove_button,
            self.template_button,
            self.memo_add_button,
            self.memo_remove_button,
            self.palette_add_button,
            self.palette_remove_button,
            self.palette_generate_button,
            self.save_button,
            self.autosave_check,
        ):
            widget.setVisible(
                self._edit_mode
            )

        self._apply_edit_mode_to_memo()
        self._apply_edit_mode_to_palette()
        self._update_image_move_buttons()

        self.name_edit.setProperty(
            "viewMode",
            not self._edit_mode,
        )
        self.name_edit.style().unpolish(
            self.name_edit
        )
        self.name_edit.style().polish(
            self.name_edit
        )

    def save(
        self,
        show_error: bool = True,
    ) -> bool:
        self._set_save_state(
            "保存中…"
        )

        try:
            save_character_bundle(
                self.character_id,
                {
                    "name": self.name_edit.text(),
                    "player_name": self.player_edit.text(),
                    "initiative": self.initiative_edit.text(),
                    "external_url": self.external_url_edit.text(),
                    "color": self.color_edit.text().strip()
                    or "#888888",
                    "secret": self.secret_check.isChecked(),
                    "invisible": self.invisible_check.isChecked(),
                    "hide_status": self.hide_status_check.isChecked(),
                },
                self._collect_images(),
                self._collect_statuses(),
                self._collect_params(),
                list(self.memo_records),
                self._collect_tag_names(),
                self._collect_group_ids(),
            )

            save_advanced_bundle(
                self.character_id,
                self._collect_derived_inline(),
                self.skills_editor.skills(),
                list(self.palette_records),
            )
        except Exception as exc:
            self._set_save_state(
                "保存エラー"
            )

            if show_error:
                QMessageBox.warning(
                    self,
                    "保存できません",
                    str(exc),
                )

            return False

        self.dirty = False
        self._set_save_state(
            "保存済み"
        )
        self.saved.emit()
        self.changed.emit()
        self._setup_tag_completer()
        self._recalculate_advanced_previews()
        return True


class CharacterEditorDialog(UnifiedCharacterDialog):
    def __init__(
        self,
        character_id: str,
        parent=None,
    ):
        super().__init__(
            character_id,
            parent,
            start_edit=True,
        )


CharacterViewDialog = UnifiedCharacterDialog

# ---------------------------------------------------------------------------
# Phase 22B: rule-aware seven-tab character editor
# ---------------------------------------------------------------------------

from app.services.settings_service import (
    get_bool_setting as get_bool_setting_v22,
)
from app.services.rule_templates import (
    list_rule_templates,
)
from app.services.rule_formula_engine import (
    FormulaError as RuleFormulaError,
    evaluate_formula as evaluate_rule_formula,
    format_formula_value,
)
from app.services.v22_character_service import (
    apply_template_v22,
    generate_coc6_palette_v22,
    load_v22_bundle,
    reset_status_initial_values,
    save_skills_and_palettes,
    save_v22_bundle,
)


class Phase22BCharacterDialog(UnifiedCharacterDialog):
    def __init__(
        self,
        character_id: str,
        parent=None,
        start_edit: bool = False,
    ):
        self._v22_start_edit = bool(
            start_edit
        )
        self._developer_mode = get_bool_setting_v22(
            "developer_mode",
            False,
        )
        self._template_id = ""
        super().__init__(
            character_id,
            parent,
            start_edit=start_edit,
        )

        self.setWindowTitle(
            "キャラクター"
        )
        self.resize(
            1480,
            980,
        )
        self.setMinimumSize(
            1100,
            760,
        )

    def _build_ui(self):
        root = QVBoxLayout(
            self
        )
        root.setContentsMargins(
            14,
            14,
            14,
            14,
        )
        root.setSpacing(
            10
        )

        self.main_splitter = QSplitter(
            Qt.Orientation.Vertical
        )
        self.main_splitter.setObjectName(
            "CharacterMainSplitter"
        )
        self.main_splitter.setChildrenCollapsible(
            False
        )
        root.addWidget(
            self.main_splitter,
            1,
        )

        # -------------------------------------------------------
        # Hero: image + identity.  This stays visible on every tab.
        # -------------------------------------------------------
        hero = QFrame()
        hero.setObjectName(
            "CharacterHero"
        )
        hero_layout = QHBoxLayout(
            hero
        )
        hero_layout.setContentsMargins(
            16,
            14,
            16,
            14,
        )
        hero_layout.setSpacing(
            18
        )

        image_column = QVBoxLayout()
        image_column.setSpacing(
            8
        )

        self.portrait_label = QLabel(
            "NO IMAGE"
        )
        self.portrait_label.setObjectName(
            "CharacterLargePortrait"
        )
        self.portrait_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.portrait_label.setFixedSize(
            350,
            285,
        )
        image_column.addWidget(
            self.portrait_label,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )

        # Hidden backing list keeps the existing image-copy/order logic.
        self.image_list = ImageListWidget()
        self.image_list.setVisible(
            False
        )
        self.image_list.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        self.image_list.setDefaultDropAction(
            Qt.DropAction.MoveAction
        )
        self.image_list.orderChanged.connect(
            self._image_order_changed
        )
        self.image_list.filesDropped.connect(
            self._external_images_dropped
        )
        self.image_list.currentRowChanged.connect(
            self._preview_image_row
        )

        image_select_row = QHBoxLayout()
        image_select_row.setSpacing(
            8
        )

        image_label = QLabel(
            "表示画像"
        )
        image_label.setObjectName(
            "MutedText"
        )

        self.image_combo = QComboBox()
        self.image_combo.setObjectName(
            "CharacterImageCombo"
        )
        self.image_combo.setMinimumWidth(
            250
        )
        self.image_combo.currentIndexChanged.connect(
            self._image_combo_changed
        )

        image_select_row.addWidget(
            image_label
        )
        image_select_row.addWidget(
            self.image_combo,
            1,
        )
        image_column.addLayout(
            image_select_row
        )

        image_buttons = QHBoxLayout()

        self.image_add_button = QPushButton(
            "画像を追加"
        )
        self.image_remove_button = QPushButton(
            "削除"
        )
        self.image_up_button = QPushButton(
            "↑"
        )
        self.image_down_button = QPushButton(
            "↓"
        )

        self.image_up_button.setToolTip(
            "画像を前へ移動します。先頭画像がMAINです。"
        )
        self.image_down_button.setToolTip(
            "画像を後ろへ移動します。"
        )

        self.image_add_button.clicked.connect(
            self._add_images_and_preview
        )
        self.image_remove_button.clicked.connect(
            self._remove_image_and_preview
        )
        self.image_up_button.clicked.connect(
            lambda: self._move_image_row(-1)
        )
        self.image_down_button.clicked.connect(
            lambda: self._move_image_row(1)
        )

        image_buttons.addWidget(
            self.image_add_button
        )
        image_buttons.addWidget(
            self.image_remove_button
        )
        image_buttons.addSpacing(
            8
        )
        image_buttons.addWidget(
            self.image_up_button
        )
        image_buttons.addWidget(
            self.image_down_button
        )
        image_buttons.addStretch(
            1
        )

        image_column.addLayout(
            image_buttons
        )

        hero_layout.addLayout(
            image_column
        )

        identity = QVBoxLayout()
        identity.setSpacing(
            10
        )

        top_row = QHBoxLayout()

        self.name_edit = QLineEdit()
        self.name_edit.setObjectName(
            "CharacterNameEdit"
        )
        self.name_edit.setPlaceholderText(
            "キャラクター名"
        )
        self.name_edit.textChanged.connect(
            self._mark_dirty
        )
        top_row.addWidget(
            self.name_edit,
            1,
        )

        self.mode_switch = QFrame()
        self.mode_switch.setObjectName(
            "CharacterModeSwitch"
        )
        mode_layout = QHBoxLayout(
            self.mode_switch
        )
        mode_layout.setContentsMargins(
            2,
            2,
            2,
            2,
        )
        mode_layout.setSpacing(
            0
        )

        self.view_mode_button = QPushButton(
            "閲覧"
        )
        self.edit_mode_button = QPushButton(
            "編集"
        )

        for button in (
            self.view_mode_button,
            self.edit_mode_button,
        ):
            button.setObjectName(
                "CharacterModeButton"
            )
            button.setCheckable(
                True
            )
            mode_layout.addWidget(
                button
            )

        self.mode_group = QButtonGroup(
            self
        )
        self.mode_group.setExclusive(
            True
        )
        self.mode_group.addButton(
            self.view_mode_button
        )
        self.mode_group.addButton(
            self.edit_mode_button
        )

        self.view_mode_button.clicked.connect(
            lambda: self.set_edit_mode(
                False
            )
        )
        self.edit_mode_button.clicked.connect(
            lambda: self.set_edit_mode(
                True
            )
        )

        top_row.addWidget(
            self.mode_switch
        )
        identity.addLayout(
            top_row
        )

        player_row = QHBoxLayout()
        player_label = QLabel(
            "Player"
        )
        player_label.setObjectName(
            "MutedText"
        )
        self.player_edit = QLineEdit()
        self.player_edit.setPlaceholderText(
            "プレイヤー名"
        )
        self.player_edit.textChanged.connect(
            self._mark_dirty
        )
        player_row.addWidget(
            player_label
        )
        player_row.addWidget(
            self.player_edit,
            1,
        )
        identity.addLayout(
            player_row
        )

        tag_label = QLabel(
            "タグ"
        )
        tag_label.setObjectName(
            "MutedText"
        )
        identity.addWidget(
            tag_label
        )

        self.tags_edit = TagChipEditor()
        self.tags_edit.tagsChanged.connect(
            self._mark_dirty
        )
        identity.addWidget(
            self.tags_edit
        )

        color_row = QHBoxLayout()
        color_label = QLabel(
            "名前の色"
        )
        color_label.setObjectName(
            "MutedText"
        )
        self.color_edit = QLineEdit()
        self.color_edit.setMaximumWidth(
            125
        )
        self.color_edit.textChanged.connect(
            self._color_changed
        )
        self.color_button = QPushButton(
            "色を選択"
        )
        self.color_button.clicked.connect(
            self._choose_color
        )

        color_row.addWidget(
            color_label
        )
        color_row.addWidget(
            self.color_edit
        )
        color_row.addWidget(
            self.color_button
        )
        color_row.addStretch(
            1
        )
        identity.addLayout(
            color_row
        )

        state_row = QHBoxLayout()

        self.save_state = QLabel(
            ""
        )
        self.save_state.setObjectName(
            "SaveState"
        )

        self.autosave_check = QCheckBox(
            "自動保存"
        )
        self.autosave_check.setChecked(
            self.autosave_enabled
        )
        self.autosave_check.toggled.connect(
            self._autosave_setting_changed
        )

        self.save_button = QPushButton(
            "保存"
        )
        self.save_button.setObjectName(
            "PrimaryButton"
        )
        self.save_button.clicked.connect(
            self.save
        )

        state_row.addWidget(
            self.save_state
        )
        state_row.addStretch(
            1
        )
        state_row.addWidget(
            self.autosave_check
        )
        state_row.addWidget(
            self.save_button
        )

        identity.addStretch(
            1
        )
        identity.addLayout(
            state_row
        )

        hero_layout.addLayout(
            identity,
            1,
        )

        self.main_splitter.addWidget(
            hero
        )

        # -------------------------------------------------------
        # Seven full-width data tabs.
        # -------------------------------------------------------
        self.data_tabs = QTabWidget()
        self.data_tabs.setObjectName(
            "CharacterDataTabs"
        )
        self.main_splitter.addWidget(
            self.data_tabs
        )

        self._build_v22_basic_tab()
        self._build_v22_status_tab()
        self._build_v22_params_tab()
        self._build_v22_skills_tab()
        self._build_v22_memo_tab()
        self._build_v22_palette_tab()
        self._build_v22_classification_tab()

        self.main_splitter.setSizes(
            [350, 650]
        )
        self.main_splitter.setStretchFactor(
            0,
            0,
        )
        self.main_splitter.setStretchFactor(
            1,
            1,
        )

        bottom = QHBoxLayout()
        bottom.addStretch(
            1
        )
        close_button = QPushButton(
            "閉じる"
        )
        close_button.clicked.connect(
            self.close
        )
        bottom.addWidget(
            close_button
        )
        root.addLayout(
            bottom
        )

    def _build_v22_basic_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(
            tab
        )
        layout.setContentsMargins(
            16,
            16,
            16,
            16,
        )
        layout.setSpacing(
            14
        )

        form = QFormLayout()
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )
        form.setVerticalSpacing(
            12
        )

        self.initiative_edit = QLineEdit()
        self.external_url_edit = QLineEdit()

        self.initiative_edit.textChanged.connect(
            self._mark_dirty
        )
        self.external_url_edit.textChanged.connect(
            self._mark_dirty
        )

        self.secret_check = QCheckBox(
            "シークレット"
        )
        self.invisible_check = QCheckBox(
            "盤面で非表示"
        )
        self.hide_status_check = QCheckBox(
            "ステータスを隠す"
        )

        for check in (
            self.secret_check,
            self.invisible_check,
            self.hide_status_check,
        ):
            check.toggled.connect(
                self._mark_dirty
            )

        flags = QWidget()
        flags_layout = QHBoxLayout(
            flags
        )
        flags_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        flags_layout.setSpacing(
            16
        )
        flags_layout.addWidget(
            self.secret_check
        )
        flags_layout.addWidget(
            self.invisible_check
        )
        flags_layout.addWidget(
            self.hide_status_check
        )
        flags_layout.addStretch(
            1
        )

        self.template_combo = QComboBox()

        for template in list_rule_templates():
            self.template_combo.addItem(
                template["name"],
                template["id"],
            )

        self.template_apply_button = QPushButton(
            "テンプレートを適用"
        )
        self.template_apply_button.clicked.connect(
            self._apply_selected_template
        )

        template_widget = QWidget()
        template_layout = QHBoxLayout(
            template_widget
        )
        template_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        template_layout.addWidget(
            self.template_combo
        )
        template_layout.addWidget(
            self.template_apply_button
        )
        template_layout.addStretch(
            1
        )

        form.addRow(
            "イニシアティブ",
            self.initiative_edit,
        )
        form.addRow(
            "外部URL",
            self.external_url_edit,
        )
        form.addRow(
            "ココフォリア設定",
            flags,
        )
        form.addRow(
            "ルールテンプレート",
            template_widget,
        )

        self.export_id_edit = QLineEdit()
        self.export_id_edit.setReadOnly(
            True
        )

        self.template_id_edit = QLineEdit()
        self.template_id_edit.setReadOnly(
            True
        )

        self.export_id_label = QLabel(
            "CCFOLIA Export ID"
        )
        self.template_id_label = QLabel(
            "Template ID"
        )

        form.addRow(
            self.export_id_label,
            self.export_id_edit,
        )
        form.addRow(
            self.template_id_label,
            self.template_id_edit,
        )

        self.export_id_label.setVisible(
            self._developer_mode
        )
        self.export_id_edit.setVisible(
            self._developer_mode
        )
        self.template_id_label.setVisible(
            self._developer_mode
        )
        self.template_id_edit.setVisible(
            self._developer_mode
        )

        layout.addLayout(
            form
        )

        note = QLabel(
            "テンプレート適用は不足している項目を補完します。"
            "既存の入力値は原則として維持します。"
        )
        note.setObjectName(
            "MutedText"
        )
        note.setWordWrap(
            True
        )
        layout.addWidget(
            note
        )
        layout.addStretch(
            1
        )

        self.data_tabs.addTab(
            tab,
            "基本情報",
        )

    def _configure_v22_table(
        self,
        table,
    ):
        self._configure_table(
            table
        )
        table.setAlternatingRowColors(
            True
        )
        table.verticalHeader().setDefaultSectionSize(
            36
        )

    def _build_v22_status_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(
            tab
        )
        layout.setContentsMargins(
            10,
            10,
            10,
            10,
        )

        self.status_table = QTableWidget(
            0,
            6,
        )
        self.status_table.setHorizontalHeaderLabels(
            [
                "名前",
                "現在",
                "最大",
                "初期式",
                "最大式",
                "式エラー",
            ]
        )
        self._configure_v22_table(
            self.status_table
        )

        header = self.status_table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.Stretch,
        )

        self.status_table.itemChanged.connect(
            self._source_table_changed
        )

        layout.addWidget(
            self.status_table,
            1,
        )

        buttons = QHBoxLayout()

        self.status_add_button = QPushButton(
            "行を追加"
        )
        self.status_remove_button = QPushButton(
            "選択行を削除"
        )
        self.status_reset_button = QPushButton(
            "ルール初期値を再計算"
        )

        self.status_add_button.clicked.connect(
            self._add_status_v22
        )
        self.status_remove_button.clicked.connect(
            lambda: self._remove_table_row(
                self.status_table
            )
        )
        self.status_reset_button.clicked.connect(
            self._reset_status_initials
        )

        buttons.addWidget(
            self.status_add_button
        )
        buttons.addWidget(
            self.status_remove_button
        )
        buttons.addStretch(
            1
        )
        buttons.addWidget(
            self.status_reset_button
        )

        layout.addLayout(
            buttons
        )

        self.data_tabs.addTab(
            tab,
            "ステータス",
        )

    def _build_v22_params_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(
            tab
        )
        layout.setContentsMargins(
            10,
            10,
            10,
            10,
        )

        self.params_table = QTableWidget(
            0,
            4,
        )
        self.params_table.setHorizontalHeaderLabels(
            [
                "名前",
                "値",
                "式",
                "式エラー",
            ]
        )
        self._configure_v22_table(
            self.params_table
        )

        header = self.params_table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )

        self.params_table.itemChanged.connect(
            self._source_table_changed
        )

        layout.addWidget(
            self.params_table,
            1,
        )

        buttons = QHBoxLayout()

        self.params_add_button = QPushButton(
            "行を追加"
        )
        self.params_remove_button = QPushButton(
            "選択行を削除"
        )

        self.params_add_button.clicked.connect(
            self._add_param_v22
        )
        self.params_remove_button.clicked.connect(
            lambda: self._remove_table_row(
                self.params_table
            )
        )

        buttons.addWidget(
            self.params_add_button
        )
        buttons.addWidget(
            self.params_remove_button
        )
        buttons.addStretch(
            1
        )

        layout.addLayout(
            buttons
        )

        self.data_tabs.addTab(
            tab,
            "パラメータ",
        )

    def _build_v22_skills_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(
            tab
        )
        layout.setContentsMargins(
            8,
            8,
            8,
            8,
        )

        self.skills_editor = SkillBlockEditor()
        self.skills_editor.changed.connect(
            self._skills_changed_inline
        )

        layout.addWidget(
            self.skills_editor,
            1,
        )

        self.data_tabs.addTab(
            tab,
            "技能",
        )

    def _build_v22_memo_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(
            tab
        )
        layout.setContentsMargins(
            10,
            10,
            10,
            10,
        )

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        left = QWidget()
        left_layout = QVBoxLayout(
            left
        )
        left_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.memo_list = QListWidget()
        self.memo_list.currentRowChanged.connect(
            self._memo_selection_changed
        )

        self.memo_add_button = QPushButton(
            "追加"
        )
        self.memo_remove_button = QPushButton(
            "削除"
        )
        self.memo_add_button.clicked.connect(
            self._add_memo
        )
        self.memo_remove_button.clicked.connect(
            self._remove_memo
        )

        memo_buttons = QHBoxLayout()
        memo_buttons.addWidget(
            self.memo_add_button
        )
        memo_buttons.addWidget(
            self.memo_remove_button
        )

        left_layout.addWidget(
            self.memo_list,
            1,
        )
        left_layout.addLayout(
            memo_buttons
        )

        right = QWidget()
        right_layout = QVBoxLayout(
            right
        )
        right_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        right_layout.setSpacing(
            8
        )

        self.memo_title = QLineEdit()
        self.memo_title.setPlaceholderText(
            "メモのタイトル"
        )

        self.memo_private = QCheckBox(
            "ココフォリアへ出力"
        )

        self.memo_body = QTextEdit()
        self.memo_body.setPlaceholderText(
            "メモ本文"
        )

        self.memo_title.textChanged.connect(
            self._memo_edited
        )
        self.memo_private.toggled.connect(
            self._memo_edited
        )
        self.memo_body.textChanged.connect(
            self._memo_edited
        )

        right_layout.addWidget(
            self.memo_title
        )
        right_layout.addWidget(
            self.memo_private
        )
        right_layout.addWidget(
            self.memo_body,
            1,
        )

        splitter.addWidget(
            left
        )
        splitter.addWidget(
            right
        )
        splitter.setSizes(
            [260, 850]
        )

        layout.addWidget(
            splitter
        )

        self.data_tabs.addTab(
            tab,
            "メモ",
        )

    def _build_v22_palette_tab(self):
        tab = QWidget()
        layout = QHBoxLayout(
            tab
        )
        layout.setContentsMargins(
            10,
            10,
            10,
            10,
        )

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        left = QWidget()
        left_layout = QVBoxLayout(
            left
        )
        left_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        self.palette_list = QListWidget()
        self.palette_list.currentRowChanged.connect(
            self._palette_selected_inline
        )

        self.palette_add_button = QPushButton(
            "追加"
        )
        self.palette_remove_button = QPushButton(
            "削除"
        )

        self.palette_add_button.clicked.connect(
            self._add_palette_inline
        )
        self.palette_remove_button.clicked.connect(
            self._remove_palette_inline
        )

        palette_buttons = QHBoxLayout()
        palette_buttons.addWidget(
            self.palette_add_button
        )
        palette_buttons.addWidget(
            self.palette_remove_button
        )

        left_layout.addWidget(
            self.palette_list,
            1,
        )
        left_layout.addLayout(
            palette_buttons
        )

        right = QWidget()
        right_layout = QVBoxLayout(
            right
        )
        right_layout.setContentsMargins(
            0,
            0,
            0,
            0,
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

        self.palette_generate_button = QPushButton(
            "CoC6基本パレット生成"
        )
        self.palette_generate_button.clicked.connect(
            self._generate_palette_v22
        )

        name_row.addWidget(
            self.palette_name,
            1,
        )
        name_row.addWidget(
            self.palette_mode
        )
        name_row.addWidget(
            self.palette_generate_button
        )

        self.palette_content = QTextEdit()
        self.palette_content.setPlaceholderText(
            "チャットパレット本文"
        )

        self.palette_name.textChanged.connect(
            self._palette_edited_inline
        )
        self.palette_mode.currentIndexChanged.connect(
            self._palette_edited_inline
        )
        self.palette_content.textChanged.connect(
            self._palette_edited_inline
        )

        right_layout.addLayout(
            name_row
        )
        right_layout.addWidget(
            self.palette_content,
            1,
        )

        splitter.addWidget(
            left
        )
        splitter.addWidget(
            right
        )
        splitter.setSizes(
            [260, 850]
        )

        layout.addWidget(
            splitter
        )

        self.data_tabs.addTab(
            tab,
            "チャットパレット",
        )

    def _build_v22_classification_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(
            tab
        )
        layout.setContentsMargins(
            14,
            14,
            14,
            14,
        )

        note = QLabel(
            "タグは画面上部で編集できます。ここでは所属グループを管理します。"
        )
        note.setObjectName(
            "MutedText"
        )

        self.group_tree = QTreeWidget()
        self.group_tree.setHeaderHidden(
            True
        )
        self.group_tree.setIndentation(
            18
        )
        self.group_tree.itemChanged.connect(
            self._group_check_changed
        )

        layout.addWidget(
            note
        )
        layout.addWidget(
            self.group_tree,
            1,
        )

        self.data_tabs.addTab(
            tab,
            "分類",
        )

    def _load(self):
        bundle = load_v22_bundle(
            self.character_id
        )
        character = bundle[
            "character"
        ]

        self.name_edit.setText(
            character[
                "name"
            ]
        )
        self.player_edit.setText(
            character[
                "player_name"
            ]
        )
        self.initiative_edit.setText(
            str(
                character[
                    "initiative"
                ]
            )
        )
        self.external_url_edit.setText(
            character[
                "external_url"
            ]
        )
        self.color_edit.setText(
            character[
                "color"
            ]
        )

        self.secret_check.setChecked(
            bool(
                character[
                    "secret"
                ]
            )
        )
        self.invisible_check.setChecked(
            bool(
                character[
                    "invisible"
                ]
            )
        )
        self.hide_status_check.setChecked(
            bool(
                character[
                    "hide_status"
                ]
            )
        )

        self.export_id_edit.setText(
            character[
                "cocofolia_export_id"
            ]
        )

        self._template_id = str(
            character.get(
                "template_id",
                "",
            )
            or ""
        )
        self.template_id_edit.setText(
            self._template_id
        )

        template_index = (
            self.template_combo.findData(
                self._template_id
                or "generic"
            )
        )
        self.template_combo.setCurrentIndex(
            max(
                0,
                template_index,
            )
        )

        self.image_list.clear()

        for image in bundle[
            "images"
        ]:
            self._append_image_item(
                image
            )

        if self.image_list.count():
            self.image_list.setCurrentRow(
                0
            )
            self._refresh_image_combo(
                0
            )
            self._preview_image_row(
                0
            )
        else:
            self._refresh_image_combo(
                -1
            )
            self._preview_image_row(
                -1
            )

        self.status_table.blockSignals(
            True
        )
        self.status_table.setRowCount(
            0
        )

        for row in bundle[
            "statuses"
        ]:
            self._append_status_v22(
                row
            )

        self.status_table.blockSignals(
            False
        )

        self.params_table.blockSignals(
            True
        )
        self.params_table.setRowCount(
            0
        )

        for row in bundle[
            "params"
        ]:
            self._append_param_v22(
                row
            )

        self.params_table.blockSignals(
            False
        )

        self.memo_records = [
            {
                "title": row[
                    "title"
                ],
                "body": row[
                    "body"
                ],
                "private": bool(
                    row[
                        "is_private"
                    ]
                ),
            }
            for row in bundle[
                "memos"
            ]
        ]

        self._refresh_memo_list(
            0
            if self.memo_records
            else -1
        )

        self._setup_tag_completer()
        self.tags_edit.set_tags(
            [
                row[
                    "name"
                ]
                for row in bundle[
                    "tags"
                ]
            ]
        )

        self._load_group_tree(
            set(
                bundle[
                    "group_ids"
                ]
            )
        )

        advanced = load_advanced_bundle(
            self.character_id
        )

        self.skills_editor.set_skills(
            advanced[
                "skills"
            ]
        )

        self.palette_records = [
            {
                "name": row[
                    "name"
                ],
                "mode": row[
                    "mode"
                ],
                "content": row[
                    "content"
                ],
            }
            for row in advanced[
                "palettes"
            ]
        ]

        self._refresh_palette_list_inline(
            0
            if self.palette_records
            else -1
        )

        self._apply_name_color()
        self._apply_developer_columns()
        self._recalculate_advanced_previews()

    def _append_status_v22(
        self,
        row: dict | None = None,
    ):
        row = row or {}

        index = (
            self.status_table.rowCount()
        )
        self.status_table.insertRow(
            index
        )
        self.status_table.setRowHeight(
            index,
            36,
        )

        values = [
            row.get(
                "label",
                "",
            ),
            ""
            if row.get(
                "current_value",
                None,
            )
            is None
            else str(
                row.get(
                    "current_value"
                )
            ),
            ""
            if row.get(
                "max_value",
                None,
            )
            is None
            else str(
                row.get(
                    "max_value"
                )
            ),
            row.get(
                "initial_formula",
                "",
            ),
            row.get(
                "max_formula",
                "",
            ),
            row.get(
                "formula_error",
                "",
            ),
        ]

        for column, value in enumerate(
            values
        ):
            item = QTableWidgetItem(
                str(
                    value
                    if value
                    is not None
                    else ""
                )
            )

            if column == 5:
                item.setFlags(
                    item.flags()
                    & ~Qt.ItemFlag.ItemIsEditable
                )

            self.status_table.setItem(
                index,
                column,
                item,
            )

        self._apply_rule_row_editability()

    def _append_param_v22(
        self,
        row: dict | None = None,
    ):
        row = row or {}

        index = (
            self.params_table.rowCount()
        )
        self.params_table.insertRow(
            index
        )
        self.params_table.setRowHeight(
            index,
            36,
        )

        values = [
            row.get(
                "label",
                "",
            ),
            row.get(
                "value",
                "",
            ),
            row.get(
                "formula",
                "",
            ),
            row.get(
                "formula_error",
                "",
            ),
        ]

        for column, value in enumerate(
            values
        ):
            item = QTableWidgetItem(
                str(
                    value
                    if value
                    is not None
                    else ""
                )
            )

            if column == 3:
                item.setFlags(
                    item.flags()
                    & ~Qt.ItemFlag.ItemIsEditable
                )

            self.params_table.setItem(
                index,
                column,
                item,
            )

        self._apply_rule_row_editability()

    def _add_status_v22(self):
        self.status_table.blockSignals(
            True
        )
        self._append_status_v22()
        self.status_table.blockSignals(
            False
        )
        row = (
            self.status_table.rowCount()
            - 1
        )
        self.status_table.setCurrentCell(
            row,
            0,
        )
        self._mark_dirty()

    def _add_param_v22(self):
        self.params_table.blockSignals(
            True
        )
        self._append_param_v22()
        self.params_table.blockSignals(
            False
        )
        row = (
            self.params_table.rowCount()
            - 1
        )
        self.params_table.setCurrentCell(
            row,
            0,
        )
        self._mark_dirty()

    def _collect_statuses_v22(self):
        output = []

        for row in range(
            self.status_table.rowCount()
        ):
            def value(column):
                item = self.status_table.item(
                    row,
                    column,
                )
                return (
                    item.text()
                    if item
                    else ""
                )

            output.append(
                {
                    "label": value(0),
                    "current": value(1),
                    "max": value(2),
                    "initial_formula": value(3),
                    "max_formula": value(4),
                }
            )

        return output

    def _collect_params_v22(self):
        output = []

        for row in range(
            self.params_table.rowCount()
        ):
            def value(column):
                item = self.params_table.item(
                    row,
                    column,
                )
                return (
                    item.text()
                    if item
                    else ""
                )

            output.append(
                {
                    "label": value(0),
                    "value": value(1),
                    "formula": value(2),
                }
            )

        return output

    def _source_values_v22(self):
        values = {}

        for row in range(
            self.params_table.rowCount()
        ):
            label_item = self.params_table.item(
                row,
                0,
            )
            value_item = self.params_table.item(
                row,
                1,
            )

            label = (
                label_item.text().strip()
                if label_item
                else ""
            )

            if label:
                values[
                    label
                ] = (
                    value_item.text()
                    if value_item
                    else ""
                )

        for row in range(
            self.status_table.rowCount()
        ):
            label_item = self.status_table.item(
                row,
                0,
            )
            value_item = self.status_table.item(
                row,
                1,
            )

            label = (
                label_item.text().strip()
                if label_item
                else ""
            )

            if (
                label
                and label
                not in values
            ):
                values[
                    label
                ] = (
                    value_item.text()
                    if value_item
                    else ""
                )

        return values

    def _recalculate_advanced_previews(self):
        if self.loading:
            return

        values = self._source_values_v22()

        self.params_table.blockSignals(
            True
        )

        pending = []

        for row in range(
            self.params_table.rowCount()
        ):
            formula_item = (
                self.params_table.item(
                    row,
                    2,
                )
            )
            formula = (
                formula_item.text().strip()
                if formula_item
                else ""
            )

            if formula:
                pending.append(
                    row
                )

        for _ in range(
            max(
                1,
                len(
                    pending
                )
                + 1,
            )
        ):
            if not pending:
                break

            next_pending = []
            progress = False

            for row in pending:
                label_item = (
                    self.params_table.item(
                        row,
                        0,
                    )
                )
                formula_item = (
                    self.params_table.item(
                        row,
                        2,
                    )
                )

                label = (
                    label_item.text().strip()
                    if label_item
                    else ""
                )
                formula = (
                    formula_item.text().strip()
                    if formula_item
                    else ""
                )

                try:
                    result = evaluate_rule_formula(
                        formula,
                        values,
                    )
                    result_text = (
                        format_formula_value(
                            result
                        )
                    )
                    error = ""
                    progress = True

                    if label:
                        values[
                            label
                        ] = result_text
                except RuleFormulaError as exc:
                    result_text = ""
                    error = str(
                        exc
                    )
                    next_pending.append(
                        row
                    )

                value_item = (
                    self.params_table.item(
                        row,
                        1,
                    )
                )

                if value_item is None:
                    value_item = QTableWidgetItem(
                        ""
                    )
                    self.params_table.setItem(
                        row,
                        1,
                        value_item,
                    )

                if not error:
                    value_item.setText(
                        result_text
                    )

                error_item = (
                    self.params_table.item(
                        row,
                        3,
                    )
                )

                if error_item is None:
                    error_item = QTableWidgetItem(
                        ""
                    )
                    self.params_table.setItem(
                        row,
                        3,
                        error_item,
                    )

                error_item.setText(
                    error
                )

            pending = next_pending

            if not progress:
                break

        self.params_table.blockSignals(
            False
        )

        values = self._source_values_v22()

        self.status_table.blockSignals(
            True
        )

        for row in range(
            self.status_table.rowCount()
        ):
            initial_item = (
                self.status_table.item(
                    row,
                    3,
                )
            )
            max_formula_item = (
                self.status_table.item(
                    row,
                    4,
                )
            )

            initial_formula = (
                initial_item.text().strip()
                if initial_item
                else ""
            )
            max_formula = (
                max_formula_item.text().strip()
                if max_formula_item
                else ""
            )

            errors = []

            if initial_formula:
                try:
                    evaluate_rule_formula(
                        initial_formula,
                        values,
                    )
                except RuleFormulaError as exc:
                    errors.append(
                        f"初期値: {exc}"
                    )

            if max_formula:
                try:
                    result = evaluate_rule_formula(
                        max_formula,
                        values,
                    )
                    max_item = (
                        self.status_table.item(
                            row,
                            2,
                        )
                    )

                    if max_item is None:
                        max_item = QTableWidgetItem(
                            ""
                        )
                        self.status_table.setItem(
                            row,
                            2,
                            max_item,
                        )

                    max_item.setText(
                        format_formula_value(
                            result
                        )
                    )
                except RuleFormulaError as exc:
                    errors.append(
                        f"最大値: {exc}"
                    )

            error_item = (
                self.status_table.item(
                    row,
                    5,
                )
            )

            if error_item is None:
                error_item = QTableWidgetItem(
                    ""
                )
                self.status_table.setItem(
                    row,
                    5,
                    error_item,
                )

            error_item.setText(
                " / ".join(
                    errors
                )
            )

        self.status_table.blockSignals(
            False
        )

        try:
            self.skills_editor.refresh_previews(
                self._source_values_v22()
            )
        except Exception:
            pass

        self._apply_rule_row_editability()

    def _source_table_changed(
        self,
        *args,
    ):
        if self.loading:
            return

        self._recalculate_advanced_previews()
        self._mark_dirty()

    def _apply_developer_columns(self):
        for column in (
            3,
            4,
            5,
        ):
            self.status_table.setColumnHidden(
                column,
                not self._developer_mode,
            )

        for column in (
            2,
            3,
        ):
            self.params_table.setColumnHidden(
                column,
                not self._developer_mode,
            )

    def _set_item_editable(
        self,
        item,
        editable: bool,
    ):
        if item is None:
            return

        old_flags = item.flags()

        if editable:
            new_flags = (
                old_flags
                | Qt.ItemFlag.ItemIsEditable
            )
        else:
            new_flags = (
                old_flags
                & ~Qt.ItemFlag.ItemIsEditable
            )

        # setFlags() 自体が itemChanged を発火させる環境がある。
        # 同じ状態なら何もしないことで不要な再入を防ぐ。
        if new_flags == old_flags:
            return

        item.setFlags(
            new_flags
        )

    def _apply_rule_row_editability(self):
        if not hasattr(
            self,
            "status_table",
        ):
            return

        # QTableWidgetItem.setFlags() は itemChanged を起こし得る。
        # itemChanged -> _source_table_changed()
        # -> _recalculate_advanced_previews()
        # -> _apply_rule_row_editability()
        # という再帰ループを防ぐため、この処理中はsignalを止める。
        status_was_blocked = (
            self.status_table.blockSignals(
                True
            )
        )
        params_was_blocked = (
            self.params_table.blockSignals(
                True
            )
        )

        try:
            for row in range(
                self.status_table.rowCount()
            ):
                max_formula_item = (
                    self.status_table.item(
                        row,
                        4,
                    )
                )
                max_formula = (
                    max_formula_item.text().strip()
                    if max_formula_item
                    else ""
                )

                self._set_item_editable(
                    self.status_table.item(
                        row,
                        0,
                    ),
                    self._edit_mode,
                )
                self._set_item_editable(
                    self.status_table.item(
                        row,
                        1,
                    ),
                    self._edit_mode,
                )
                self._set_item_editable(
                    self.status_table.item(
                        row,
                        2,
                    ),
                    (
                        self._edit_mode
                        and not max_formula
                    ),
                )
                self._set_item_editable(
                    self.status_table.item(
                        row,
                        3,
                    ),
                    (
                        self._edit_mode
                        and self._developer_mode
                    ),
                )
                self._set_item_editable(
                    self.status_table.item(
                        row,
                        4,
                    ),
                    (
                        self._edit_mode
                        and self._developer_mode
                    ),
                )
                self._set_item_editable(
                    self.status_table.item(
                        row,
                        5,
                    ),
                    False,
                )

            for row in range(
                self.params_table.rowCount()
            ):
                formula_item = (
                    self.params_table.item(
                        row,
                        2,
                    )
                )
                formula = (
                    formula_item.text().strip()
                    if formula_item
                    else ""
                )

                self._set_item_editable(
                    self.params_table.item(
                        row,
                        0,
                    ),
                    self._edit_mode,
                )
                self._set_item_editable(
                    self.params_table.item(
                        row,
                        1,
                    ),
                    (
                        self._edit_mode
                        and not formula
                    ),
                )
                self._set_item_editable(
                    self.params_table.item(
                        row,
                        2,
                    ),
                    (
                        self._edit_mode
                        and self._developer_mode
                    ),
                )
                self._set_item_editable(
                    self.params_table.item(
                        row,
                        3,
                    ),
                    False,
                )
        finally:
            self.status_table.blockSignals(
                status_was_blocked
            )
            self.params_table.blockSignals(
                params_was_blocked
            )

    def _apply_selected_template(self):
        if not self._edit_mode:
            return

        if self.dirty:
            if not self.save(
                show_error=True
            ):
                return

        template_id = (
            self.template_combo.currentData()
            or "generic"
        )

        try:
            apply_template_v22(
                self.character_id,
                template_id,
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "テンプレート",
                str(
                    exc
                ),
            )
            return

        old_loading = self.loading
        self.loading = True
        self._load()
        self.loading = old_loading

        self._template_id = (
            template_id
        )
        self._set_save_state(
            "保存済み"
        )
        self.saved.emit()
        self.changed.emit()

    def _reset_status_initials(self):
        if not self._edit_mode:
            return

        if self.dirty:
            if not self.save(
                show_error=True
            ):
                return

        answer = QMessageBox.question(
            self,
            "ルール初期値を再計算",
            "式を持つステータスの現在値を、"
            "ルール上の初期値で再計算します。\n\n"
            "HP・MPなどの現在値が上書きされる場合があります。"
            "\n続行しますか？",
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
            reset_status_initial_values(
                self.character_id
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "再計算できません",
                str(
                    exc
                ),
            )
            return

        old_loading = self.loading
        self.loading = True
        self._load()
        self.loading = old_loading
        self._set_save_state(
            "保存済み"
        )

    def _generate_palette_v22(self):
        if self.dirty:
            if not self.save(
                show_error=True
            ):
                return

        try:
            content = (
                generate_coc6_palette_v22(
                    self.character_id
                )
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "チャットパレット",
                str(
                    exc
                ),
            )
            return

        self.palette_records.append(
            {
                "name": "CoC6基本",
                "mode": "normal",
                "content": content,
            }
        )

        self._refresh_palette_list_inline(
            len(
                self.palette_records
            )
            - 1
        )
        self._mark_dirty()

    def _refresh_image_combo(
        self,
        selected_row: int | None = None,
    ):
        if selected_row is None:
            selected_row = (
                self.image_list.currentRow()
            )

        self.image_combo.blockSignals(
            True
        )
        self.image_combo.clear()

        for row in range(
            self.image_list.count()
        ):
            item = self.image_list.item(
                row
            )
            data = item.data(
                Qt.ItemDataRole.UserRole
            ) or {}

            label = str(
                data.get(
                    "label",
                    "",
                )
                or ""
            ).strip()

            if row == 0:
                display = (
                    f"MAIN · {label}"
                    if label
                    else "MAIN"
                )
            else:
                display = (
                    f"差分 {row + 1} · {label}"
                    if label
                    else f"差分 {row + 1}"
                )

            self.image_combo.addItem(
                display,
                row,
            )

        if self.image_combo.count():
            selected_row = max(
                0,
                min(
                    selected_row,
                    self.image_combo.count()
                    - 1,
                ),
            )
            self.image_combo.setCurrentIndex(
                selected_row
            )

        self.image_combo.blockSignals(
            False
        )
        self._update_image_move_buttons()

    def _sync_rule_values_from_bundle(
        self,
        bundle,
    ):
        status_by_label = {}

        for row in bundle[
            "statuses"
        ]:
            status_by_label.setdefault(
                str(
                    row[
                        "label"
                    ]
                ),
                [],
            ).append(
                row
            )

        param_by_label = {}

        for row in bundle[
            "params"
        ]:
            param_by_label.setdefault(
                str(
                    row[
                        "label"
                    ]
                ),
                [],
            ).append(
                row
            )

        self.status_table.blockSignals(
            True
        )
        self.params_table.blockSignals(
            True
        )

        try:
            used = {}

            for row in range(
                self.status_table.rowCount()
            ):
                label_item = (
                    self.status_table.item(
                        row,
                        0,
                    )
                )
                label = (
                    label_item.text()
                    if label_item
                    else ""
                )

                index = used.get(
                    label,
                    0,
                )
                candidates = (
                    status_by_label.get(
                        label,
                        [],
                    )
                )

                if index >= len(
                    candidates
                ):
                    continue

                db_row = candidates[
                    index
                ]
                used[
                    label
                ] = index + 1

                for column, key in (
                    (
                        1,
                        "current_value",
                    ),
                    (
                        2,
                        "max_value",
                    ),
                    (
                        5,
                        "formula_error",
                    ),
                ):
                    item = (
                        self.status_table.item(
                            row,
                            column,
                        )
                    )

                    if item is None:
                        item = QTableWidgetItem(
                            ""
                        )
                        self.status_table.setItem(
                            row,
                            column,
                            item,
                        )

                    value = db_row.get(
                        key,
                        "",
                    )

                    item.setText(
                        ""
                        if value is None
                        else str(
                            value
                        )
                    )

            used = {}

            for row in range(
                self.params_table.rowCount()
            ):
                label_item = (
                    self.params_table.item(
                        row,
                        0,
                    )
                )
                label = (
                    label_item.text()
                    if label_item
                    else ""
                )

                index = used.get(
                    label,
                    0,
                )
                candidates = (
                    param_by_label.get(
                        label,
                        [],
                    )
                )

                if index >= len(
                    candidates
                ):
                    continue

                db_row = candidates[
                    index
                ]
                used[
                    label
                ] = index + 1

                for column, key in (
                    (
                        1,
                        "value",
                    ),
                    (
                        3,
                        "formula_error",
                    ),
                ):
                    item = (
                        self.params_table.item(
                            row,
                            column,
                        )
                    )

                    if item is None:
                        item = QTableWidgetItem(
                            ""
                        )
                        self.params_table.setItem(
                            row,
                            column,
                            item,
                        )

                    value = db_row.get(
                        key,
                        "",
                    )

                    item.setText(
                        ""
                        if value is None
                        else str(
                            value
                        )
                    )
        finally:
            self.status_table.blockSignals(
                False
            )
            self.params_table.blockSignals(
                False
            )

        self._apply_rule_row_editability()

    def _apply_edit_mode_to_memo(self):
        has_memo = (
            0
            <= self.memo_list.currentRow()
            < len(
                self.memo_records
            )
        )
        editable = (
            self._edit_mode
            and has_memo
        )

        self.memo_title.setReadOnly(
            not editable
        )
        self.memo_private.setEnabled(
            editable
        )
        self.memo_body.setReadOnly(
            not editable
        )

    def _apply_edit_mode_to_palette(self):
        has_palette = (
            0
            <= self.palette_list.currentRow()
            < len(
                self.palette_records
            )
        )
        editable = (
            self._edit_mode
            and has_palette
        )

        self.palette_name.setReadOnly(
            not editable
        )
        self.palette_mode.setEnabled(
            editable
        )
        self.palette_content.setReadOnly(
            not editable
        )

    def set_edit_mode(
        self,
        edit_mode: bool,
    ):
        self._edit_mode = bool(
            edit_mode
        )

        self.view_mode_button.blockSignals(
            True
        )
        self.edit_mode_button.blockSignals(
            True
        )

        self.view_mode_button.setChecked(
            not self._edit_mode
        )
        self.edit_mode_button.setChecked(
            self._edit_mode
        )

        self.view_mode_button.blockSignals(
            False
        )
        self.edit_mode_button.blockSignals(
            False
        )

        for widget in (
            self.name_edit,
            self.player_edit,
            self.initiative_edit,
            self.external_url_edit,
            self.color_edit,
        ):
            widget.setReadOnly(
                not self._edit_mode
            )

        for widget in (
            self.secret_check,
            self.invisible_check,
            self.hide_status_check,
            self.autosave_check,
        ):
            widget.setEnabled(
                self._edit_mode
            )

        self.tags_edit.setEnabled(
            self._edit_mode
        )
        self.group_tree.setEnabled(
            self._edit_mode
        )
        self.skills_editor.setEnabled(
            self._edit_mode
        )

        self.template_combo.setEnabled(
            self._edit_mode
        )
        self.template_apply_button.setVisible(
            self._edit_mode
        )

        self.image_list.setAcceptDrops(
            self._edit_mode
        )

        for widget in (
            self.color_button,
            self.image_add_button,
            self.image_remove_button,
            self.image_up_button,
            self.image_down_button,
            self.status_add_button,
            self.status_remove_button,
            self.status_reset_button,
            self.params_add_button,
            self.params_remove_button,
            self.memo_add_button,
            self.memo_remove_button,
            self.palette_add_button,
            self.palette_remove_button,
            self.palette_generate_button,
            self.save_button,
            self.autosave_check,
        ):
            widget.setVisible(
                self._edit_mode
            )

        self._apply_developer_columns()
        self._apply_rule_row_editability()
        self._apply_edit_mode_to_memo()
        self._apply_edit_mode_to_palette()
        self._update_image_move_buttons()

        self.name_edit.setProperty(
            "viewMode",
            not self._edit_mode,
        )
        self.name_edit.style().unpolish(
            self.name_edit
        )
        self.name_edit.style().polish(
            self.name_edit
        )

    def save(
        self,
        show_error: bool = True,
    ) -> bool:
        self._set_save_state(
            "保存中…"
        )

        try:
            template_id = (
                self.template_combo.currentData()
                or self._template_id
                or ""
            )

            bundle = save_v22_bundle(
                self.character_id,
                {
                    "name": self.name_edit.text(),
                    "player_name": self.player_edit.text(),
                    "initiative": self.initiative_edit.text(),
                    "external_url": self.external_url_edit.text(),
                    "color": (
                        self.color_edit.text().strip()
                        or "#888888"
                    ),
                    "secret": self.secret_check.isChecked(),
                    "invisible": self.invisible_check.isChecked(),
                    "hide_status": self.hide_status_check.isChecked(),
                },
                self._collect_images(),
                self._collect_statuses_v22(),
                self._collect_params_v22(),
                list(
                    self.memo_records
                ),
                self._collect_tag_names(),
                self._collect_group_ids(),
                str(
                    template_id
                ),
            )

            save_skills_and_palettes(
                self.character_id,
                self.skills_editor.skills(),
                list(
                    self.palette_records
                ),
            )
        except Exception as exc:
            self._set_save_state(
                "保存エラー"
            )

            if show_error:
                QMessageBox.warning(
                    self,
                    "保存できません",
                    str(
                        exc
                    ),
                )

            return False

        self._template_id = str(
            template_id
            or ""
        )
        self.template_id_edit.setText(
            self._template_id
        )

        self._sync_rule_values_from_bundle(
            bundle
        )

        self.dirty = False
        self._set_save_state(
            "保存済み"
        )
        self.saved.emit()
        self.changed.emit()
        self._setup_tag_completer()
        self._recalculate_advanced_previews()
        return True


class CharacterEditorDialog(
    Phase22BCharacterDialog
):
    def __init__(
        self,
        character_id: str,
        parent=None,
    ):
        super().__init__(
            character_id,
            parent,
            start_edit=True,
        )


CharacterViewDialog = Phase22BCharacterDialog

# ---------------------------------------------------------------------------
# Phase 23: character editor usability / safety polish
# ---------------------------------------------------------------------------

from app.services.settings_service import (
    get_setting as get_setting_v23,
    set_setting as set_setting_v23,
)


class Phase23CharacterDialog(Phase22BCharacterDialog):
    LAST_TAB_SETTING = "character_last_tab"

    def _build_ui(self):
        super()._build_ui()

        # Keep the portrait useful without allowing the hero area to
        # dominate the full-height data tabs.
        self.portrait_label.setFixedSize(
            320,
            260,
        )
        self.image_combo.setMinimumWidth(
            220
        )
        self.main_splitter.setSizes(
            [315, 685]
        )

        # Template selection is an explicit action. Selecting an entry in
        # the combo alone never changes the character's active template.
        self.template_combo.setToolTip(
            "選択しただけでは変更されません。"
            "「テンプレートを適用」を押したときに反映されます。"
        )
        self.template_apply_button.setToolTip(
            "選択中のテンプレートをキャラクターへ適用します。"
        )

        try:
            last_tab = int(
                get_setting_v23(
                    self.LAST_TAB_SETTING,
                    "0",
                )
            )
        except (
            TypeError,
            ValueError,
        ):
            last_tab = 0

        if self.data_tabs.count():
            last_tab = max(
                0,
                min(
                    last_tab,
                    self.data_tabs.count() - 1,
                ),
            )
            self.data_tabs.setCurrentIndex(
                last_tab
            )

        self.data_tabs.currentChanged.connect(
            self._remember_v23_tab
        )

    def _remember_v23_tab(
        self,
        index: int,
    ):
        if index < 0:
            return

        try:
            set_setting_v23(
                self.LAST_TAB_SETTING,
                index,
            )
        except Exception:
            # Remembering a tab is convenience only; it must never block
            # the character editor itself.
            pass

    def _build_v22_status_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(
            tab
        )
        layout.setContentsMargins(
            12,
            12,
            12,
            12,
        )
        layout.setSpacing(
            8
        )

        self.status_table = QTableWidget(
            0,
            6,
        )
        self.status_table.setHorizontalHeaderLabels(
            [
                "名前",
                "現在",
                "最大",
                "初期式",
                "最大式",
                "式エラー",
            ]
        )
        self._configure_v22_table(
            self.status_table
        )

        header = self.status_table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.Stretch,
        )

        self.status_table.itemChanged.connect(
            self._source_table_changed
        )

        layout.addWidget(
            self.status_table,
            1,
        )

        note = QLabel(
            "現在値は通常どおり手動で変更できます。"
            "ルール式を持つ最大値は自動計算されます。"
            "式そのものはデベロッパーモードで確認できます。"
        )
        note.setObjectName(
            "MutedText"
        )
        note.setWordWrap(
            True
        )
        layout.addWidget(
            note
        )

        buttons = QHBoxLayout()

        self.status_add_button = QPushButton(
            "行を追加"
        )
        self.status_remove_button = QPushButton(
            "選択行を削除"
        )
        self.status_up_button = QPushButton(
            "↑"
        )
        self.status_down_button = QPushButton(
            "↓"
        )
        self.status_reset_button = QPushButton(
            "ルール初期値を再計算"
        )

        self.status_up_button.setToolTip(
            "選択行を1つ上へ移動します。"
        )
        self.status_down_button.setToolTip(
            "選択行を1つ下へ移動します。"
        )

        self.status_add_button.clicked.connect(
            self._add_status_v22
        )
        self.status_remove_button.clicked.connect(
            lambda: self._remove_table_row(
                self.status_table
            )
        )
        self.status_up_button.clicked.connect(
            lambda: self._move_v23_rule_row(
                self.status_table,
                -1,
            )
        )
        self.status_down_button.clicked.connect(
            lambda: self._move_v23_rule_row(
                self.status_table,
                1,
            )
        )
        self.status_reset_button.clicked.connect(
            self._reset_status_initials
        )

        buttons.addWidget(
            self.status_add_button
        )
        buttons.addWidget(
            self.status_remove_button
        )
        buttons.addSpacing(
            8
        )
        buttons.addWidget(
            self.status_up_button
        )
        buttons.addWidget(
            self.status_down_button
        )
        buttons.addStretch(
            1
        )
        buttons.addWidget(
            self.status_reset_button
        )

        layout.addLayout(
            buttons
        )

        self.data_tabs.addTab(
            tab,
            "ステータス",
        )

    def _build_v22_params_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(
            tab
        )
        layout.setContentsMargins(
            12,
            12,
            12,
            12,
        )
        layout.setSpacing(
            8
        )

        self.params_table = QTableWidget(
            0,
            4,
        )
        self.params_table.setHorizontalHeaderLabels(
            [
                "名前",
                "値",
                "式",
                "式エラー",
            ]
        )
        self._configure_v22_table(
            self.params_table
        )

        header = self.params_table.horizontalHeader()
        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.Stretch,
        )
        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )

        self.params_table.itemChanged.connect(
            self._source_table_changed
        )

        layout.addWidget(
            self.params_table,
            1,
        )

        note = QLabel(
            "テンプレート由来の自動計算値は直接編集できません。"
            "通常のパラメータはそのまま編集できます。"
        )
        note.setObjectName(
            "MutedText"
        )
        note.setWordWrap(
            True
        )
        layout.addWidget(
            note
        )

        buttons = QHBoxLayout()

        self.params_add_button = QPushButton(
            "行を追加"
        )
        self.params_remove_button = QPushButton(
            "選択行を削除"
        )
        self.params_up_button = QPushButton(
            "↑"
        )
        self.params_down_button = QPushButton(
            "↓"
        )

        self.params_up_button.setToolTip(
            "選択行を1つ上へ移動します。"
        )
        self.params_down_button.setToolTip(
            "選択行を1つ下へ移動します。"
        )

        self.params_add_button.clicked.connect(
            self._add_param_v22
        )
        self.params_remove_button.clicked.connect(
            lambda: self._remove_table_row(
                self.params_table
            )
        )
        self.params_up_button.clicked.connect(
            lambda: self._move_v23_rule_row(
                self.params_table,
                -1,
            )
        )
        self.params_down_button.clicked.connect(
            lambda: self._move_v23_rule_row(
                self.params_table,
                1,
            )
        )

        buttons.addWidget(
            self.params_add_button
        )
        buttons.addWidget(
            self.params_remove_button
        )
        buttons.addSpacing(
            8
        )
        buttons.addWidget(
            self.params_up_button
        )
        buttons.addWidget(
            self.params_down_button
        )
        buttons.addStretch(
            1
        )

        layout.addLayout(
            buttons
        )

        self.data_tabs.addTab(
            tab,
            "パラメータ",
        )

    def _move_v23_rule_row(
        self,
        table,
        delta: int,
    ):
        if not self._edit_mode:
            return

        row = table.currentRow()
        target = row + delta

        if not (
            0 <= row < table.rowCount()
            and 0 <= target < table.rowCount()
        ):
            return

        was_blocked = table.blockSignals(
            True
        )

        try:
            items = [
                table.takeItem(
                    row,
                    column,
                )
                for column in range(
                    table.columnCount()
                )
            ]

            table.removeRow(
                row
            )
            table.insertRow(
                target
            )
            table.setRowHeight(
                target,
                36,
            )

            for column, item in enumerate(
                items
            ):
                if item is not None:
                    table.setItem(
                        target,
                        column,
                        item,
                    )

            table.setCurrentCell(
                target,
                0,
            )
        finally:
            table.blockSignals(
                was_blocked
            )

        self._apply_rule_row_editability()
        self._mark_dirty()

    def _set_v23_auto_cell(
        self,
        item,
        *,
        automatic: bool,
        tooltip: str = "",
    ):
        if item is None:
            return

        item.setToolTip(
            tooltip
        )

        if automatic:
            item.setBackground(
                QColor(
                    "#201c31"
                )
            )
        else:
            item.setData(
                Qt.ItemDataRole.BackgroundRole,
                None,
            )

    def _apply_rule_row_editability(self):
        # Keep the Phase 22B freeze fix, then add visual hints.
        super()._apply_rule_row_editability()

        if not hasattr(
            self,
            "status_table",
        ):
            return

        status_was_blocked = (
            self.status_table.blockSignals(
                True
            )
        )
        params_was_blocked = (
            self.params_table.blockSignals(
                True
            )
        )

        try:
            for row in range(
                self.status_table.rowCount()
            ):
                initial_item = (
                    self.status_table.item(
                        row,
                        3,
                    )
                )
                max_formula_item = (
                    self.status_table.item(
                        row,
                        4,
                    )
                )

                initial_formula = (
                    initial_item.text().strip()
                    if initial_item
                    else ""
                )
                max_formula = (
                    max_formula_item.text().strip()
                    if max_formula_item
                    else ""
                )

                current_item = (
                    self.status_table.item(
                        row,
                        1,
                    )
                )
                max_item = (
                    self.status_table.item(
                        row,
                        2,
                    )
                )

                self._set_v23_auto_cell(
                    current_item,
                    automatic=False,
                    tooltip=(
                        "初期式を持つステータスです。"
                        "現在値は手動で変更できます。"
                        if initial_formula
                        else ""
                    ),
                )
                self._set_v23_auto_cell(
                    max_item,
                    automatic=bool(
                        max_formula
                    ),
                    tooltip=(
                        "ルール式から自動計算される最大値です。"
                        if max_formula
                        else ""
                    ),
                )

            for row in range(
                self.params_table.rowCount()
            ):
                formula_item = (
                    self.params_table.item(
                        row,
                        2,
                    )
                )
                formula = (
                    formula_item.text().strip()
                    if formula_item
                    else ""
                )

                self._set_v23_auto_cell(
                    self.params_table.item(
                        row,
                        1,
                    ),
                    automatic=bool(
                        formula
                    ),
                    tooltip=(
                        "ルール式から自動計算される値です。"
                        if formula
                        else ""
                    ),
                )
        finally:
            self.status_table.blockSignals(
                status_was_blocked
            )
            self.params_table.blockSignals(
                params_was_blocked
            )

    def _apply_selected_template(self):
        if not self._edit_mode:
            return

        template_id = (
            self.template_combo.currentData()
            or "generic"
        )

        template_name = (
            self.template_combo.currentText()
            or str(
                template_id
            )
        )

        if template_id == "generic":
            message = (
                f"「{template_name}」へ切り替えます。\n\n"
                "既存のステータス・パラメータ・式は削除されません。"
                "\n続行しますか？"
            )
        else:
            message = (
                f"「{template_name}」を適用します。\n\n"
                "不足している項目とルール式を補完します。"
                "また、HP・MP・SANなど式を持つステータスの"
                "現在値がルール初期値へ再計算される場合があります。"
                "\n続行しますか？"
            )

        answer = QMessageBox.question(
            self,
            "テンプレートを適用",
            message,
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):
            self._restore_v23_template_combo()
            return

        if self.dirty:
            if not self.save(
                show_error=True
            ):
                return

        try:
            apply_template_v22(
                self.character_id,
                template_id,
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "テンプレート",
                str(
                    exc
                ),
            )
            self._restore_v23_template_combo()
            return

        self._template_id = str(
            template_id
            or ""
        )

        old_loading = self.loading
        self.loading = True

        try:
            self._load()
        finally:
            self.loading = old_loading

        self._set_save_state(
            "保存済み"
        )
        self.saved.emit()
        self.changed.emit()

    def _restore_v23_template_combo(self):
        active = (
            self._template_id
            or "generic"
        )
        index = self.template_combo.findData(
            active
        )

        if index < 0:
            index = 0

        self.template_combo.blockSignals(
            True
        )
        self.template_combo.setCurrentIndex(
            index
        )
        self.template_combo.blockSignals(
            False
        )

    def set_edit_mode(
        self,
        enabled: bool,
    ):
        super().set_edit_mode(
            enabled
        )

        for name in (
            "status_up_button",
            "status_down_button",
            "params_up_button",
            "params_down_button",
        ):
            widget = getattr(
                self,
                name,
                None,
            )

            if widget is not None:
                widget.setVisible(
                    self._edit_mode
                )

    def save(
        self,
        show_error: bool = True,
    ) -> bool:
        self._set_save_state(
            "保存中…"
        )

        # The active template only changes through
        # _apply_selected_template(). Merely selecting the combobox must
        # never mutate template_id during autosave/manual save.
        template_id = str(
            self._template_id
            or ""
        )

        try:
            bundle = save_v22_bundle(
                self.character_id,
                {
                    "name": self.name_edit.text(),
                    "player_name": self.player_edit.text(),
                    "initiative": self.initiative_edit.text(),
                    "external_url": self.external_url_edit.text(),
                    "color": (
                        self.color_edit.text().strip()
                        or "#888888"
                    ),
                    "secret": self.secret_check.isChecked(),
                    "invisible": self.invisible_check.isChecked(),
                    "hide_status": self.hide_status_check.isChecked(),
                },
                self._collect_images(),
                self._collect_statuses_v22(),
                self._collect_params_v22(),
                list(
                    self.memo_records
                ),
                self._collect_tag_names(),
                self._collect_group_ids(),
                template_id,
            )

            save_skills_and_palettes(
                self.character_id,
                self.skills_editor.skills(),
                list(
                    self.palette_records
                ),
            )
        except Exception as exc:
            self._set_save_state(
                "保存エラー"
            )

            if show_error:
                QMessageBox.warning(
                    self,
                    "保存できません",
                    str(
                        exc
                    ),
                )

            return False

        self.template_id_edit.setText(
            template_id
        )

        self._sync_rule_values_from_bundle(
            bundle
        )

        self.dirty = False
        self._set_save_state(
            "保存済み"
        )
        self.saved.emit()
        self.changed.emit()
        self._setup_tag_completer()
        self._recalculate_advanced_previews()
        return True


class CharacterEditorDialog(
    Phase23CharacterDialog
):
    def __init__(
        self,
        character_id: str,
        parent=None,
    ):
        super().__init__(
            character_id,
            parent,
            start_edit=True,
        )


CharacterViewDialog = Phase23CharacterDialog

# ---------------------------------------------------------------------------
# Phase 23.1: restore drag & drop route for portrait image area
# ---------------------------------------------------------------------------

from PySide6.QtCore import QEvent


class Phase231DragDropCharacterDialog(
    Phase23CharacterDialog
):
    def _build_ui(self):
        super()._build_ui()
        self._install_portrait_drop_target()

    def _install_portrait_drop_target(self):
        if not hasattr(
            self,
            "portrait_label",
        ):
            return

        self.portrait_label.installEventFilter(
            self
        )
        self._set_portrait_drop_state(
            hover=False
        )

    def _set_portrait_drop_state(
        self,
        *,
        hover: bool,
    ):
        if not hasattr(
            self,
            "portrait_label",
        ):
            return

        enabled = bool(
            getattr(
                self,
                "_edit_mode",
                False,
            )
        )

        self.portrait_label.setAcceptDrops(
            enabled
        )
        self.portrait_label.setProperty(
            "dropEnabled",
            enabled,
        )
        self.portrait_label.setProperty(
            "dropHover",
            enabled and hover,
        )

        if enabled:
            self.portrait_label.setToolTip(
                "編集モード中はここへ画像をドラッグ＆ドロップできます。"
                "複数枚ドロップした場合は画像差分として追加されます。"
            )
        else:
            self.portrait_label.setToolTip(
                ""
            )

        style = self.portrait_label.style()
        style.unpolish(
            self.portrait_label
        )
        style.polish(
            self.portrait_label
        )
        self.portrait_label.update()

    def _dropped_image_paths(
        self,
        event,
    ) -> list[str]:
        mime = event.mimeData()

        if not mime or not mime.hasUrls():
            return []

        paths = []

        for url in mime.urls():
            if not url.isLocalFile():
                continue

            path = Path(
                url.toLocalFile()
            )

            if not path.is_file():
                continue

            if (
                path.suffix.lower()
                not in IMAGE_EXTENSIONS
            ):
                continue

            paths.append(
                str(path)
            )

        return paths

    def _portrait_drop_insert_at(
        self,
    ) -> int:
        if not hasattr(
            self,
            "image_list",
        ):
            return 0

        current = -1

        if hasattr(
            self,
            "image_combo",
        ):
            current = self.image_combo.currentIndex()

        if not (
            0 <= current < self.image_list.count()
        ):
            current = self.image_list.currentRow()

        if 0 <= current < self.image_list.count():
            return current + 1

        return self.image_list.count()

    def _handle_portrait_drop(
        self,
        paths: list[str],
    ):
        if not (
            self._edit_mode
            and paths
            and hasattr(
                self,
                "_external_images_dropped",
            )
        ):
            return

        before = (
            self.image_list.count()
            if hasattr(
                self,
                "image_list",
            )
            else 0
        )
        insert_at = self._portrait_drop_insert_at()

        self._external_images_dropped(
            paths,
            insert_at,
        )

        after = self.image_list.count()
        added = after - before

        if added <= 0:
            return

        row = min(
            insert_at + added - 1,
            after - 1,
        )

        self.image_list.setCurrentRow(
            row
        )
        self._refresh_image_combo(row)
        self._preview_image_row(row)

    def eventFilter(
        self,
        watched,
        event,
    ):
        if (
            hasattr(
                self,
                "portrait_label",
            )
            and watched is self.portrait_label
        ):
            event_type = event.type()

            if event_type == QEvent.Type.DragEnter:
                paths = self._dropped_image_paths(
                    event
                )

                if self._edit_mode and paths:
                    self._set_portrait_drop_state(
                        hover=True
                    )
                    event.acceptProposedAction()
                    return True

                event.ignore()
                return True

            if event_type == QEvent.Type.DragMove:
                paths = self._dropped_image_paths(
                    event
                )

                if self._edit_mode and paths:
                    event.acceptProposedAction()
                    return True

                event.ignore()
                return True

            if event_type == QEvent.Type.DragLeave:
                self._set_portrait_drop_state(
                    hover=False
                )
                return False

            if event_type == QEvent.Type.Drop:
                paths = self._dropped_image_paths(
                    event
                )

                self._set_portrait_drop_state(
                    hover=False
                )

                if self._edit_mode and paths:
                    self._handle_portrait_drop(
                        paths
                    )
                    event.acceptProposedAction()
                    return True

                event.ignore()
                return True

        return super().eventFilter(
            watched,
            event,
        )

    def set_edit_mode(
        self,
        enabled: bool,
    ):
        super().set_edit_mode(
            enabled
        )
        self._set_portrait_drop_state(
            hover=False
        )


class CharacterEditorDialog(
    Phase231DragDropCharacterDialog
):
    def __init__(
        self,
        character_id: str,
        parent=None,
    ):
        super().__init__(
            character_id,
            parent,
            start_edit=True,
        )


CharacterViewDialog = Phase231DragDropCharacterDialog

# PHASE37_QUICK_MEMO_AND_GROUP_COLLAPSE
from app.services.quick_memo_service import (
    get_quick_memo as get_quick_memo_v37,
    set_quick_memo as set_quick_memo_v37,
)


class Phase37CharacterDialog(
    Phase231DragDropCharacterDialog
):
    def _build_ui(self):
        super()._build_ui()

        self.quick_memo_editor = QTextEdit()
        self.quick_memo_editor.setPlaceholderText(
            "CCMサイドパネルの臨時メモ"
        )
        self.quick_memo_editor.setMaximumHeight(
            110
        )
        self.quick_memo_editor.textChanged.connect(
            self._mark_dirty
        )

        quick_label = QLabel(
            "Quick Memo / 臨時メモ"
        )
        quick_label.setObjectName(
            "SectionTitle"
        )

        target_layout = None

        if hasattr(
            self,
            "memo_title",
        ):
            parent = self.memo_title.parentWidget()

            if parent is not None:
                target_layout = parent.layout()

        if target_layout is not None:
            index = target_layout.indexOf(
                self.memo_title
            )

            if index < 0:
                index = 0

            target_layout.insertWidget(
                index,
                quick_label,
            )
            target_layout.insertWidget(
                index + 1,
                self.quick_memo_editor,
            )

    def _load(self):
        super()._load()

        if not hasattr(
            self,
            "quick_memo_editor",
        ):
            return

        blocked = self.quick_memo_editor.blockSignals(
            True
        )

        try:
            self.quick_memo_editor.setPlainText(
                get_quick_memo_v37(
                    self.character_id
                )
            )
        finally:
            self.quick_memo_editor.blockSignals(
                blocked
            )

    def _load_group_tree(
        self,
        selected_ids,
    ):
        super()._load_group_tree(
            selected_ids
        )

        if not hasattr(
            self,
            "group_tree",
        ):
            return

        self.group_tree.collapseAll()

        selected = {
            str(value)
            for value in selected_ids
        }

        def walk(item):
            group_id = item.data(
                0,
                Qt.ItemDataRole.UserRole,
            )

            if str(group_id) in selected:
                parent = item.parent()

                while parent is not None:
                    parent.setExpanded(
                        True
                    )
                    parent = parent.parent()

            for i in range(
                item.childCount()
            ):
                walk(
                    item.child(i)
                )

        for i in range(
            self.group_tree.topLevelItemCount()
        ):
            walk(
                self.group_tree.topLevelItem(i)
            )

    def set_edit_mode(
        self,
        enabled: bool,
    ):
        super().set_edit_mode(
            enabled
        )

        if hasattr(
            self,
            "quick_memo_editor",
        ):
            self.quick_memo_editor.setReadOnly(
                not self._edit_mode
            )

    def save(
        self,
        show_error: bool = True,
    ) -> bool:
        ok = super().save(
            show_error=show_error
        )

        if not ok:
            return False

        try:
            set_quick_memo_v37(
                self.character_id,
                self.quick_memo_editor.toPlainText(),
            )
        except Exception as exc:
            self.dirty = True
            self._set_save_state(
                "保存エラー"
            )

            if show_error:
                QMessageBox.warning(
                    self,
                    "臨時メモを保存できません",
                    str(exc),
                )

            return False

        return True


class CharacterEditorDialog(
    Phase37CharacterDialog
):
    def __init__(
        self,
        character_id: str,
        parent=None,
    ):
        super().__init__(
            character_id,
            parent,
            start_edit=True,
        )


CharacterViewDialog = Phase37CharacterDialog
