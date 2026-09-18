from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
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

from app.paths import PROJECT_ROOT
from app.services.image_service import (
    add_group_to_images,
    add_tags_to_images,
    create_image_group,
    delete_image_assets,
    delete_image_group,
    get_image_asset_bundle,
    import_image_asset,
    list_image_assets,
    list_image_groups,
    list_image_tags,
    rename_image_asset,
    rename_image_group,
    set_image_tags,
)
from app.ui.tag_chip_editor import TagChipEditor


ROLE_IMAGE_ID = Qt.ItemDataRole.UserRole
ROLE_FILTER_KIND = Qt.ItemDataRole.UserRole + 1
ROLE_GROUP_ID = Qt.ItemDataRole.UserRole + 2

FILTER_ALL = "all"
FILTER_UNGROUPED = "ungrouped"
FILTER_UNTAGGED = "untagged"
FILTER_GROUP = "group"

# IMAGES_PERF_PAGED_LIST
IMAGE_PAGE_SIZE = 120


class ImagesPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_filter_kind = FILTER_ALL
        self.current_group_id: str | None = None

        self._loaded_image_count = 0
        self._total_image_count = 0
        self._loading_more_images = False

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self.refresh_images)

        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("TopBar")
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 12, 16, 12)
        top_layout.setSpacing(8)

        title = QLabel("IMAGE LIBRARY")
        title.setObjectName("AppTitle")
        top_layout.addWidget(title)
        top_layout.addSpacing(12)

        self.search_mode_group = QButtonGroup(self)
        self.search_mode_group.setExclusive(True)

        self.keyword_mode_button = QPushButton("キーワード")
        self.keyword_mode_button.setObjectName("SearchModeButton")
        self.keyword_mode_button.setCheckable(True)
        self.keyword_mode_button.setChecked(True)

        self.tag_mode_button = QPushButton("タグ")
        self.tag_mode_button.setObjectName("SearchModeButton")
        self.tag_mode_button.setCheckable(True)

        self.search_mode_group.addButton(self.keyword_mode_button)
        self.search_mode_group.addButton(self.tag_mode_button)

        self.search_mode_switch = QFrame()
        self.search_mode_switch.setObjectName("SearchModeSwitch")
        mode_layout = QHBoxLayout(self.search_mode_switch)
        mode_layout.setContentsMargins(0, 0, 0, 0)
        mode_layout.setSpacing(0)
        mode_layout.addWidget(self.keyword_mode_button)
        mode_layout.addWidget(self.tag_mode_button)

        self.keyword_mode_button.clicked.connect(self._search_mode_changed)
        self.tag_mode_button.clicked.connect(self._search_mode_changed)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("画像を検索...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(lambda: self.search_timer.start())

        self.tag_search = TagChipEditor()
        self.tag_search.set_placeholder("タグを入力して検索...")
        self.tag_search.setVisible(False)
        self.tag_search.tagsChanged.connect(self.refresh_images)

        self.selection_mode = QPushButton("選択")
        self.selection_mode.setObjectName("SelectionModeButton")
        self.selection_mode.setCheckable(True)
        self.selection_mode.setToolTip("複数画像を選択します")
        self.selection_mode.toggled.connect(self._selection_mode_changed)

        self.import_button = QPushButton("＋ 画像")
        self.import_button.setObjectName("PrimaryButton")
        self.import_button.clicked.connect(self.import_images)

        top_layout.addWidget(self.search_mode_switch)
        top_layout.addWidget(self.search_box, 1)
        top_layout.addWidget(self.tag_search, 1)
        top_layout.addWidget(self.selection_mode)
        top_layout.addWidget(self.import_button)

        root_layout.addWidget(top_bar)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setMinimumWidth(210)
        sidebar.setMaximumWidth(320)

        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 14, 12, 12)

        group_header_row = QHBoxLayout()
        group_header = QLabel("グループ")
        group_header.setObjectName("SectionTitle")

        self.add_group_button = QPushButton("＋")
        self.add_group_button.setObjectName("CompactButton")
        self.add_group_button.setFixedWidth(32)
        self.add_group_button.setToolTip("ルートグループを追加")
        self.add_group_button.clicked.connect(self.add_root_group)

        group_header_row.addWidget(group_header)
        group_header_row.addStretch(1)
        group_header_row.addWidget(self.add_group_button)

        self.group_tree = QTreeWidget()
        self.group_tree.setHeaderHidden(True)
        self.group_tree.setIndentation(16)
        self.group_tree.setAnimated(True)
        self.group_tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.group_tree.customContextMenuRequested.connect(
            self.show_group_context_menu
        )
        self.group_tree.currentItemChanged.connect(
            self.group_changed
        )

        sidebar_layout.addLayout(group_header_row)
        sidebar_layout.addWidget(self.group_tree, 1)

        content = QFrame()
        content.setObjectName("Content")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(16, 14, 16, 14)
        content_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        self.result_label = QLabel("画像")
        self.result_label.setObjectName("SectionTitle")
        header_layout.addWidget(self.result_label)
        header_layout.addStretch(1)
        content_layout.addLayout(header_layout)

        self.selection_toolbar = QFrame()
        self.selection_toolbar.setObjectName("SelectionToolbar")
        self.selection_toolbar.setVisible(False)

        selection_layout = QHBoxLayout(self.selection_toolbar)
        selection_layout.setContentsMargins(12, 8, 12, 8)
        selection_layout.setSpacing(8)

        self.selection_count_label = QLabel("0件選択")
        self.selection_count_label.setObjectName("SelectionCount")

        self.select_all_button = QPushButton("すべて選択")
        self.select_all_button.setObjectName("SelectionUtilityButton")
        self.select_all_button.clicked.connect(self.select_all_visible)

        self.clear_selection_button = QPushButton("選択解除")
        self.clear_selection_button.setObjectName("SelectionUtilityButton")
        self.clear_selection_button.clicked.connect(self.clear_selection)

        self.bulk_tag_button = QPushButton("タグ追加")
        self.bulk_tag_button.setObjectName("SelectionSecondaryAction")
        self.bulk_tag_button.clicked.connect(self.bulk_add_tags)

        self.bulk_group_button = QPushButton("グループ追加")
        self.bulk_group_button.setObjectName("SelectionSecondaryAction")
        self.bulk_group_button.clicked.connect(self.bulk_add_group)

        self.bulk_delete_button = QPushButton("削除")
        self.bulk_delete_button.setObjectName("SelectionSecondaryAction")
        self.bulk_delete_button.clicked.connect(self.delete_selected)

        selection_layout.addWidget(self.selection_count_label)
        selection_layout.addStretch(1)
        selection_layout.addWidget(self.select_all_button)
        selection_layout.addWidget(self.clear_selection_button)
        selection_layout.addSpacing(8)
        selection_layout.addWidget(self.bulk_tag_button)
        selection_layout.addWidget(self.bulk_group_button)
        selection_layout.addWidget(self.bulk_delete_button)

        content_layout.addWidget(self.selection_toolbar)

        self.image_list = QListWidget()
        self.image_list.setObjectName("ImageAssetList")
        self.image_list.setViewMode(QListView.ViewMode.IconMode)
        self.image_list.setResizeMode(QListView.ResizeMode.Adjust)
        self.image_list.setMovement(QListView.Movement.Static)
        self.image_list.setWrapping(True)
        self.image_list.setWordWrap(True)
        self.image_list.setSpacing(8)
        self.image_list.setIconSize(QSize(132, 96))
        self.image_list.setGridSize(QSize(160, 145))
        self.image_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.image_list.itemSelectionChanged.connect(
            self.update_selection_ui
        )
        self.image_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.image_list.customContextMenuRequested.connect(
            self.show_image_context_menu
        )
        self.image_list.verticalScrollBar().valueChanged.connect(
            self._maybe_load_more_images
        )

        content_layout.addWidget(self.image_list, 1)

        splitter.addWidget(sidebar)
        splitter.addWidget(content)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 940])

        root_layout.addWidget(splitter, 1)

    def activate(self) -> None:
        self.refresh_groups()
        self.refresh_tag_candidates()
        self.refresh_images()

    def _current_search_mode(self) -> str:
        if self.tag_mode_button.isChecked():
            return "tag"
        return "keyword"

    def _search_mode_changed(self, *args) -> None:
        tag_mode = self._current_search_mode() == "tag"

        self.search_box.setVisible(not tag_mode)
        self.tag_search.setVisible(tag_mode)

        if tag_mode:
            self.refresh_tag_candidates()
            self.tag_search.focus_input()
        else:
            self.search_box.setFocus()

        self.refresh_images()

    def refresh_tag_candidates(self) -> None:
        self.tag_search.set_available_tags(
            [row["name"] for row in list_image_tags()]
        )

    def _search_text(self) -> str:
        if self._current_search_mode() == "tag":
            return ", ".join(self.tag_search.tags())
        return self.search_box.text()

    def _image_query_kwargs(self) -> dict:
        kwargs = {
            "search_text": self._search_text(),
            "search_mode": self._current_search_mode(),
        }

        if self.current_filter_kind == FILTER_GROUP:
            kwargs["group_id"] = self.current_group_id
        elif self.current_filter_kind == FILTER_UNGROUPED:
            kwargs["only_ungrouped"] = True
        elif self.current_filter_kind == FILTER_UNTAGGED:
            kwargs["only_untagged"] = True

        return kwargs

    def _append_image_rows(
        self,
        rows,
        selected_ids: set[str] | None = None,
    ) -> None:
        selected_ids = selected_ids or set()

        for row in rows:
            item = QListWidgetItem(str(row["display_name"] or "画像"))
            image_id = str(row["id"])
            item.setData(ROLE_IMAGE_ID, image_id)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)

            local_path = str(row["local_path"] or "")
            if local_path:
                path = PROJECT_ROOT / local_path
                if path.exists():
                    item.setIcon(QIcon(str(path)))

            original = str(row["original_filename"] or "")
            registered = bool(row["ccfolia_registered"])
            state = "CCFOLIA登録済み" if registered else "ローカルのみ"
            tooltip_parts = [str(row["display_name"] or "画像"), state]
            if original:
                tooltip_parts.append(original)
            item.setToolTip("\n".join(tooltip_parts))

            if image_id in selected_ids and self.selection_mode.isChecked():
                item.setSelected(True)

            self.image_list.addItem(item)

    def _update_result_label(self) -> None:
        if self._total_image_count <= 0:
            self.result_label.setText("画像  0")
            return

        if self._loaded_image_count < self._total_image_count:
            self.result_label.setText(
                f"画像  {self._loaded_image_count}/{self._total_image_count}"
            )
        else:
            self.result_label.setText(f"画像  {self._total_image_count}")

    def refresh_images(self) -> None:
        selected_ids = set(self.selected_image_ids())

        try:
            rows = list_image_assets(
                **self._image_query_kwargs(),
                limit=IMAGE_PAGE_SIZE,
                offset=0,
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "画像一覧の取得に失敗",
                str(exc),
            )
            return

        self.image_list.blockSignals(True)
        self.image_list.clear()

        self._loaded_image_count = len(rows)
        self._total_image_count = (
            int(rows[0]["total_count"] or 0)
            if rows
            else 0
        )

        self._append_image_rows(rows, selected_ids)

        self.image_list.blockSignals(False)
        self._update_result_label()
        self.update_selection_ui()

        QTimer.singleShot(0, self._maybe_load_more_images)

    def _maybe_load_more_images(self, *_args) -> None:
        if self._loading_more_images:
            return

        if self._loaded_image_count >= self._total_image_count:
            return

        scrollbar = self.image_list.verticalScrollBar()

        if scrollbar.maximum() <= 0:
            near_bottom = True
        else:
            near_bottom = (
                scrollbar.value() + max(1, scrollbar.pageStep())
                >= scrollbar.maximum()
            )

        if not near_bottom:
            return

        self._loading_more_images = True

        try:
            rows = list_image_assets(
                **self._image_query_kwargs(),
                limit=IMAGE_PAGE_SIZE,
                offset=self._loaded_image_count,
            )

            if not rows:
                self._loaded_image_count = self._total_image_count
                self._update_result_label()
                return

            selected_ids = set(self.selected_image_ids())

            self.image_list.blockSignals(True)
            try:
                self._append_image_rows(rows, selected_ids)
            finally:
                self.image_list.blockSignals(False)

            self._loaded_image_count += len(rows)
            self._total_image_count = int(
                rows[0]["total_count"]
                or self._total_image_count
            )

            self._update_result_label()
            self.update_selection_ui()
        except Exception as exc:
            QMessageBox.warning(
                self,
                "画像一覧の追加取得に失敗",
                str(exc),
            )
        finally:
            self._loading_more_images = False

    def refresh_groups(self) -> None:
        selected_kind = self.current_filter_kind
        selected_group_id = self.current_group_id

        self.group_tree.blockSignals(True)
        self.group_tree.clear()

        def special_item(label: str, kind: str):
            item = QTreeWidgetItem([label])
            item.setData(0, ROLE_FILTER_KIND, kind)
            item.setData(0, ROLE_GROUP_ID, None)
            self.group_tree.addTopLevelItem(item)
            return item

        all_item = special_item("すべて", FILTER_ALL)
        ungrouped_item = special_item("未分類", FILTER_UNGROUPED)
        untagged_item = special_item("タグ無し", FILTER_UNTAGGED)

        rows = list_image_groups()
        item_map = {}

        for row in rows:
            item = QTreeWidgetItem([row["name"]])
            item.setData(0, ROLE_FILTER_KIND, FILTER_GROUP)
            item.setData(0, ROLE_GROUP_ID, row["id"])
            item_map[row["id"]] = item

        for row in rows:
            item = item_map[row["id"]]
            parent_id = row["parent_group_id"]

            if parent_id and parent_id in item_map:
                item_map[parent_id].addChild(item)
            else:
                self.group_tree.addTopLevelItem(item)

        target = all_item

        if selected_kind == FILTER_UNGROUPED:
            target = ungrouped_item
        elif selected_kind == FILTER_UNTAGGED:
            target = untagged_item
        elif (
            selected_kind == FILTER_GROUP
            and selected_group_id in item_map
        ):
            target = item_map[selected_group_id]

        self.group_tree.collapseAll()

        parent = target.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()

        self.group_tree.setCurrentItem(target)
        self.group_tree.blockSignals(False)

    def group_changed(self, current, previous) -> None:
        if current is None:
            self.current_filter_kind = FILTER_ALL
            self.current_group_id = None
        else:
            self.current_filter_kind = (
                current.data(0, ROLE_FILTER_KIND) or FILTER_ALL
            )
            self.current_group_id = current.data(0, ROLE_GROUP_ID)

        self.refresh_images()

    def add_root_group(self) -> None:
        self._prompt_create_group(None)

    def _prompt_create_group(self, parent_group_id: str | None) -> None:
        title = "子グループ作成" if parent_group_id else "グループ作成"

        name, accepted = QInputDialog.getText(
            self,
            title,
            "グループ名",
        )
        if not accepted or not name.strip():
            return

        try:
            new_id = create_image_group(name.strip(), parent_group_id)
        except Exception as exc:
            QMessageBox.warning(self, "グループ作成失敗", str(exc))
            return

        self.current_filter_kind = FILTER_GROUP
        self.current_group_id = new_id
        self.refresh_groups()
        self.refresh_images()

    def show_group_context_menu(self, pos) -> None:
        item = self.group_tree.itemAt(pos)
        if item is None:
            return

        kind = item.data(0, ROLE_FILTER_KIND)
        group_id = item.data(0, ROLE_GROUP_ID)

        menu = QMenu(self)

        if kind != FILTER_GROUP or not group_id:
            action = menu.addAction("グループを追加")
            action.triggered.connect(self.add_root_group)
        else:
            add_child = menu.addAction("子グループを追加")
            rename_action = menu.addAction("名前を変更")
            menu.addSeparator()
            delete_action = menu.addAction("削除")

            add_child.triggered.connect(
                lambda: self._prompt_create_group(group_id)
            )
            rename_action.triggered.connect(
                lambda: self._rename_group_dialog(
                    group_id,
                    item.text(0),
                )
            )
            delete_action.triggered.connect(
                lambda: self._delete_group_dialog(
                    group_id,
                    item.text(0),
                )
            )

        menu.exec(self.group_tree.viewport().mapToGlobal(pos))

    def _rename_group_dialog(
        self,
        group_id: str,
        current_name: str,
    ) -> None:
        name, accepted = QInputDialog.getText(
            self,
            "グループ名変更",
            "グループ名",
            text=current_name,
        )
        if not accepted or not name.strip():
            return

        try:
            rename_image_group(group_id, name.strip())
        except Exception as exc:
            QMessageBox.warning(self, "変更失敗", str(exc))
            return

        self.refresh_groups()

    def _delete_group_dialog(
        self,
        group_id: str,
        name: str,
    ) -> None:
        answer = QMessageBox.question(
            self,
            "グループ削除",
            f"「{name}」を削除しますか？\n\n"
            "配下の子グループも削除されますが、画像自体は削除されません。",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_image_group(group_id)
        except Exception as exc:
            QMessageBox.warning(self, "削除失敗", str(exc))
            return

        if (
            self.current_filter_kind == FILTER_GROUP
            and self.current_group_id == group_id
        ):
            self.current_filter_kind = FILTER_ALL
            self.current_group_id = None

        self.refresh_groups()
        self.refresh_images()

    def import_images(self) -> None:
        paths, _selected_filter = QFileDialog.getOpenFileNames(
            self,
            "画像を追加",
            "",
            (
                "画像ファイル "
                "(*.png *.jpg *.jpeg *.jfif *.webp *.gif *.bmp *.avif);;"
                "すべてのファイル (*.*)"
            ),
        )

        if not paths:
            return

        succeeded = 0
        failures = []

        for path in paths:
            try:
                import_image_asset(path)
                succeeded += 1
            except Exception as exc:
                failures.append(f"{Path(path).name}: {exc}")

        self.refresh_tag_candidates()
        self.refresh_images()

        if failures:
            text = "\n".join(failures[:8])
            if len(failures) > 8:
                text += f"\nほか {len(failures) - 8} 件"

            QMessageBox.warning(
                self,
                "画像追加",
                f"{succeeded}件追加しました。\n\n"
                f"失敗:\n{text}",
            )

    def _selection_mode_changed(self, checked: bool) -> None:
        mode = (
            QAbstractItemView.SelectionMode.ExtendedSelection
            if checked
            else QAbstractItemView.SelectionMode.SingleSelection
        )
        self.image_list.setSelectionMode(mode)
        self.selection_toolbar.setVisible(checked)

        if not checked:
            self.image_list.clearSelection()

        self.update_selection_ui()

    def selected_image_ids(self) -> list[str]:
        output = []
        for item in self.image_list.selectedItems():
            image_id = item.data(ROLE_IMAGE_ID)
            if image_id:
                output.append(str(image_id))
        return output

    def update_selection_ui(self) -> None:
        count = len(self.selected_image_ids())
        self.selection_count_label.setText(f"{count}件選択")

        enabled = count > 0
        self.bulk_tag_button.setEnabled(enabled)
        self.bulk_group_button.setEnabled(enabled)
        self.bulk_delete_button.setEnabled(enabled)

    def select_all_visible(self) -> None:
        if not self.selection_mode.isChecked():
            self.selection_mode.setChecked(True)

        self.image_list.selectAll()
        self.update_selection_ui()

    def clear_selection(self) -> None:
        self.image_list.clearSelection()
        self.update_selection_ui()

    def bulk_add_tags(self) -> None:
        image_ids = self.selected_image_ids()
        if not image_ids:
            return

        text, accepted = QInputDialog.getText(
            self,
            "一括タグ追加",
            "追加するタグ（カンマ区切り）",
        )
        if not accepted:
            return

        names = [
            part.strip()
            for part in text.replace("、", ",").split(",")
            if part.strip()
        ]
        if not names:
            return

        try:
            add_tags_to_images(image_ids, names)
        except Exception as exc:
            QMessageBox.warning(self, "タグ追加失敗", str(exc))
            return

        self.refresh_tag_candidates()
        self.refresh_images()

    def _group_path_options(self) -> list[tuple[str, str]]:
        rows = list_image_groups()
        by_id = {row["id"]: row for row in rows}
        output = []

        for row in rows:
            names = [str(row["name"])]
            parent_id = row["parent_group_id"]
            visited = {row["id"]}

            while parent_id and parent_id in by_id and parent_id not in visited:
                visited.add(parent_id)
                parent = by_id[parent_id]
                names.append(str(parent["name"]))
                parent_id = parent["parent_group_id"]

            output.append((" / ".join(reversed(names)), row["id"]))

        output.sort(key=lambda pair: pair[0].casefold())
        return output

    def bulk_add_group(self) -> None:
        image_ids = self.selected_image_ids()
        if not image_ids:
            return

        options = self._group_path_options()
        if not options:
            QMessageBox.information(
                self,
                "グループ追加",
                "先に画像グループを作成してください。",
            )
            return

        labels = [label for label, _group_id in options]
        label, accepted = QInputDialog.getItem(
            self,
            "一括グループ追加",
            "追加先グループ",
            labels,
            0,
            False,
        )
        if not accepted:
            return

        lookup = dict(options)
        group_id = lookup.get(label)
        if not group_id:
            return

        try:
            add_group_to_images(image_ids, group_id)
        except Exception as exc:
            QMessageBox.warning(self, "グループ追加失敗", str(exc))
            return

        self.refresh_images()

    def delete_selected(self) -> None:
        image_ids = self.selected_image_ids()
        if not image_ids:
            return

        answer = QMessageBox.question(
            self,
            "画像削除",
            f"選択した {len(image_ids)} 件をManagerから削除しますか？\n\n"
            "CCFOLIA側に登録済みの画像は削除しません。",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_image_assets(image_ids)
        except Exception as exc:
            QMessageBox.warning(self, "削除失敗", str(exc))
            return

        self.refresh_images()

    def show_image_context_menu(self, pos) -> None:
        item = self.image_list.itemAt(pos)
        if item is None:
            return

        if not item.isSelected():
            if not self.selection_mode.isChecked():
                self.image_list.clearSelection()
            item.setSelected(True)

        image_ids = self.selected_image_ids()
        if not image_ids:
            return

        menu = QMenu(self)

        if len(image_ids) == 1:
            image_id = image_ids[0]

            rename_action = menu.addAction("名前を変更")
            tags_action = menu.addAction("タグを編集")
            group_action = menu.addAction("グループを追加")
            menu.addSeparator()
            delete_action = menu.addAction("削除")

            rename_action.triggered.connect(
                lambda: self.rename_one(image_id)
            )
            tags_action.triggered.connect(
                lambda: self.edit_one_tags(image_id)
            )
            group_action.triggered.connect(
                lambda: self.add_one_to_group(image_id)
            )
            delete_action.triggered.connect(self.delete_selected)
        else:
            tags_action = menu.addAction(
                f"選択中 {len(image_ids)} 件へタグ追加"
            )
            group_action = menu.addAction(
                f"選択中 {len(image_ids)} 件をグループへ追加"
            )
            menu.addSeparator()
            delete_action = menu.addAction(
                f"選択中 {len(image_ids)} 件を削除"
            )

            tags_action.triggered.connect(self.bulk_add_tags)
            group_action.triggered.connect(self.bulk_add_group)
            delete_action.triggered.connect(self.delete_selected)

        menu.exec(self.image_list.viewport().mapToGlobal(pos))

    def rename_one(self, image_id: str) -> None:
        bundle = get_image_asset_bundle(image_id)
        current_name = str(bundle["asset"]["display_name"] or "")

        name, accepted = QInputDialog.getText(
            self,
            "画像名変更",
            "画像名",
            text=current_name,
        )
        if not accepted or not name.strip():
            return

        try:
            rename_image_asset(image_id, name.strip())
        except Exception as exc:
            QMessageBox.warning(self, "変更失敗", str(exc))
            return

        self.refresh_images()

    def edit_one_tags(self, image_id: str) -> None:
        bundle = get_image_asset_bundle(image_id)
        current = ", ".join(tag["name"] for tag in bundle["tags"])

        text, accepted = QInputDialog.getText(
            self,
            "タグ編集",
            "タグ（カンマ区切り）",
            text=current,
        )
        if not accepted:
            return

        names = [
            part.strip()
            for part in text.replace("、", ",").split(",")
            if part.strip()
        ]

        try:
            set_image_tags(image_id, names)
        except Exception as exc:
            QMessageBox.warning(self, "タグ編集失敗", str(exc))
            return

        self.refresh_tag_candidates()
        self.refresh_images()

    def add_one_to_group(self, image_id: str) -> None:
        if not self.selection_mode.isChecked():
            self.selection_mode.setChecked(True)

        self.image_list.clearSelection()

        for index in range(self.image_list.count()):
            item = self.image_list.item(index)
            if str(item.data(ROLE_IMAGE_ID) or "") == image_id:
                item.setSelected(True)
                break

        self.bulk_add_group()
