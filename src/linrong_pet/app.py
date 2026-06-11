from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .controller import PetController
from .paths import asset_path
from .single_instance import SingleInstance
from .tray import PetTrayIcon


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("林榕桌宠")
    app.setApplicationDisplayName("林榕桌宠")
    app.setOrganizationName("LinRongPet")
    app.setQuitOnLastWindowClosed(False)

    icon = QIcon(str(asset_path("linrong.ico")))
    app.setWindowIcon(icon)

    instance = SingleInstance()
    if not instance.claim():
        return 0
    if not QSystemTrayIcon.isSystemTrayAvailable():
        return 2

    controller = PetController()
    tray = PetTrayIcon(controller, icon)
    instance.activate_requested.connect(controller.show_pet)
    app.aboutToQuit.connect(controller.shutdown)
    tray.show()

    # Keep Python references alive for the lifetime of the Qt event loop.
    app.instance_guard = instance
    app.pet_controller = controller
    app.pet_tray = tray
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
