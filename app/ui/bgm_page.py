from __future__ import annotations

# BGM_DESKTOP_UI_V1

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services.bgm_service import (
    add_group_to_bgm,
    add_tags_to_bgm,
    create_bgm_group,
    delete_bgm_assets,
    delete_bgm_group,
    get_bgm_asset_bundle,
    import_bgm_assets,
    list_bgm_assets,
    list_bgm_groups,
    list_bgm_tags,
    rename_bgm_group,
    set_bgm_groups,
    set_bgm_tags,
    update_bgm_asset,
)


ROLE_BGM_ID = Qt.ItemDataRole.UserRole
ROLE_FILTER_KIND = Qt.ItemDataRole.UserRole + 1
ROLE_GROUP_ID = Qt.ItemDataRole.UserRole + 2

FILTER_ALL = "all"
FILTER_UNGROUPED = "ungrouped"
FILTER_UNTAGGED = "untagged"
FILTER_GROUP = "group"

_AUDIO_FILTER = (
    "Audio Files "
    "(*.mp3 *.wav *.ogg *.oga *.m4a *.aac "
    "*.flac *.opus *.webm);;All Files (*.*)"
)

_ALLOWED_SUFFIXES = {
    ".mp3",
    ".wav",
    ".ogg",
    ".oga",
    ".m4a",
    ".aac",
    ".flac",
    ".opus",
    ".webm",
}


class BgmEditDialog(QDialog):
    def __init__(self, bundle: dict, parent=None):
        super().__init__(parent)

        asset = bundle["asset"]

        self.setWindowTitle("BGM編集")
        self.setMinimumWidth(420)

        root = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(
            str(asset.get("display_name") or "")
        )

        self.kind_combo = QComboBox()
        self.kind_combo.addItem("BGM", "bgm")
        self.kind_combo.addItem("SE", "se")
        self.kind_combo.addItem("その他", "other")

        kind = str(asset.get("media_kind") or "bgm")
        index = self.kind_combo.findData(kind)
        self.kind_combo.setCurrentIndex(max(0, index))

        self.volume_spin = QDoubleSpinBox()
        self.volume_spin.setRange(0.0, 1.0)
        self.volume_spin.setSingleStep(0.05)
        self.volume_spin.setDecimals(2)
        self.volume_spin.setValue(
            float(asset.get("default_volume") or 0.0)
        )

        self.loop_check = QCheckBox("Loopする")
        self.loop_check.setChecked(
            bool(asset.get("default_loop"))
        )

        tag_names = [
            str(tag.get("name") or "")
            for tag in bundle.get("tags", [])
            if str(tag.get("name") or "").strip()
        ]

        self.tags_edit = QLineEdit(", ".join(tag_names))
        self.tags_edit.setPlaceholderText(
            "タグをカンマ区切りで入力"
        )

        form.addRow("表示名", self.name_edit)
        form.addRow("種別", self.kind_combo)
        form.addRow("既定音量", self.volume_spin)
        form.addRow("", self.loop_check)
        form.addRow("タグ", self.tags_edit)

        root.addLayout(form)

        note = QLabel(
            "※ ここで設定する音量/Loopは"
            "BGMライブラリ側の既定値です。"
        )
        note.setWordWrap(True)
        note.setObjectName("MutedLabel")
        root.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def values(self) -> dict:
        tags = [
            part.strip()
            for part in (
                self.tags_edit.text()
                .replace("、", ",")
                .split(",")
            )
            if part.strip()
        ]

        return {
            "display_name": self.name_edit.text().strip(),
            "media_kind": str(
                self.kind_combo.currentData() or "bgm"
            ),
            "default_volume": float(
                self.volume_spin.value()
            ),
            "default_loop": bool(
                self.loop_check.isChecked()
            ),
            "tags": tags,
        }


class BgmPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_filter_kind = FILTER_ALL
        self.current_group_id: str | None = None

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(
            self.refresh_assets
        )

        self.setAcceptDrops(True)

        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top = QHBoxLayout(top_bar)
        top.setContentsMargins(16, 12, 16, 12)
        top.setSpacing(8)

        title = QLabel("BGM LIBRARY")
        title.setObjectName("AppTitle")
        top.addWidget(title)
        top.addSpacing(12)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)

        self.keyword_button = QPushButton("キーワード")
        self.keyword_button.setObjectName("SearchModeButton")
        self.keyword_button.setCheckable(True)
        self.keyword_button.setChecked(True)

        self.tag_button = QPushButton("タグ")
        self.tag_button.setObjectName("SearchModeButton")
        self.tag_button.setCheckable(True)

        self.mode_group.addButton(self.keyword_button)
        self.mode_group.addButton(self.tag_button)

        top.addWidget(self.keyword_button)
        top.addWidget(self.tag_button)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("BGMを検索")
        self.search_box.setClearButtonEnabled(True)
        top.addWidget(self.search_box, 1)

        self.kind_filter = QComboBox()
        self.kind_filter.addItem("すべて", "")
        self.kind_filter.addItem("BGM", "bgm")
        self.kind_filter.addItem("SE", "se")
        self.kind_filter.addItem("その他", "other")
        self.kind_filter.setMinimumWidth(95)
        top.addWidget(self.kind_filter)

        self.import_button = QPushButton("＋ 追加")
        self.import_button.setObjectName("PrimaryButton")
        top.addWidget(self.import_button)

        self.refresh_button = QPushButton("↻")
        self.refresh_button.setToolTip("更新")
        top.addWidget(self.refresh_button)

        root.addWidget(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        sidebar = QFrame()
        sidebar.setObjectName("SideBar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(10, 12, 10, 12)
        sidebar_layout.setSpacing(8)

        group_title_row = QHBoxLayout()
        group_title = QLabel("グループ")
        group_title.setObjectName("SectionTitle")
        group_title_row.addWidget(group_title)
        group_title_row.addStretch(1)

        self.add_group_button = QPushButton("＋")
        self.add_group_button.setToolTip("グループ追加")
        group_title_row.addWidget(self.add_group_button)

        sidebar_layout.addLayout(group_title_row)

        self.group_tree = QTreeWidget()
        self.group_tree.setHeaderHidden(True)
        self.group_tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        sidebar_layout.addWidget(self.group_tree, 1)

        tag_title = QLabel("タグ")
        tag_title.setObjectName("SectionTitle")
        sidebar_layout.addWidget(tag_title)

        self.tag_list = QListWidget()
        self.tag_list.setMaximumHeight(190)
        sidebar_layout.addWidget(self.tag_list)

        content = QFrame()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 12, 12, 12)
        content_layout.setSpacing(8)

        bulk_row = QHBoxLayout()

        self.count_label = QLabel("0件")
        self.count_label.setObjectName("MutedLabel")
        bulk_row.addWidget(self.count_label)
        bulk_row.addStretch(1)

        self.bulk_tag_button = QPushButton("タグ追加")
        self.bulk_group_button = QPushButton("グループ追加")
        self.bulk_delete_button = QPushButton("削除")

        bulk_row.addWidget(self.bulk_tag_button)
        bulk_row.addWidget(self.bulk_group_button)
        bulk_row.addWidget(self.bulk_delete_button)

        content_layout.addLayout(bulk_row)

        self.asset_list = QListWidget()
        self.asset_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.asset_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.asset_list.setAlternatingRowColors(True)
        content_layout.addWidget(self.asset_list, 1)

        hint = QLabel(
            "右クリック: 編集 / タグ / グループ / 削除　"
            "｜ 音声ファイルはこの画面へドラッグ&ドロップ可能"
        )
        hint.setObjectName("MutedLabel")
        hint.setWordWrap(True)
        content_layout.addWidget(hint)

        splitter.addWidget(sidebar)
        splitter.addWidget(content)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([250, 950])

        root.addWidget(splitter, 1)

        self.keyword_button.clicked.connect(
            self._search_mode_changed
        )
        self.tag_button.clicked.connect(
            self._search_mode_changed
        )
        self.search_box.textChanged.connect(
            lambda _text: self.search_timer.start()
        )
        self.kind_filter.currentIndexChanged.connect(
            lambda _index: self.refresh_assets()
        )
        self.import_button.clicked.connect(self.import_files)
        self.refresh_button.clicked.connect(self.refresh_all)
        self.add_group_button.clicked.connect(self.create_group)
        self.group_tree.itemSelectionChanged.connect(
            self._group_selection_changed
        )
        self.group_tree.customContextMenuRequested.connect(
            self._group_context_menu
        )
        self.tag_list.itemClicked.connect(self._tag_clicked)
        self.asset_list.customContextMenuRequested.connect(
            self._asset_context_menu
        )
        self.asset_list.itemDoubleClicked.connect(
            lambda item: self.edit_asset(
                str(item.data(ROLE_BGM_ID) or "")
            )
        )
        self.bulk_tag_button.clicked.connect(
            self.bulk_add_tags
        )
        self.bulk_group_button.clicked.connect(
            self.bulk_add_group
        )
        self.bulk_delete_button.clicked.connect(
            self.bulk_delete
        )

    def activate(self) -> None:
        self.refresh_all()

    def _current_search_mode(self) -> str:
        if self.tag_button.isChecked():
            return "tag"
        return "keyword"

    def _search_mode_changed(self) -> None:
        self.refresh_assets()

    def refresh_all(self) -> None:
        self.refresh_groups()
        self.refresh_tags()
        self.refresh_assets()

    def refresh_groups(self) -> None:
        selected_id = self.current_group_id
        selected_kind = self.current_filter_kind

        rows = [dict(row) for row in list_bgm_groups()]

        self.group_tree.blockSignals(True)
        self.group_tree.clear()

        all_item = QTreeWidgetItem(["すべて"])
        all_item.setData(
            0, ROLE_FILTER_KIND, FILTER_ALL
        )
        self.group_tree.addTopLevelItem(all_item)

        ungrouped = QTreeWidgetItem(["未分類"])
        ungrouped.setData(
            0, ROLE_FILTER_KIND, FILTER_UNGROUPED
        )
        self.group_tree.addTopLevelItem(ungrouped)

        untagged = QTreeWidgetItem(["タグ無し"])
        untagged.setData(
            0, ROLE_FILTER_KIND, FILTER_UNTAGGED
        )
        self.group_tree.addTopLevelItem(untagged)

        by_parent: dict[str | None, list[dict]] = {}

        for row in rows:
            parent = row.get("parent_group_id")
            parent = (
                str(parent)
                if parent is not None
                else None
            )
            by_parent.setdefault(parent, []).append(row)

        def add_children(parent_item, parent_id):
            for row in by_parent.get(parent_id, []):
                item = QTreeWidgetItem([str(row["name"])])
                item.setData(
                    0, ROLE_FILTER_KIND, FILTER_GROUP
                )
                item.setData(
                    0, ROLE_GROUP_ID, str(row["id"])
                )

                if parent_item is None:
                    self.group_tree.addTopLevelItem(item)
                else:
                    parent_item.addChild(item)

                add_children(item, str(row["id"]))

        add_children(None, None)

        target = None
        root_item = self.group_tree.invisibleRootItem()
        stack = [
            root_item.child(i)
            for i in range(root_item.childCount())
        ]

        while stack:
            item = stack.pop(0)
            kind = item.data(0, ROLE_FILTER_KIND)
            group_id = item.data(0, ROLE_GROUP_ID)

            if (
                kind == selected_kind
                and (
                    kind != FILTER_GROUP
                    or str(group_id) == str(selected_id)
                )
            ):
                target = item
                break

            for i in range(item.childCount()):
                stack.append(item.child(i))

        if target is None:
            target = all_item
            self.current_filter_kind = FILTER_ALL
            self.current_group_id = None

        self.group_tree.setCurrentItem(target)
        self.group_tree.expandAll()
        self.group_tree.blockSignals(False)

    def refresh_tags(self) -> None:
        self.tag_list.clear()

        for row in list_bgm_tags():
            self.tag_list.addItem(
                QListWidgetItem(str(row["name"] or ""))
            )

    def refresh_assets(self) -> None:
        try:
            rows = list_bgm_assets(
                search_text=self.search_box.text().strip(),
                search_mode=self._current_search_mode(),
                group_id=(
                    self.current_group_id
                    if self.current_filter_kind == FILTER_GROUP
                    else None
                ),
                only_ungrouped=(
                    self.current_filter_kind == FILTER_UNGROUPED
                ),
                only_untagged=(
                    self.current_filter_kind == FILTER_UNTAGGED
                ),
                media_kind=(
                    str(self.kind_filter.currentData() or "")
                    or None
                ),
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "BGM読込失敗",
                str(exc),
            )
            return

        self.asset_list.clear()

        for row in rows:
            item = QListWidgetItem()
            item.setData(ROLE_BGM_ID, str(row["id"]))

            name = str(
                row["display_name"]
                or row["original_filename"]
                or "(名称なし)"
            )
            kind = str(row["media_kind"] or "bgm").upper()
            volume = float(row["default_volume"] or 0)
            loop = "LOOP" if bool(row["default_loop"]) else "1SHOT"

            local_state = (
                "LOCAL"
                if str(row["local_path"] or "").strip()
                else "REMOTE"
            )
            ccfolia_state = (
                "CCFOLIA"
                if str(row["ccfolia_url"] or "").strip()
                else "未登録"
            )

            duration_ms = int(row["duration_ms"] or 0)
            duration = (
                self._format_duration(duration_ms)
                if duration_ms > 0
                else "--:--"
            )

            item.setText(
                f"{name}\n"
                f"{kind}  |  {duration}  |  "
                f"VOL {volume:.2f}  |  {loop}  |  "
                f"{local_state}  |  {ccfolia_state}"
            )
            item.setToolTip(
                str(row["original_filename"] or name)
            )

            self.asset_list.addItem(item)

        self.count_label.setText(f"{len(rows)}件")

    @staticmethod
    def _format_duration(duration_ms: int) -> str:
        total_seconds = max(
            0, int(duration_ms // 1000)
        )
        minutes, seconds = divmod(total_seconds, 60)
        hours, minutes = divmod(minutes, 60)

        if hours:
            return (
                f"{hours}:{minutes:02d}:{seconds:02d}"
            )

        return f"{minutes}:{seconds:02d}"

    def _selected_ids(self) -> list[str]:
        return [
            str(item.data(ROLE_BGM_ID) or "")
            for item in self.asset_list.selectedItems()
            if str(item.data(ROLE_BGM_ID) or "").strip()
        ]

    def _group_selection_changed(self) -> None:
        item = self.group_tree.currentItem()

        if item is None:
            return

        kind = str(
            item.data(0, ROLE_FILTER_KIND)
            or FILTER_ALL
        )
        self.current_filter_kind = kind

        if kind == FILTER_GROUP:
            self.current_group_id = str(
                item.data(0, ROLE_GROUP_ID) or ""
            )
        else:
            self.current_group_id = None

        self.refresh_assets()

    def _tag_clicked(self, item: QListWidgetItem) -> None:
        self.tag_button.setChecked(True)
        self.keyword_button.setChecked(False)
        self.search_box.setText(item.text())
        self.refresh_assets()

    def import_files(self) -> None:
        paths, _selected = QFileDialog.getOpenFileNames(
            self,
            "BGMを追加",
            "",
            _AUDIO_FILTER,
        )

        if paths:
            self._import_paths(paths)

    def _import_paths(self, paths) -> None:
        result = import_bgm_assets(
            paths,
            media_kind="bgm",
            deduplicate=True,
        )

        self.refresh_all()

        error_count = len(result["errors"])

        message = (
            f"新規: {result['created']}件\n"
            f"重複: {result['duplicates']}件"
        )

        if error_count:
            message += f"\n失敗: {error_count}件"

        QMessageBox.information(
            self,
            "BGM追加",
            message,
        )

    def dragEnterEvent(
        self,
        event: QDragEnterEvent,
    ) -> None:
        urls = (
            event.mimeData().urls()
            if event.mimeData().hasUrls()
            else []
        )

        if any(
            url.isLocalFile()
            and Path(url.toLocalFile()).suffix.lower()
            in _ALLOWED_SUFFIXES
            for url in urls
        ):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(
        self,
        event: QDropEvent,
    ) -> None:
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if (
                url.isLocalFile()
                and Path(url.toLocalFile()).suffix.lower()
                in _ALLOWED_SUFFIXES
            )
        ]

        if not paths:
            event.ignore()
            return

        event.acceptProposedAction()
        self._import_paths(paths)

    def edit_asset(self, bgm_id: str) -> None:
        bundle = get_bgm_asset_bundle(bgm_id)

        if bundle is None:
            QMessageBox.warning(
                self,
                "BGM編集",
                "BGMが見つかりません。",
            )
            return

        dialog = BgmEditDialog(bundle, self)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        values = dialog.values()

        try:
            update_bgm_asset(
                bgm_id,
                display_name=values["display_name"],
                default_volume=values["default_volume"],
                default_loop=values["default_loop"],
                media_kind=values["media_kind"],
            )
            set_bgm_tags(
                bgm_id,
                values["tags"],
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "BGM編集失敗",
                str(exc),
            )
            return

        self.refresh_all()

    def _asset_context_menu(self, pos) -> None:
        item = self.asset_list.itemAt(pos)

        if item is None:
            return

        if not item.isSelected():
            self.asset_list.clearSelection()
            item.setSelected(True)

        ids = self._selected_ids()
        menu = QMenu(self)

        if len(ids) == 1:
            edit_action = QAction("編集", menu)
            edit_action.triggered.connect(
                lambda: self.edit_asset(ids[0])
            )
            menu.addAction(edit_action)
            menu.addSeparator()

        tags_action = QAction("タグを追加", menu)
        tags_action.triggered.connect(
            self.bulk_add_tags
        )
        menu.addAction(tags_action)

        group_action = QAction("グループに追加", menu)
        group_action.triggered.connect(
            self.bulk_add_group
        )
        menu.addAction(group_action)

        if len(ids) == 1:
            set_groups_action = QAction(
                "所属グループを設定",
                menu,
            )
            set_groups_action.triggered.connect(
                lambda: self.set_asset_groups(ids[0])
            )
            menu.addAction(set_groups_action)

        menu.addSeparator()

        delete_action = QAction("削除", menu)
        delete_action.triggered.connect(
            self.bulk_delete
        )
        menu.addAction(delete_action)

        menu.exec(
            self.asset_list.mapToGlobal(pos)
        )

    def bulk_add_tags(self) -> None:
        ids = self._selected_ids()

        if not ids:
            return

        text, ok = QInputDialog.getText(
            self,
            "タグ追加",
            "追加するタグ（カンマ区切り）",
        )

        if not ok:
            return

        names = [
            part.strip()
            for part in (
                text.replace("、", ",").split(",")
            )
            if part.strip()
        ]

        if not names:
            return

        try:
            add_tags_to_bgm(ids, names)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "タグ追加失敗",
                str(exc),
            )
            return

        self.refresh_all()

    def _choose_group_id(self, title: str) -> str | None:
        rows = [dict(row) for row in list_bgm_groups()]

        if not rows:
            QMessageBox.information(
                self,
                title,
                "グループがありません。",
            )
            return None

        labels = []
        ids = []
        names_by_id = {
            str(row["id"]): str(row["name"])
            for row in rows
        }

        for row in rows:
            group_id = str(row["id"])
            parent_id = (
                str(row["parent_group_id"])
                if row["parent_group_id"] is not None
                else None
            )

            if parent_id:
                label = (
                    f"{names_by_id.get(parent_id, '…')}"
                    f" / {row['name']}"
                )
            else:
                label = str(row["name"])

            labels.append(label)
            ids.append(group_id)

        label, ok = QInputDialog.getItem(
            self,
            title,
            "グループ",
            labels,
            0,
            False,
        )

        if not ok:
            return None

        try:
            index = labels.index(label)
        except ValueError:
            return None

        return ids[index]

    def bulk_add_group(self) -> None:
        ids = self._selected_ids()

        if not ids:
            return

        group_id = self._choose_group_id(
            "グループ追加"
        )

        if not group_id:
            return

        try:
            add_group_to_bgm(ids, group_id)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "グループ追加失敗",
                str(exc),
            )
            return

        self.refresh_all()

    def set_asset_groups(self, bgm_id: str) -> None:
        rows = [dict(row) for row in list_bgm_groups()]

        if not rows:
            QMessageBox.information(
                self,
                "所属グループ",
                "グループがありません。",
            )
            return

        bundle = get_bgm_asset_bundle(bgm_id)

        if bundle is None:
            return

        current = {
            str(value)
            for value in bundle.get("group_ids", [])
        }

        dialog = QDialog(self)
        dialog.setWindowTitle("所属グループ")
        dialog.setMinimumWidth(340)
        layout = QVBoxLayout(dialog)

        checks = []

        for row in rows:
            check = QCheckBox(str(row["name"]))
            check.setChecked(
                str(row["id"]) in current
            )
            layout.addWidget(check)
            checks.append(
                (check, str(row["id"]))
            )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        selected = [
            group_id
            for check, group_id in checks
            if check.isChecked()
        ]

        try:
            set_bgm_groups(bgm_id, selected)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "所属グループ設定失敗",
                str(exc),
            )
            return

        self.refresh_all()

    def bulk_delete(self) -> None:
        ids = self._selected_ids()

        if not ids:
            return

        answer = QMessageBox.question(
            self,
            "BGM削除",
            (
                f"{len(ids)}件を"
                "Managerから削除しますか？\n\n"
                "ローカル保存済み音源も削除されます。"
            ),
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_bgm_assets(ids)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "BGM削除失敗",
                str(exc),
            )
            return

        self.refresh_all()

    def create_group(self) -> None:
        name, ok = QInputDialog.getText(
            self,
            "グループ追加",
            "グループ名",
        )

        if not ok or not name.strip():
            return

        parent_id = (
            self.current_group_id
            if self.current_filter_kind == FILTER_GROUP
            else None
        )

        try:
            create_bgm_group(name, parent_id)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "グループ追加失敗",
                str(exc),
            )
            return

        self.refresh_groups()

    def _group_context_menu(self, pos) -> None:
        item = self.group_tree.itemAt(pos)

        if item is None:
            return

        kind = item.data(0, ROLE_FILTER_KIND)

        if kind != FILTER_GROUP:
            return

        group_id = str(
            item.data(0, ROLE_GROUP_ID) or ""
        )

        menu = QMenu(self)

        add_child = QAction(
            "子グループを追加",
            menu,
        )
        add_child.triggered.connect(
            lambda: self._create_child_group(group_id)
        )
        menu.addAction(add_child)

        rename = QAction("名前を変更", menu)
        rename.triggered.connect(
            lambda: self._rename_group(
                group_id,
                item.text(0),
            )
        )
        menu.addAction(rename)

        menu.addSeparator()

        delete = QAction("削除", menu)
        delete.triggered.connect(
            lambda: self._delete_group(
                group_id,
                item.text(0),
            )
        )
        menu.addAction(delete)

        menu.exec(
            self.group_tree.mapToGlobal(pos)
        )

    def _create_child_group(self, parent_id: str) -> None:
        name, ok = QInputDialog.getText(
            self,
            "子グループ追加",
            "グループ名",
        )

        if not ok or not name.strip():
            return

        try:
            create_bgm_group(name, parent_id)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "グループ追加失敗",
                str(exc),
            )
            return

        self.refresh_groups()

    def _rename_group(
        self,
        group_id: str,
        current_name: str,
    ) -> None:
        name, ok = QInputDialog.getText(
            self,
            "グループ名変更",
            "新しい名前",
            text=current_name,
        )

        if not ok or not name.strip():
            return

        try:
            rename_bgm_group(group_id, name)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "グループ名変更失敗",
                str(exc),
            )
            return

        self.refresh_groups()

    def _delete_group(
        self,
        group_id: str,
        name: str,
    ) -> None:
        answer = QMessageBox.question(
            self,
            "グループ削除",
            (
                f"「{name}」を削除しますか？\n"
                "BGM本体は削除されません。"
            ),
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_bgm_group(group_id)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "グループ削除失敗",
                str(exc),
            )
            return

        self.current_filter_kind = FILTER_ALL
        self.current_group_id = None
        self.refresh_all()
