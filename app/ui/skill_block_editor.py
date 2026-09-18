from __future__ import annotations

from PySide6.QtCore import (
    Qt,
    Signal,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.services.advanced_service import (
    SKILL_CATEGORIES,
)
from app.services.formula_engine import (
    resolve_value_text,
)


UNCATEGORIZED = "未分類"
FIXED_CATEGORY_ORDER = (
    SKILL_CATEGORIES
    + [UNCATEGORIZED]
)


class SkillCategoryBlock(QFrame):
    changed = Signal()
    selectionChanged = Signal(object)

    def __init__(self, category, parent=None):
        super().__init__(parent)

        self.category = str(category)
        self._loading = False

        self.setObjectName("SkillCategoryBlock")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.header_button = QToolButton()
        self.header_button.setObjectName("SkillCategoryHeader")
        self.header_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        )
        self.header_button.setArrowType(Qt.ArrowType.DownArrow)
        self.header_button.setCheckable(True)
        self.header_button.setChecked(True)
        self.header_button.toggled.connect(
            self._toggle_content
        )

        root.addWidget(self.header_button)

        self.content = QWidget()
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(8, 4, 8, 8)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(
            ["技能", "値 / 式", "現在値"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.table.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        header = self.table.horizontalHeader()
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
            QHeaderView.ResizeMode.ResizeToContents,
        )

        self.table.itemChanged.connect(self._item_changed)
        self.table.itemSelectionChanged.connect(
            lambda: self.selectionChanged.emit(self)
        )

        content_layout.addWidget(self.table)
        root.addWidget(self.content)

        self._update_header()
        self._update_height()

    def _readonly_item(self, text=""):
        item = QTableWidgetItem(str(text))
        item.setFlags(
            item.flags()
            & ~Qt.ItemFlag.ItemIsEditable
        )
        return item

    def _toggle_content(self, checked):
        self.content.setVisible(checked)
        self.header_button.setArrowType(
            Qt.ArrowType.DownArrow
            if checked
            else Qt.ArrowType.RightArrow
        )

    def _item_changed(self, item):
        if self._loading:
            return

        if item.column() == 2:
            return

        self.changed.emit()

    def _update_header(self):
        self.header_button.setText(
            f"{self.category}  ({self.table.rowCount()})"
        )

    def _update_height(self):
        rows = max(1, self.table.rowCount())

        header_height = (
            self.table
            .horizontalHeader()
            .height()
        )

        self.table.setFixedHeight(
            header_height
            + rows * 34
            + 4
        )

    def clear(self):
        self._loading = True
        self.table.setRowCount(0)
        self._loading = False
        self._update_header()
        self._update_height()

    def add_skill(self, label="", value=""):
        self._loading = True

        row = self.table.rowCount()
        self.table.insertRow(row)
        self.table.setRowHeight(row, 34)

        self.table.setItem(
            row,
            0,
            QTableWidgetItem(str(label)),
        )
        self.table.setItem(
            row,
            1,
            QTableWidgetItem(str(value)),
        )
        self.table.setItem(
            row,
            2,
            self._readonly_item(""),
        )

        self._loading = False

        self._update_header()
        self._update_height()

        return row

    def remove_selected(self):
        row = self.table.currentRow()

        if row < 0:
            return False

        self.table.removeRow(row)
        self._update_header()
        self._update_height()
        self.changed.emit()

        return True

    def selected_skill(self):
        row = self.table.currentRow()

        if row < 0:
            return None

        label_item = self.table.item(row, 0)
        value_item = self.table.item(row, 1)

        return {
            "label": (
                label_item.text()
                if label_item
                else ""
            ),
            "value": (
                value_item.text()
                if value_item
                else ""
            ),
            "row": row,
        }

    def take_selected_skill(self):
        selected = self.selected_skill()

        if selected is None:
            return None

        row = selected.pop("row")

        self._loading = True
        self.table.removeRow(row)
        self._loading = False

        self._update_header()
        self._update_height()

        return selected

    def rows(self):
        output = []

        for row in range(self.table.rowCount()):
            label_item = self.table.item(row, 0)
            value_item = self.table.item(row, 1)

            output.append(
                {
                    "label": (
                        label_item.text()
                        if label_item
                        else ""
                    ),
                    "value": (
                        value_item.text()
                        if value_item
                        else ""
                    ),
                    "category": self.category,
                }
            )

        return output

    def refresh_previews(self, source_values):
        self._loading = True

        for row in range(self.table.rowCount()):
            value_item = self.table.item(row, 1)

            raw = (
                value_item.text()
                if value_item
                else ""
            )

            result, error = resolve_value_text(
                raw,
                source_values,
            )

            preview = self.table.item(row, 2)

            if preview is None:
                preview = self._readonly_item("")
                self.table.setItem(
                    row,
                    2,
                    preview,
                )

            preview.setText(
                result if not error else "!"
            )
            preview.setToolTip(error)

        self._loading = False


class SkillBlockEditor(QWidget):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        self.blocks = {}
        self.block_order = []
        self._loading = False
        self._selected_block = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(8)

        note = QLabel(
            "CoC6技能をカテゴリ別に表示します。"
            "見出しをクリックすると折りたためます。"
        )
        note.setObjectName("MutedText")
        root.addWidget(note)

        controls = QHBoxLayout()

        controls.addWidget(QLabel("カテゴリ"))

        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItems(
            FIXED_CATEGORY_ORDER
        )
        self.category_combo.setMinimumWidth(150)

        add_button = QPushButton("技能を追加")
        move_button = QPushButton("選択技能を移動")
        remove_button = QPushButton("選択技能を削除")

        add_button.clicked.connect(self._add_skill)
        move_button.clicked.connect(self._move_selected)
        remove_button.clicked.connect(self._remove_selected)

        controls.addWidget(self.category_combo)
        controls.addWidget(add_button)
        controls.addWidget(move_button)
        controls.addWidget(remove_button)
        controls.addStretch(1)

        root.addLayout(controls)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)

        self.container = QWidget()
        self.blocks_layout = QVBoxLayout(self.container)
        self.blocks_layout.setContentsMargins(0, 0, 0, 0)
        self.blocks_layout.setSpacing(8)

        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll, 1)

        # 先に固定カテゴリを正しい順序で作る。
        for category in FIXED_CATEGORY_ORDER:
            self._create_block_at_end(category)

        self.blocks_layout.addStretch(1)

    def _create_block_at_end(self, category):
        category = (
            str(category).strip()
            or UNCATEGORIZED
        )

        if category in self.blocks:
            return self.blocks[category]

        block = SkillCategoryBlock(
            category,
            self,
        )
        block.changed.connect(self._block_changed)
        block.selectionChanged.connect(self._selection_changed)

        # stretch追加前なら普通に末尾追加。
        # stretch追加後ならその直前へ挿入。
        count = self.blocks_layout.count()

        if (
            count > 0
            and self.blocks_layout.itemAt(
                count - 1
            ).spacerItem()
            is not None
        ):
            self.blocks_layout.insertWidget(
                count - 1,
                block,
            )
        else:
            self.blocks_layout.addWidget(block)

        self.blocks[category] = block
        self.block_order.append(category)

        if self.category_combo.findText(category) < 0:
            self.category_combo.addItem(category)

        return block

    def _ensure_block(self, category):
        category = (
            str(category).strip()
            or UNCATEGORIZED
        )

        if category in self.blocks:
            return self.blocks[category]

        # 独自カテゴリは未分類の直前へ配置。
        block = SkillCategoryBlock(
            category,
            self,
        )
        block.changed.connect(self._block_changed)
        block.selectionChanged.connect(self._selection_changed)

        uncategorized_block = self.blocks.get(UNCATEGORIZED)

        if uncategorized_block is not None:
            index = self.blocks_layout.indexOf(
                uncategorized_block
            )
            self.blocks_layout.insertWidget(
                index,
                block,
            )

            uncategorized_order_index = (
                self.block_order.index(UNCATEGORIZED)
            )
            self.block_order.insert(
                uncategorized_order_index,
                category,
            )
        else:
            self._create_block_at_end(category)
            return self.blocks[category]

        self.blocks[category] = block

        if self.category_combo.findText(category) < 0:
            self.category_combo.addItem(category)

        return block

    def _selection_changed(self, block):
        if block.table.currentRow() < 0:
            return

        self._selected_block = block

        for other in self.blocks.values():
            if other is block:
                continue

            other.table.blockSignals(True)
            other.table.clearSelection()
            other.table.blockSignals(False)

    def _block_changed(self):
        if not self._loading:
            self.changed.emit()

    def _target_category(self):
        return (
            self.category_combo
            .currentText()
            .strip()
            or UNCATEGORIZED
        )

    def _add_skill(self):
        category = self._target_category()
        block = self._ensure_block(category)

        row = block.add_skill("", "")
        block.header_button.setChecked(True)
        block.table.setCurrentCell(row, 0)
        block.table.editItem(
            block.table.item(row, 0)
        )

        self._selected_block = block
        self.changed.emit()

    def _move_selected(self):
        block = self._selected_block

        if (
            block is None
            or block.table.currentRow() < 0
        ):
            QMessageBox.information(
                self,
                "技能を選択",
                "移動する技能を選択してください。",
            )
            return

        target_category = self._target_category()

        if target_category == block.category:
            return

        data = block.take_selected_skill()

        if data is None:
            return

        target = self._ensure_block(target_category)

        row = target.add_skill(
            data["label"],
            data["value"],
        )

        target.header_button.setChecked(True)
        target.table.setCurrentCell(row, 0)

        self._selected_block = target
        self.changed.emit()

    def _remove_selected(self):
        block = self._selected_block

        if block is None:
            return

        if block.remove_selected():
            self.changed.emit()

    def set_skills(self, rows):
        self._loading = True

        for block in self.blocks.values():
            block.clear()

        for row in rows:
            category = (
                str(
                    row.get(
                        "category",
                        "",
                    )
                    or ""
                ).strip()
                or UNCATEGORIZED
            )

            block = self._ensure_block(category)

            block.add_skill(
                row.get("label", ""),
                row.get("value", ""),
            )

        self._loading = False

    def skills(self):
        output = []

        for category in self.block_order:
            block = self.blocks[category]

            for row in block.rows():
                if (
                    not row["label"].strip()
                    and not row["value"].strip()
                ):
                    continue

                output.append(row)

        return output

    def refresh_previews(self, source_values):
        for category in self.block_order:
            self.blocks[
                category
            ].refresh_previews(
                source_values
            )
