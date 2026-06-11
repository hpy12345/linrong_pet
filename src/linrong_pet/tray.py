from __future__ import annotations

from PySide6.QtGui import QAction, QActionGroup, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .controller import PetController
from .settings import ALLOWED_HEIGHTS


class PetTrayIcon(QSystemTrayIcon):
    def __init__(self, controller: PetController, icon: QIcon) -> None:
        super().__init__(icon)
        self.controller = controller
        self.setToolTip("林榕桌宠")

        menu = QMenu()
        self.visibility_action = menu.addAction("隐藏林榕")
        self.visibility_action.triggered.connect(controller.toggle_visibility)

        self.roaming_action = menu.addAction("启用自动漫游")
        self.roaming_action.setCheckable(True)
        self.roaming_action.setChecked(controller.settings.roaming_enabled)
        self.roaming_action.toggled.connect(controller.set_roaming_enabled)

        size_menu = menu.addMenu("角色大小")
        self.size_actions: dict[int, QAction] = {}
        size_group = QActionGroup(self)
        size_group.setExclusive(True)
        labels = {240: "小（240 px）", 320: "标准（320 px）", 400: "大（400 px）"}
        for height in ALLOWED_HEIGHTS:
            action = size_menu.addAction(labels[height])
            action.setCheckable(True)
            action.setChecked(height == controller.settings.pet_height)
            action.triggered.connect(
                lambda checked=False, value=height: controller.set_pet_height(value)
            )
            size_group.addAction(action)
            self.size_actions[height] = action

        self.mute_action = menu.addAction("静音")
        self.mute_action.setCheckable(True)
        self.mute_action.setChecked(controller.settings.muted)
        self.mute_action.toggled.connect(controller.set_muted)

        self.autostart_action = menu.addAction("开机启动")
        self.autostart_action.setCheckable(True)
        self.autostart_action.setChecked(controller.settings.autostart_enabled)
        self.autostart_action.toggled.connect(controller.set_autostart_enabled)

        menu.addSeparator()
        exit_action = menu.addAction("退出")
        exit_action.triggered.connect(self._exit)
        self.setContextMenu(menu)

        self.activated.connect(self._activated)
        controller.visibility_changed.connect(self._visibility_changed)
        controller.roaming_changed.connect(self._sync_roaming)
        controller.muted_changed.connect(self._sync_muted)
        controller.size_changed.connect(self._sync_size)
        controller.autostart_changed.connect(self._sync_autostart)

    def _activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.Trigger:
            self.controller.toggle_visibility()

    def _visibility_changed(self, visible: bool) -> None:
        self.visibility_action.setText("隐藏林榕" if visible else "显示林榕")

    def _sync_roaming(self, enabled: bool) -> None:
        self.roaming_action.blockSignals(True)
        self.roaming_action.setChecked(enabled)
        self.roaming_action.blockSignals(False)

    def _sync_muted(self, muted: bool) -> None:
        self.mute_action.blockSignals(True)
        self.mute_action.setChecked(muted)
        self.mute_action.blockSignals(False)

    def _sync_size(self, height: int) -> None:
        self.size_actions[height].setChecked(True)

    def _sync_autostart(self, enabled: bool) -> None:
        self.autostart_action.blockSignals(True)
        self.autostart_action.setChecked(enabled)
        self.autostart_action.blockSignals(False)

    def _exit(self) -> None:
        self.controller.save()
        QApplication.quit()

