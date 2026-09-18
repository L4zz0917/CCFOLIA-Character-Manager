import sys

from PySide6.QtCore import QEvent, QObject, QSettings
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QMenu,
    QMessageBox,
    QStyle,
    QSystemTrayIcon,
)

from app.db.database import initialize_database
from app.paths import STYLE_PATH, ensure_app_directories
from app.services.bridge_service import get_bridge_server
from app.ui.manager_shell import ManagerShellWindow



# CCFOLIA_MANAGER_CLOSE_TO_TRAY_V2
class _CloseAwareWindowFilter(QObject):
    def __init__(self, controller):
        super().__init__(controller)
        self._controller = controller

    def eventFilter(self, watched, event):
        if (
            watched is self._controller.window
            and event.type() == QEvent.Type.Close
        ):
            return self._controller.handle_close_event(event)

        return super().eventFilter(watched, event)


class _TrayController(QObject):
    SETTINGS_KEY = "close_button_auto_minimize"

    def __init__(self, app: QApplication, window):
        super().__init__(app)
        self.app = app
        self.window = window
        self._allow_real_close = False
        self.settings = QSettings("Local", "CCFOLIA Manager")

        self.tray = QSystemTrayIcon(self)

        icon = window.windowIcon()
        if icon.isNull():
            icon = app.style().standardIcon(
                QStyle.StandardPixmap.SP_ComputerIcon
            )

        self.tray.setIcon(icon)
        self.tray.setToolTip("CCFOLIA Manager")

        self.menu = QMenu()

        show_action = QAction("CCFOLIA Managerを表示", self.menu)
        reset_action = QAction("×ボタンの確認を再表示", self.menu)
        quit_action = QAction("終了", self.menu)

        show_action.triggered.connect(self.restore)
        reset_action.triggered.connect(self.reset_close_preference)
        quit_action.triggered.connect(self.quit)

        self.menu.addAction(show_action)
        self.menu.addSeparator()
        self.menu.addAction(reset_action)
        self.menu.addSeparator()
        self.menu.addAction(quit_action)

        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self._on_activated)

        self._close_filter = _CloseAwareWindowFilter(self)
        window.installEventFilter(self._close_filter)

        self.tray.show()

    def auto_minimize_enabled(self) -> bool:
        return self.settings.value(
            self.SETTINGS_KEY,
            False,
            type=bool,
        )

    def set_auto_minimize(self, enabled: bool) -> None:
        self.settings.setValue(self.SETTINGS_KEY, bool(enabled))
        self.settings.sync()

    def handle_close_event(self, event) -> bool:
        if self._allow_real_close:
            return False

        if self.auto_minimize_enabled():
            event.ignore()
            self.hide_to_tray(show_notice=False)
            return True

        box = QMessageBox(self.window)
        box.setWindowTitle("CCFOLIA Manager")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText("終了しますか？")
        box.setInformativeText(
            "「いいえ」を選ぶと、CCFOLIA Managerは"
            "タスクトレイで動作を続けます。"
        )

        yes_button = box.addButton(
            "はい",
            QMessageBox.ButtonRole.YesRole,
        )
        no_button = box.addButton(
            "いいえ",
            QMessageBox.ButtonRole.NoRole,
        )
        box.setDefaultButton(no_button)

        remember = QCheckBox("次回から自動で最小化")
        box.setCheckBox(remember)

        box.exec()

        if box.clickedButton() is yes_button:
            self._allow_real_close = True
            return False

        if remember.isChecked():
            self.set_auto_minimize(True)

        event.ignore()
        self.hide_to_tray(show_notice=True)
        return True

    def hide_to_tray(self, show_notice: bool = False) -> None:
        self.window.hide()

        if show_notice:
            self.tray.showMessage(
                "CCFOLIA Manager",
                "バックグラウンドで動作中です。"
                " トレイアイコンをクリックすると戻せます。",
                QSystemTrayIcon.MessageIcon.Information,
                2500,
            )

    def restore(self) -> None:
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def reset_close_preference(self) -> None:
        self.set_auto_minimize(False)
        self.tray.showMessage(
            "CCFOLIA Manager",
            "次回から×ボタン押下時に終了確認を表示します。",
            QSystemTrayIcon.MessageIcon.Information,
            2000,
        )

    def quit(self) -> None:
        self._allow_real_close = True
        self.tray.hide()
        self.window.close()
        self.app.quit()

    def _on_activated(self, reason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.restore()


def main() -> int:
    ensure_app_directories()
    initialize_database()

    bridge = get_bridge_server()
    bridge.start()

    app = QApplication(sys.argv)

    # CCFOLIA_MANAGER_QFONT_NORMALIZE
    _ccm_base_font = app.font()
    if _ccm_base_font.pointSize() <= 0:
        _ccm_base_font.setPointSize(10)
        app.setFont(_ccm_base_font)

    # PHASE32_VALID_QT_FONT
    base_font = app.font()
    if base_font.pointSize() <= 0:
        base_font.setPointSize(10)
        app.setFont(base_font)
    app.setApplicationName("CCFOLIA Manager")
    app.setOrganizationName("Local")
    app.aboutToQuit.connect(bridge.stop)

    if STYLE_PATH.exists():
        app.setStyleSheet(STYLE_PATH.read_text(encoding="utf-8"))

    window = ManagerShellWindow()
    window.show()

    tray_controller = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray_controller = _TrayController(app, window)

    # Keep the controller alive for the lifetime of QApplication.
    app._ccfolia_manager_tray_controller = tray_controller

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
