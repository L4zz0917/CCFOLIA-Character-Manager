from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.ui.main_window import MainWindow as CharacterMainWindow
from app.ui.bgm_page import BgmPage


class ManagerShellWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("CCFOLIA Manager")
        self.resize(1220, 800)
        self.setMinimumSize(920, 620)

        self._build_ui()
        self.switch_module(0)

    def _build_ui(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        nav = QFrame()
        nav.setObjectName("TopBar")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(16, 10, 16, 10)
        nav_layout.setSpacing(8)

        title = QLabel("CCFOLIA MANAGER")
        title.setObjectName("AppTitle")
        nav_layout.addWidget(title)
        nav_layout.addSpacing(18)

        self.module_group = QButtonGroup(self)
        self.module_group.setExclusive(True)

        self.character_button = self._module_button("キャラクター", 0)
        self.images_button = self._module_button("画像", 1)
        self.bgm_button = self._module_button("BGM", 2)

        nav_layout.addWidget(self.character_button)
        nav_layout.addWidget(self.images_button)
        nav_layout.addWidget(self.bgm_button)
        nav_layout.addStretch(1)

        layout.addWidget(nav)

        self.stack = QStackedWidget()

        self.character_page = CharacterMainWindow()
        self.character_page.setWindowFlags(Qt.WindowType.Widget)
        self.character_page.setMinimumSize(0, 0)

        # IMAGES_PERF_LAZY_INIT
        self.images_page = None
        self.images_placeholder = QWidget()

        # BGM_DESKTOP_SHELL_V1
        self.bgm_page = BgmPage()

        self.stack.addWidget(self.character_page)
        self.stack.addWidget(self.images_placeholder)
        self.stack.addWidget(self.bgm_page)

        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

    def _module_button(self, text: str, index: int) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName("SearchModeButton")
        button.setCheckable(True)
        button.clicked.connect(lambda _checked=False, i=index: self.switch_module(i))
        self.module_group.addButton(button, index)
        return button

    def _ensure_images_page(self) -> None:
        if self.images_page is not None:
            return

        # Build the heavier image module only when it is first opened.
        from app.ui.image_page import ImagesPage

        page = ImagesPage()
        placeholder = self.stack.widget(1)

        self.stack.removeWidget(placeholder)
        placeholder.deleteLater()
        self.stack.insertWidget(1, page)
        self.images_page = page

    def switch_module(self, index: int) -> None:
        index = max(0, min(index, self.stack.count() - 1))

        if index == 1:
            self._ensure_images_page()

        self.stack.setCurrentIndex(index)

        button = self.module_group.button(index)
        if button is not None and not button.isChecked():
            button.setChecked(True)

        if index == 1 and self.images_page is not None:
            self.images_page.activate()


