from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
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
from app.services.character_lifecycle_service import (
    duplicate_character,
    soft_delete_character,
)
from app.services.cocofolia_service import (
    default_export_path,
    export_characters_to_zip,
    import_room_zip,
)
from app.services.character_service import (
    create_character,
    create_group,
    delete_group,
    list_characters,
    list_groups,
    list_tags,
    rename_group,
)
from app.ui.character_dialogs import (
    CharacterEditorDialog,
    CharacterViewDialog,
)
from app.ui.tag_chip_editor import TagChipEditor
from app.ui.trash_dialog import TrashDialog


from app.ui.backup_dialog import BackupDialog

from app.services.settings_service import apply_ui_font_size
from app.ui.settings_dialog import SettingsDialog
from app.services.cocofolia_send_service import queue_characters_for_cocofolia

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        apply_ui_font_size()

        self.setWindowTitle("CCFOLIA Character Manager")
        self.resize(1180, 760)
        self.setMinimumSize(900, 600)

        self.current_group_id = None

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self.refresh_characters)

        self._build_ui()
        self.refresh_groups()
        self.refresh_characters()

    def _build_ui(self):
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        top_bar = QFrame()
        top_bar.setObjectName("TopBar")

        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(16, 12, 16, 12)
        top_layout.setSpacing(8)

        title = QLabel("CHARACTER LIBRARY")
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

        self.search_mode_group.addButton(
            self.keyword_mode_button
        )
        self.search_mode_group.addButton(
            self.tag_mode_button
        )

        self.search_mode_switch = QFrame()
        self.search_mode_switch.setObjectName("SearchModeSwitch")

        search_mode_layout = QHBoxLayout(
            self.search_mode_switch
        )
        search_mode_layout.setContentsMargins(0, 0, 0, 0)
        search_mode_layout.setSpacing(0)
        search_mode_layout.addWidget(
            self.keyword_mode_button
        )
        search_mode_layout.addWidget(
            self.tag_mode_button
        )

        self.keyword_mode_button.clicked.connect(
            self._search_mode_changed
        )
        self.tag_mode_button.clicked.connect(
            self._search_mode_changed
        )

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("キャラクターを検索...")
        self.search_box.setClearButtonEnabled(True)
        self.search_box.textChanged.connect(
            lambda: self.search_timer.start()
        )

        self.tag_search = TagChipEditor()
        self.tag_search.set_placeholder(
            "タグを入力して検索..."
        )
        self.tag_search.setVisible(False)
        self.tag_search.tagsChanged.connect(
            self.refresh_characters
        )

        self.selection_mode = QPushButton("選択")
        self.selection_mode.setObjectName("SelectionModeButton")
        self.selection_mode.setCheckable(True)
        self.selection_mode.setToolTip("複数キャラクターを選択します")
        self.selection_mode.toggled.connect(self.refresh_characters)
        self.selection_mode.toggled.connect(self.selection_mode_changed)

        self.settings_button = QPushButton("設定")
        self.settings_button.setObjectName("SecondaryButton")
        self.settings_button.clicked.connect(
            self.open_settings
        )

        self.backup_button = QPushButton("バックアップ")
        self.backup_button.setObjectName("SecondaryButton")
        self.backup_button.clicked.connect(
            self.open_backup
        )

        self.trash_button = QPushButton("ゴミ箱")
        self.trash_button.setObjectName("SecondaryButton")
        self.trash_button.clicked.connect(
            self.open_trash
        )

        self.import_button = QPushButton("ZIPインポート")
        self.import_button.setObjectName("SecondaryButton")
        self.import_button.clicked.connect(
            self.import_cocofolia_zip
        )

        self.add_button = QPushButton("＋ キャラクター")
        self.add_button.setObjectName("PrimaryButton")
        self.add_button.clicked.connect(self.add_character)

        self.manage_button = QPushButton("管理")
        self.manage_button.setObjectName("ManageButton")
        self.manage_button.setToolTip("設定・バックアップ・ゴミ箱・ZIPインポート")

        manage_menu = QMenu(self.manage_button)

        if hasattr(self, "import_button"):
            action = manage_menu.addAction("ZIPをインポート")
            action.triggered.connect(self.import_cocofolia_zip)
            self.import_button.setVisible(False)

        if hasattr(self, "backup_button"):
            action = manage_menu.addAction("バックアップ / 復元")
            action.triggered.connect(self.open_backup)
            self.backup_button.setVisible(False)

        if hasattr(self, "trash_button"):
            action = manage_menu.addAction("ゴミ箱")
            action.triggered.connect(self.open_trash)
            self.trash_button.setVisible(False)

        if hasattr(self, "settings_button"):
            manage_menu.addSeparator()
            action = manage_menu.addAction("設定")
            action.triggered.connect(self.open_settings)
            self.settings_button.setVisible(False)

        self.manage_button.setMenu(manage_menu)

        if hasattr(self, "send_cocofolia_button"):
            self.send_cocofolia_button.setObjectName("SendButton")
            self.send_cocofolia_button.setToolTip(
                "現在のキャラクター、または選択中のキャラクターをココフォリアへ送ります"
            )

        self.add_button.setToolTip("新しいキャラクターを作成します")

        top_layout.addWidget(self.search_mode_switch)
        top_layout.addWidget(self.search_box, 1)
        top_layout.addWidget(self.tag_search, 1)
        top_layout.addWidget(self.selection_mode)
        top_layout.addWidget(self.settings_button)
        top_layout.addWidget(self.backup_button)
        top_layout.addWidget(self.trash_button)
        if not hasattr(self, "send_cocofolia_button"):
            self.send_cocofolia_button = QPushButton(
                "ココフォリアへ送る"
            )
            self.send_cocofolia_button.setObjectName(
                "PrimaryButton"
            )
            self.send_cocofolia_button.clicked.connect(
                self.send_to_cocofolia
            )

        top_layout.addWidget(self.send_cocofolia_button)
        top_layout.addWidget(self.import_button)
        top_layout.addWidget(self.manage_button)
        top_layout.addWidget(self.add_button)

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
        self.add_group_button.clicked.connect(
            self.add_root_group
        )

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

        self.result_label = QLabel("キャラクター")
        self.result_label.setObjectName("SectionTitle")

        self.send_cocofolia_button = QPushButton("ココフォリアへ送る")
        self.send_cocofolia_button.setObjectName("PrimaryButton")
        self.send_cocofolia_button.clicked.connect(
            self.send_to_cocofolia
        )

        self.export_button = QPushButton(
            "選択したキャラクターをエクスポート"
        )
        self.export_button.setObjectName("SecondaryButton")
        self.export_button.setVisible(False)
        self.export_button.clicked.connect(self.export_selected)

        header_layout.addWidget(self.result_label)
        header_layout.addStretch(1)
        header_layout.addWidget(self.export_button)

        self.selection_toolbar = QFrame()
        self.selection_toolbar.setObjectName("SelectionToolbar")
        self.selection_toolbar.setVisible(False)

        selection_toolbar_layout = QHBoxLayout(self.selection_toolbar)
        selection_toolbar_layout.setContentsMargins(12, 8, 12, 8)
        selection_toolbar_layout.setSpacing(8)

        self.selection_count_label = QLabel("0件選択")
        self.selection_count_label.setObjectName("SelectionCount")

        self.selection_hint_label = QLabel("行をクリックして選択")
        self.selection_hint_label.setObjectName("SelectionHint")

        self.select_all_button = QPushButton("すべて選択")
        self.select_all_button.setObjectName("SelectionUtilityButton")
        self.select_all_button.clicked.connect(self.select_all_visible)

        self.clear_selection_button = QPushButton("選択解除")
        self.clear_selection_button.setObjectName("SelectionUtilityButton")
        self.clear_selection_button.clicked.connect(self.clear_selection_visible)

        self.selection_export_button = QPushButton("ZIP書き出し")
        self.selection_export_button.setObjectName("SelectionSecondaryAction")
        self.selection_export_button.setEnabled(False)
        self.selection_export_button.clicked.connect(self.export_selected)

        self.selection_send_button = QPushButton("ココフォリアへ送る")
        self.selection_send_button.setObjectName("SelectionPrimaryAction")
        self.selection_send_button.setEnabled(False)
        self.selection_send_button.clicked.connect(self.send_to_cocofolia)

        selection_toolbar_layout.addWidget(self.selection_count_label)
        selection_toolbar_layout.addWidget(self.selection_hint_label)
        selection_toolbar_layout.addStretch(1)
        selection_toolbar_layout.addWidget(self.select_all_button)
        selection_toolbar_layout.addWidget(self.clear_selection_button)
        selection_toolbar_layout.addSpacing(8)
        selection_toolbar_layout.addWidget(self.selection_export_button)
        selection_toolbar_layout.addWidget(self.selection_send_button)

        self.character_list = QListWidget()
        self.character_list.setObjectName("CharacterList")
        self.character_list.setIconSize(QSize(40, 40))
        self.character_list.setSpacing(2)
        self.character_list.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.character_list.itemChanged.connect(
            self.update_export_button
        )
        self.character_list.itemDoubleClicked.connect(
            self.character_double_clicked
        )
        self.character_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.character_list.customContextMenuRequested.connect(
            self.show_character_context_menu
        )

        self.character_list.itemPressed.connect(self._remember_item_press)
        self.character_list.itemClicked.connect(self._selection_row_clicked)
        self.character_list.setUniformItemSizes(True)

        content_layout.addLayout(header_layout)
        content_layout.addWidget(self.selection_toolbar)
        content_layout.addWidget(self.character_list, 1)

        splitter.addWidget(sidebar)
        splitter.addWidget(content)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 940])

        root_layout.addWidget(splitter, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage("準備完了")

    def _current_search_mode(self):
        if self.tag_mode_button.isChecked():
            return "tag"
        return "keyword"

    def _search_mode_changed(self, *args):
        tag_mode = (
            self._current_search_mode()
            == "tag"
        )

        self.search_box.setVisible(
            not tag_mode
        )
        self.tag_search.setVisible(
            tag_mode
        )

        if tag_mode:
            self.tag_search.set_available_tags(
                [
                    row["name"]
                    for row in list_tags()
                ]
            )
            self.tag_search.focus_input()
        else:
            self.search_box.setPlaceholderText(
                "キャラクターを検索..."
            )
            self.search_box.setFocus()

        self.refresh_characters()

    def refresh_groups(self):
        selected_id = self.current_group_id

        self.group_tree.blockSignals(True)
        self.group_tree.clear()

        all_item = QTreeWidgetItem(["すべて"])
        all_item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            None,
        )
        self.group_tree.addTopLevelItem(all_item)

        rows = list_groups()
        item_map = {}

        for row in rows:
            item = QTreeWidgetItem([row["name"]])
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                row["id"],
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

        target = all_item
        if selected_id is not None:
            target = item_map.get(selected_id, all_item)

        self.group_tree.setCurrentItem(target)
        self.group_tree.blockSignals(False)

    def refresh_characters(self):
        self.character_list.blockSignals(True)
        self.character_list.clear()

        search_mode = self._current_search_mode()

        if search_mode == "tag":
            search_text = ", ".join(
                self.tag_search.tags()
            )
        else:
            search_text = self.search_box.text()

        rows = list_characters(
            search_text=search_text,
            search_mode=search_mode,
            group_id=self.current_group_id,
        )

        selection_enabled = self.selection_mode.isChecked()

        for row in rows:
            item = QListWidgetItem(row["name"])
            item.setData(
                Qt.ItemDataRole.UserRole,
                row["id"],
            )
            item.setData(
                Qt.ItemDataRole.UserRole + 1,
                row["cocofolia_export_id"],
            )

            image_path = row["main_image"]
            if image_path:
                path = PROJECT_ROOT / image_path
                if path.exists():
                    item.setIcon(QIcon(str(path)))

            if selection_enabled:
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                item.setCheckState(
                    Qt.CheckState.Unchecked
                )

            self.character_list.addItem(item)

        self.character_list.blockSignals(False)
        self.result_label.setText(
            f"キャラクター  {len(rows)}"
        )
        self.update_export_button()

    def group_changed(self, current, previous):
        if current is None:
            self.current_group_id = None
        else:
            self.current_group_id = current.data(
                0,
                Qt.ItemDataRole.UserRole,
            )
        self.refresh_characters()

    def add_root_group(self):
        self._prompt_create_group(None)

    def _prompt_create_group(self, parent_group_id):
        title = (
            "子グループ作成"
            if parent_group_id
            else "グループ作成"
        )
        name, accepted = QInputDialog.getText(
            self,
            title,
            "グループ名",
        )
        if not accepted:
            return

        name = name.strip()
        if not name:
            return

        try:
            new_id = create_group(
                name,
                parent_group_id,
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "グループ作成失敗",
                str(exc),
            )
            return

        self.current_group_id = new_id
        self.refresh_groups()
        self.refresh_characters()

    def show_group_context_menu(self, pos):
        item = self.group_tree.itemAt(pos)
        if item is None:
            return

        group_id = item.data(
            0,
            Qt.ItemDataRole.UserRole,
        )

        menu = QMenu(self)

        if group_id is None:
            add_root = QAction("グループを追加", self)
            add_root.triggered.connect(
                self.add_root_group
            )
            menu.addAction(add_root)
        else:
            add_child = QAction("子グループを追加", self)
            rename_action = QAction("名前を変更", self)
            delete_action = QAction("削除", self)

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
                    item.childCount(),
                )
            )

            menu.addAction(add_child)
            menu.addSeparator()
            menu.addAction(rename_action)
            menu.addAction(delete_action)

        menu.exec(
            self.group_tree.viewport().mapToGlobal(pos)
        )

    def _rename_group_dialog(
        self,
        group_id: str,
        current_name: str,
    ):
        name, accepted = QInputDialog.getText(
            self,
            "グループ名変更",
            "グループ名",
            text=current_name,
        )
        if not accepted:
            return

        try:
            rename_group(group_id, name)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "変更失敗",
                str(exc),
            )
            return

        self.refresh_groups()

    def _delete_group_dialog(
        self,
        group_id: str,
        name: str,
        child_count: int,
    ):
        extra = ""
        if child_count:
            extra = (
                "\n\nこのグループ配下の子グループも"
                "まとめて削除されます。"
            )

        answer = QMessageBox.question(
            self,
            "グループ削除",
            f"「{name}」を削除しますか？"
            f"{extra}\n\n"
            "キャラクター自体は削除されません。",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            delete_group(group_id)
        except Exception as exc:
            QMessageBox.warning(
                self,
                "削除失敗",
                str(exc),
            )
            return

        if self.current_group_id == group_id:
            self.current_group_id = None

        self.refresh_groups()
        self.refresh_characters()

    def show_character_context_menu(self, pos):
        item = self.character_list.itemAt(
            pos
        )

        if item is None:
            return

        self.character_list.setCurrentItem(
            item
        )

        character_id = item.data(
            Qt.ItemDataRole.UserRole
        )

        menu = QMenu(self)

        duplicate_action = QAction(
            "複製",
            self,
        )
        trash_action = QAction(
            "ゴミ箱へ移動",
            self,
        )

        duplicate_action.triggered.connect(
            lambda: self.duplicate_character_item(
                character_id
            )
        )
        trash_action.triggered.connect(
            lambda: self.trash_character_item(
                character_id,
                item.text(),
            )
        )

        menu.addAction(
            duplicate_action
        )
        menu.addSeparator()
        menu.addAction(
            trash_action
        )

        menu.exec(
            self.character_list
            .viewport()
            .mapToGlobal(pos)
        )

    def duplicate_character_item(
        self,
        character_id,
    ):
        try:
            new_id = duplicate_character(
                character_id
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "複製失敗",
                str(exc),
            )
            return

        self.refresh_characters()

        self.statusBar().showMessage(
            "キャラクターを複製しました",
            4000,
        )

        dialog = CharacterViewDialog(
            new_id,
            self,
        )
        dialog.changed.connect(
            self.refresh_characters
        )
        dialog.exec()

        self.refresh_characters()

    def trash_character_item(
        self,
        character_id,
        name,
    ):
        answer = QMessageBox.question(
            self,
            "ゴミ箱へ移動",
            f"「{name}」をゴミ箱へ移動しますか？\n\n"
            "あとで復元できます。",
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
            soft_delete_character(
                character_id
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "削除失敗",
                str(exc),
            )
            return

        self.refresh_characters()

        self.statusBar().showMessage(
            "キャラクターをゴミ箱へ移動しました",
            4000,
        )

    def open_settings(self):
        dialog = SettingsDialog(
            self
        )
        dialog.exec()

    def open_backup(self):
        dialog = BackupDialog(
            self
        )
        dialog.exec()

    def open_trash(self):
        dialog = TrashDialog(
            self
        )
        dialog.changed.connect(
            self.refresh_characters
        )
        dialog.exec()

        self.refresh_characters()

    def selection_mode_changed(self, checked):
        self.selection_toolbar.setVisible(checked)
        self.selection_mode.setText("選択中" if checked else "選択")
        self.export_button.setVisible(False)
        self.update_selection_ui()

    def _remember_item_press(self, item):
        if not self.selection_mode.isChecked():
            self._pressed_item_id = None
            self._pressed_check_state = None
            return

        self._pressed_item_id = item.data(Qt.ItemDataRole.UserRole)
        self._pressed_check_state = item.checkState()

    def _selection_row_clicked(self, item):
        if not self.selection_mode.isChecked():
            return

        item_id = item.data(Qt.ItemDataRole.UserRole)
        current_state = item.checkState()

        if (
            item_id == getattr(self, "_pressed_item_id", None)
            and current_state == getattr(self, "_pressed_check_state", None)
        ):
            item.setCheckState(
                Qt.CheckState.Checked
                if current_state != Qt.CheckState.Checked
                else Qt.CheckState.Unchecked
            )

        self.update_selection_ui()

    def select_all_visible(self):
        if not self.selection_mode.isChecked():
            return

        self.character_list.blockSignals(True)

        try:
            for index in range(self.character_list.count()):
                self.character_list.item(index).setCheckState(Qt.CheckState.Checked)
        finally:
            self.character_list.blockSignals(False)

        self.update_selection_ui()

    def clear_selection_visible(self):
        if not self.selection_mode.isChecked():
            return

        self.character_list.blockSignals(True)

        try:
            for index in range(self.character_list.count()):
                self.character_list.item(index).setCheckState(Qt.CheckState.Unchecked)
        finally:
            self.character_list.blockSignals(False)

        self.update_selection_ui()

    def update_selection_ui(self):
        enabled = self.selection_mode.isChecked()
        count = 0

        if enabled:
            for index in range(self.character_list.count()):
                if (
                    self.character_list.item(index).checkState()
                    == Qt.CheckState.Checked
                ):
                    count += 1

        if hasattr(self, "selection_count_label"):
            self.selection_count_label.setText(f"{count}件選択")

        if hasattr(self, "selection_send_button"):
            self.selection_send_button.setEnabled(count > 0)

        if hasattr(self, "selection_export_button"):
            self.selection_export_button.setEnabled(count > 0)

        if hasattr(self, "selection_hint_label"):
            self.selection_hint_label.setVisible(count == 0)

        self.export_button.setVisible(False)

    def add_character(self):
        name, accepted = QInputDialog.getText(
            self,
            "キャラクター作成",
            "まず名前を入力してください。\n"
            "作成後、そのまま編集画面を開きます。",
        )
        if not accepted:
            return

        name = name.strip()
        if not name:
            return

        try:
            character_id = create_character(name)
        except Exception as exc:
            QMessageBox.critical(
                self,
                "作成失敗",
                str(exc),
            )
            return

        editor = CharacterEditorDialog(
            character_id,
            self,
        )
        editor.saved.connect(self.refresh_characters)
        editor.exec()

        self.refresh_characters()
        self.statusBar().showMessage(
            f"「{name}」を作成しました",
            4000,
        )

    def update_export_button(self):
        self.update_selection_ui()

    def send_to_cocofolia(self):
        character_ids = []

        for index in range(self.character_list.count()):
            item = self.character_list.item(index)

            try:
                checked = (
                    item.checkState()
                    == Qt.CheckState.Checked
                )
            except Exception:
                checked = False

            if checked:
                character_id = item.data(
                    Qt.ItemDataRole.UserRole
                )

                if character_id:
                    character_ids.append(character_id)

        if not character_ids:
            current = self.character_list.currentItem()

            if current is not None:
                character_id = current.data(
                    Qt.ItemDataRole.UserRole
                )

                if character_id:
                    character_ids.append(character_id)

        if not character_ids:
            QMessageBox.information(
                self,
                "ココフォリアへ送る",
                "送信するキャラクターを選択してください。",
            )
            return

        try:
            result = queue_characters_for_cocofolia(
                character_ids
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "ココフォリア連携失敗",
                str(exc),
            )
            return

        self.statusBar().showMessage(
            f"ココフォリアへ送信待機: {result['characters']}件"
            "（アクティブなルームへ自動投入します）",
            10000,
        )

    def export_selected(self):
        character_ids = []

        for index in range(self.character_list.count()):
            item = self.character_list.item(index)

            if item.checkState() == Qt.CheckState.Checked:
                character_ids.append(
                    item.data(Qt.ItemDataRole.UserRole)
                )

        if not character_ids:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "ココフォリアZIPを書き出す",
            str(default_export_path()),
            "ZIPファイル (*.zip)",
        )

        if not path:
            return

        try:
            result = export_characters_to_zip(
                character_ids,
                path,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "エクスポート失敗",
                str(exc),
            )
            return

        QMessageBox.information(
            self,
            "エクスポート完了",
            f"{result['characters']}件を書き出しました。\n\n"
            f"{result['path']}",
        )

        self.statusBar().showMessage(
            "ココフォリアZIPを書き出しました",
            5000,
        )

    def import_cocofolia_zip(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "ココフォリアのルームZIPを選択",
            "",
            "ZIPファイル (*.zip)",
        )

        if not path:
            return

        template_label, accepted = QInputDialog.getItem(
            self,
            "インポート設定",
            "不足項目に適用するテンプレート",
            [
                "汎用（追加なし）",
                "CoC6",
            ],
            0,
            False,
        )

        if not accepted:
            return

        template = (
            "coc6"
            if template_label == "CoC6"
            else "generic"
        )

        answer = QMessageBox.question(
            self,
            "ZIPインポート",
            "同じCCFOLIAキャラクターIDが既にある場合は、"
            "ZIP側の基本情報・ステータス・パラメータ・画像・"
            "commandsで更新します。\n\n"
            "続行しますか？",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            imported = import_room_zip(
                path,
                template=template,
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "インポート失敗",
                str(exc),
            )
            return

        self.refresh_characters()

        created = sum(
            1
            for item in imported
            if item["created"]
        )
        updated = len(imported) - created

        QMessageBox.information(
            self,
            "インポート完了",
            f"{len(imported)}件を取り込みました。\n"
            f"新規: {created}件\n"
            f"更新: {updated}件",
        )

        self.statusBar().showMessage(
            "ココフォリアZIPをインポートしました",
            5000,
        )
    def character_double_clicked(self, item):
        if self.selection_mode.isChecked():
            return

        character_id = item.data(Qt.ItemDataRole.UserRole)

        dialog = CharacterViewDialog(
            character_id,
            self,
        )
        dialog.changed.connect(self.refresh_characters)
        dialog.exec()

        self.refresh_characters()

# ---------------------------------------------------------------------------
# Phase 25: bulk tags / groups in selection mode
# ---------------------------------------------------------------------------

from app.services.character_service import (
    add_group_to_characters as add_group_to_characters_v25,
    add_tags_to_characters as add_tags_to_characters_v25,
)


class Phase25MainWindow(MainWindow):
    def _build_ui(self):
        super()._build_ui()

        self.selection_tag_button = QPushButton(
            "タグ追加"
        )
        self.selection_tag_button.setObjectName(
            "SelectionSecondaryAction"
        )
        self.selection_tag_button.setEnabled(False)
        self.selection_tag_button.setToolTip(
            "選択中のキャラクターすべてにタグを追加します。"
            "既存タグは保持されます。"
        )
        self.selection_tag_button.clicked.connect(
            self.bulk_add_tags_v25
        )

        self.selection_group_button = QPushButton(
            "グループ追加"
        )
        self.selection_group_button.setObjectName(
            "SelectionSecondaryAction"
        )
        self.selection_group_button.setEnabled(False)
        self.selection_group_button.setToolTip(
            "選択中のキャラクターすべてをグループへ追加します。"
            "既存所属は保持されます。"
        )
        self.selection_group_button.clicked.connect(
            self.bulk_add_group_v25
        )

        layout = self.selection_toolbar.layout()

        if layout is not None:
            insert_at = max(
                0,
                layout.count() - 2,
            )
            layout.insertWidget(
                insert_at,
                self.selection_tag_button,
            )
            layout.insertWidget(
                insert_at + 1,
                self.selection_group_button,
            )

        self.update_selection_ui()

    def _selected_character_ids_v25(self):
        ids = []

        for index in range(
            self.character_list.count()
        ):
            item = self.character_list.item(index)

            if (
                item.checkState()
                != Qt.CheckState.Checked
            ):
                continue

            character_id = item.data(
                Qt.ItemDataRole.UserRole
            )

            if character_id:
                ids.append(
                    str(character_id)
                )

        return ids

    def update_selection_ui(self):
        super().update_selection_ui()

        count = len(
            self._selected_character_ids_v25()
        )

        if hasattr(
            self,
            "selection_tag_button",
        ):
            self.selection_tag_button.setEnabled(
                count > 0
            )

        if hasattr(
            self,
            "selection_group_button",
        ):
            self.selection_group_button.setEnabled(
                count > 0
            )

    def bulk_add_tags_v25(self):
        character_ids = (
            self._selected_character_ids_v25()
        )

        if not character_ids:
            return

        text, accepted = QInputDialog.getText(
            self,
            "一括タグ追加",
            (
                f"{len(character_ids)}件のキャラクターへ"
                "タグを追加します。\n"
                "複数指定する場合はカンマ区切りで入力してください。"
            ),
        )

        if not accepted:
            return

        raw = str(
            text or ""
        )
        raw = raw.replace(
            "、",
            ",",
        )
        raw = raw.replace(
            "\n",
            ",",
        )
        raw = raw.replace(
            "\t",
            ",",
        )

        tag_names = [
            value.strip()
            for value in raw.split(",")
            if value.strip()
        ]

        if not tag_names:
            return

        try:
            added = add_tags_to_characters_v25(
                character_ids,
                tag_names,
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "一括タグ追加",
                str(exc),
            )
            return

        self.refresh_characters()

        self.statusBar().showMessage(
            (
                f"{len(character_ids)}件へタグを追加しました"
                f"（新規関連付け {added}件）"
            ),
            5000,
        )

    def _group_paths_v25(self):
        rows = list(
            list_groups()
        )

        by_id = {
            str(row["id"]): row
            for row in rows
        }

        cache = {}

        def path_for(
            group_id,
            seen=None,
        ):
            group_id = str(
                group_id
            )

            if group_id in cache:
                return cache[group_id]

            row = by_id.get(
                group_id
            )

            if row is None:
                return group_id

            if seen is None:
                seen = set()

            if group_id in seen:
                return str(
                    row["name"]
                )

            next_seen = set(seen)
            next_seen.add(group_id)

            parent_id = row[
                "parent_group_id"
            ]

            if parent_id:
                parent_path = path_for(
                    str(parent_id),
                    next_seen,
                )
                value = (
                    f"{parent_path} / {row['name']}"
                )
            else:
                value = str(
                    row["name"]
                )

            cache[group_id] = value
            return value

        output = []

        for row in rows:
            group_id = str(
                row["id"]
            )
            output.append(
                (
                    path_for(group_id),
                    group_id,
                )
            )

        output.sort(
            key=lambda value: value[0].casefold()
        )
        return output

    def bulk_add_group_v25(self):
        character_ids = (
            self._selected_character_ids_v25()
        )

        if not character_ids:
            return

        groups = self._group_paths_v25()

        if not groups:
            QMessageBox.information(
                self,
                "一括グループ追加",
                "グループがまだありません。",
            )
            return

        names = [
            path
            for path, _ in groups
        ]

        selected, accepted = QInputDialog.getItem(
            self,
            "一括グループ追加",
            (
                f"{len(character_ids)}件のキャラクターを"
                "追加するグループ:"
            ),
            names,
            0,
            False,
        )

        if not accepted:
            return

        try:
            index = names.index(
                selected
            )
        except ValueError:
            return

        group_id = groups[
            index
        ][1]

        try:
            added = add_group_to_characters_v25(
                character_ids,
                group_id,
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "一括グループ追加",
                str(exc),
            )
            return

        self.refresh_characters()

        self.statusBar().showMessage(
            (
                f"{len(character_ids)}件を"
                f"「{selected}」へ追加しました"
                f"（新規関連付け {added}件）"
            ),
            5000,
        )


MainWindow = Phase25MainWindow

# ---------------------------------------------------------------------------
# Phase 25.1: add "未分類" group filter
# ---------------------------------------------------------------------------

from app.services.character_service import (
    list_ungrouped_characters as list_ungrouped_characters_v251,
)


class Phase251MainWindow(MainWindow):
    UNGROUPED_GROUP_ID = "__ungrouped__"

    def refresh_groups(self):
        selected_id = self.current_group_id

        self.group_tree.blockSignals(True)
        self.group_tree.clear()

        all_item = QTreeWidgetItem(["すべて"])
        all_item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            None,
        )
        self.group_tree.addTopLevelItem(all_item)

        ungrouped_item = QTreeWidgetItem(["未分類"])
        ungrouped_item.setData(
            0,
            Qt.ItemDataRole.UserRole,
            self.UNGROUPED_GROUP_ID,
        )
        self.group_tree.addTopLevelItem(
            ungrouped_item
        )

        rows = list_groups()
        item_map = {}

        for row in rows:
            item = QTreeWidgetItem([row["name"]])
            item.setData(
                0,
                Qt.ItemDataRole.UserRole,
                row["id"],
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

        if selected_id is None:
            target = all_item
        elif selected_id == self.UNGROUPED_GROUP_ID:
            target = ungrouped_item
        else:
            target = item_map.get(
                selected_id,
                all_item,
            )

        self.group_tree.setCurrentItem(target)
        self.group_tree.blockSignals(False)

    def refresh_characters(self):
        self.character_list.blockSignals(True)
        self.character_list.clear()

        search_mode = self._current_search_mode()

        if search_mode == "tag":
            search_text = ", ".join(
                self.tag_search.tags()
            )
        else:
            search_text = self.search_box.text()

        if self.current_group_id == self.UNGROUPED_GROUP_ID:
            rows = list_ungrouped_characters_v251(
                search_text=search_text,
                search_mode=search_mode,
            )
        else:
            rows = list_characters(
                search_text=search_text,
                search_mode=search_mode,
                group_id=self.current_group_id,
            )

        selection_enabled = self.selection_mode.isChecked()

        for row in rows:
            item = QListWidgetItem(row["name"])
            item.setData(
                Qt.ItemDataRole.UserRole,
                row["id"],
            )
            item.setData(
                Qt.ItemDataRole.UserRole + 1,
                row["cocofolia_export_id"],
            )

            image_path = row["main_image"]
            if image_path:
                path = PROJECT_ROOT / image_path
                if path.exists():
                    item.setIcon(QIcon(str(path)))

            if selection_enabled:
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                item.setCheckState(
                    Qt.CheckState.Unchecked
                )

            self.character_list.addItem(item)

        self.character_list.blockSignals(False)
        self.result_label.setText(
            f"キャラクター  {len(rows)}"
        )
        self.update_export_button()
        self.update_selection_ui()

    def group_changed(self, current, previous):
        if current is None:
            self.current_group_id = None
        else:
            self.current_group_id = current.data(
                0,
                Qt.ItemDataRole.UserRole,
            )
        self.refresh_characters()


MainWindow = Phase251MainWindow

# ---------------------------------------------------------------------------
# Phase 27.1: group drag/drop + bulk delete
# ---------------------------------------------------------------------------

from PySide6.QtCore import QEvent

from app.services.character_service import (
    persist_group_tree_structure
    as persist_group_tree_structure_v271,
)
from app.services.character_lifecycle_service import (
    soft_delete_characters
    as soft_delete_characters_v271,
)


class Phase271MainWindow(MainWindow):
    def _build_ui(self):
        super()._build_ui()

        self.selection_delete_button = QPushButton(
            "選択を削除"
        )
        self.selection_delete_button.setObjectName(
            "DangerButton"
        )
        self.selection_delete_button.setEnabled(
            False
        )
        self.selection_delete_button.setToolTip(
            "選択中のキャラクターをまとめてゴミ箱へ移動します。"
        )
        self.selection_delete_button.clicked.connect(
            self.bulk_delete_selected_v271
        )

        toolbar_layout = (
            self.selection_toolbar.layout()
        )

        insert_index = toolbar_layout.count()

        if hasattr(
            self,
            "selection_export_button",
        ):
            found = toolbar_layout.indexOf(
                self.selection_export_button
            )
            if found >= 0:
                insert_index = found

        toolbar_layout.insertWidget(
            insert_index,
            self.selection_delete_button,
        )

        self._configure_group_drag_v271()

    def refresh_groups(self):
        super().refresh_groups()

        if hasattr(
            self,
            "group_tree",
        ):
            self._configure_group_items_v271()

    def _configure_group_drag_v271(self):
        tree = self.group_tree

        tree.setDragEnabled(
            True
        )
        tree.setAcceptDrops(
            True
        )
        tree.setDropIndicatorShown(
            True
        )
        tree.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove
        )
        tree.setDefaultDropAction(
            Qt.DropAction.MoveAction
        )

        viewport = tree.viewport()

        if not getattr(
            self,
            "_group_drop_filter_installed_v271",
            False,
        ):
            viewport.installEventFilter(
                self
            )
            self._group_drop_filter_installed_v271 = True

        self._configure_group_items_v271()

    def _configure_group_items_v271(self):
        if not hasattr(
            self,
            "group_tree",
        ):
            return

        real_ids = {
            row["id"]
            for row in list_groups()
        }

        def walk(item):
            group_id = item.data(
                0,
                Qt.ItemDataRole.UserRole,
            )

            flags = item.flags()

            if group_id in real_ids:
                flags |= (
                    Qt.ItemFlag.ItemIsDragEnabled
                )
                flags |= (
                    Qt.ItemFlag.ItemIsDropEnabled
                )
            else:
                flags &= ~(
                    Qt.ItemFlag.ItemIsDragEnabled
                )
                flags &= ~(
                    Qt.ItemFlag.ItemIsDropEnabled
                )

            item.setFlags(
                flags
            )

            for index in range(
                item.childCount()
            ):
                walk(
                    item.child(index)
                )

        root = self.group_tree.invisibleRootItem()

        for index in range(
            root.childCount()
        ):
            walk(
                root.child(index)
            )

    def eventFilter(
        self,
        watched,
        event,
    ):
        if (
            hasattr(
                self,
                "group_tree",
            )
            and watched
            is self.group_tree.viewport()
            and event.type()
            == QEvent.Type.Drop
        ):
            # InternalMove changes the QTreeWidget after the event
            # returns, so persist on the next event-loop turn.
            QTimer.singleShot(
                0,
                self._persist_group_tree_v271,
            )

        return super().eventFilter(
            watched,
            event,
        )

    def _persist_group_tree_v271(self):
        real_ids = {
            row["id"]
            for row in list_groups()
        }

        rows = []

        def collect(
            parent_item,
            parent_group_id,
        ):
            sibling_order = 0

            for index in range(
                parent_item.childCount()
            ):
                item = parent_item.child(
                    index
                )
                group_id = item.data(
                    0,
                    Qt.ItemDataRole.UserRole,
                )

                if group_id not in real_ids:
                    continue

                rows.append(
                    (
                        group_id,
                        parent_group_id,
                        sibling_order,
                    )
                )

                sibling_order += 1

                collect(
                    item,
                    group_id,
                )

        collect(
            self.group_tree.invisibleRootItem(),
            None,
        )

        try:
            persist_group_tree_structure_v271(
                rows
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "グループ移動失敗",
                str(exc),
            )
            self.refresh_groups()
            return

        self.refresh_groups()

        self.statusBar().showMessage(
            "グループの配置を更新しました",
            2500,
        )

    def _checked_character_ids_v271(self):
        character_ids = []

        for index in range(
            self.character_list.count()
        ):
            item = self.character_list.item(
                index
            )

            if (
                item.checkState()
                != Qt.CheckState.Checked
            ):
                continue

            character_id = item.data(
                Qt.ItemDataRole.UserRole
            )

            if character_id:
                character_ids.append(
                    character_id
                )

        return character_ids

    def update_selection_ui(self):
        super().update_selection_ui()

        if hasattr(
            self,
            "selection_delete_button",
        ):
            count = len(
                self._checked_character_ids_v271()
            )
            self.selection_delete_button.setEnabled(
                count > 0
            )

    def bulk_delete_selected_v271(self):
        character_ids = (
            self._checked_character_ids_v271()
        )

        if not character_ids:
            return

        names = []

        for index in range(
            self.character_list.count()
        ):
            item = self.character_list.item(
                index
            )

            if (
                item.checkState()
                == Qt.CheckState.Checked
            ):
                names.append(
                    item.text()
                )

        preview = "\n".join(
            f"・{name}"
            for name in names[:8]
        )

        if len(names) > 8:
            preview += (
                f"\n・ほか {len(names) - 8} 件"
            )

        answer = QMessageBox.question(
            self,
            "選択キャラクターを削除",
            (
                f"{len(character_ids)}件のキャラクターを"
                "ゴミ箱へ移動しますか？\n\n"
                f"{preview}\n\n"
                "あとでゴミ箱から復元できます。"
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
                soft_delete_characters_v271(
                    character_ids
                )
            )
        except Exception as exc:
            QMessageBox.warning(
                self,
                "一括削除失敗",
                str(exc),
            )
            return

        self.refresh_characters()

        self.statusBar().showMessage(
            f"{deleted_count}件をゴミ箱へ移動しました",
            4000,
        )


MainWindow = Phase271MainWindow

# PHASE37_MAIN_FILTER_AND_GROUP_COLLAPSE
from app.services.character_service import (
    list_characters as list_characters_v37,
    list_ungrouped_characters as list_ungrouped_characters_v37,
)


class Phase37MainWindow(
    MainWindow
):
    def _build_ui(self):
        super()._build_ui()

        self.tagless_filter_button = QPushButton(
            "タグ無し"
        )
        self.tagless_filter_button.setCheckable(
            True
        )
        self.tagless_filter_button.setObjectName(
            "SearchModeButton"
        )
        self.tagless_filter_button.setToolTip(
            "タグが1つも付いていないキャラクターだけを表示します。"
        )
        self.tagless_filter_button.setVisible(
            False
        )

        parent = self.tag_search.parentWidget()
        layout = (
            parent.layout()
            if parent is not None
            else None
        )

        if layout is not None:
            index = layout.indexOf(
                self.tag_search
            )

            layout.insertWidget(
                index + 1,
                self.tagless_filter_button,
            )

        self.tagless_filter_button.toggled.connect(
            self._phase37_tagless_toggled
        )

        self.tag_search.tagsChanged.connect(
            self._phase37_normal_tag_used
        )

    def _phase37_tagless_toggled(
        self,
        checked: bool,
    ):
        if checked:
            blocked = self.tag_search.blockSignals(
                True
            )

            try:
                self.tag_search.set_tags(
                    []
                )
            finally:
                self.tag_search.blockSignals(
                    blocked
                )

        self.refresh_characters()

    def _phase37_normal_tag_used(self):
        if (
            self.tagless_filter_button.isChecked()
            and self.tag_search.tags()
        ):
            blocked = (
                self.tagless_filter_button.blockSignals(
                    True
                )
            )

            try:
                self.tagless_filter_button.setChecked(
                    False
                )
            finally:
                self.tagless_filter_button.blockSignals(
                    blocked
                )

    def _search_mode_changed(self):
        super()._search_mode_changed()

        tag_mode = (
            self._current_search_mode()
            == "tag"
        )

        self.tagless_filter_button.setVisible(
            tag_mode
        )

        if not tag_mode:
            self.tagless_filter_button.setChecked(
                False
            )

    def refresh_characters(self):
        self.character_list.blockSignals(
            True
        )
        self.character_list.clear()

        search_mode = self._current_search_mode()

        if search_mode == "tag":
            if self.tagless_filter_button.isChecked():
                search_text = "__CCM_TAGLESS__"
            else:
                search_text = ", ".join(
                    self.tag_search.tags()
                )
        else:
            search_text = self.search_box.text()

        if (
            self.current_group_id
            == self.UNGROUPED_GROUP_ID
        ):
            rows = list_ungrouped_characters_v37(
                search_text=search_text,
                search_mode=search_mode,
            )
        else:
            rows = list_characters_v37(
                search_text=search_text,
                search_mode=search_mode,
                group_id=self.current_group_id,
            )

        selection_enabled = (
            self.selection_mode.isChecked()
        )

        for row in rows:
            item = QListWidgetItem(
                row["name"]
            )
            item.setData(
                Qt.ItemDataRole.UserRole,
                row["id"],
            )
            item.setData(
                Qt.ItemDataRole.UserRole + 1,
                row["cocofolia_export_id"],
            )

            image_path = row["main_image"]

            if image_path:
                path = PROJECT_ROOT / image_path

                if path.exists():
                    item.setIcon(
                        QIcon(
                            str(path)
                        )
                    )

            if selection_enabled:
                item.setFlags(
                    item.flags()
                    | Qt.ItemFlag.ItemIsUserCheckable
                )
                item.setCheckState(
                    Qt.CheckState.Unchecked
                )

            self.character_list.addItem(
                item
            )

        self.character_list.blockSignals(
            False
        )
        self.result_label.setText(
            f"キャラクター  {len(rows)}"
        )
        self.update_export_button()
        self.update_selection_ui()

    def refresh_groups(self):
        super().refresh_groups()

        if not hasattr(
            self,
            "group_tree",
        ):
            return

        current = self.group_tree.currentItem()

        self.group_tree.collapseAll()

        parent = (
            current.parent()
            if current is not None
            else None
        )

        while parent is not None:
            parent.setExpanded(
                True
            )
            parent = parent.parent()


MainWindow = Phase37MainWindow
