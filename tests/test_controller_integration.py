from __future__ import annotations

from PySide6.QtCore import QPoint
from PySide6.QtGui import QIcon

import linrong_pet.controller as controller_module
from linrong_pet.controller import INTERACTIONS, PetController
from linrong_pet.settings import PetSettings, SettingsStore
from linrong_pet.tray import PetTrayIcon


def make_controller(tmp_path, monkeypatch, request) -> PetController:
    monkeypatch.setattr(controller_module.autostart, "is_enabled", lambda: False)
    store = SettingsStore(tmp_path / "settings.json")
    store.save(PetSettings(roaming_enabled=False))
    controller = PetController(store)
    controller.roam_timer.stop()
    controller.resume_timer.stop()
    controller.move_timer.stop()
    request.addfinalizer(controller.shutdown)
    return controller


def test_click_interaction_plays_animation_audio_and_bubble(
    qtbot, tmp_path, monkeypatch, request
):
    controller = make_controller(tmp_path, monkeypatch, request)
    qtbot.addWidget(controller.window)
    interaction = INTERACTIONS[0]
    played = []
    messages = []
    monkeypatch.setattr(controller_module.random, "choice", lambda _: interaction)
    monkeypatch.setattr(controller.audio, "play", played.append)
    monkeypatch.setattr(
        controller.bubble,
        "show_message",
        lambda text, anchor: messages.append((text, anchor)),
    )

    controller.window.clicked.emit()

    assert controller.player.state_name == "waving"
    assert controller._interaction_active
    assert played == ["hello.wav"]
    assert messages[0][0] == "你好呀，我是林榕。"

    controller._animation_finished("waving")
    assert controller.player.state_name == "idle"
    assert not controller._interaction_active


def test_roaming_moves_on_primary_screen_floor(
    qtbot, tmp_path, monkeypatch, request
):
    controller = make_controller(tmp_path, monkeypatch, request)
    qtbot.addWidget(controller.window)
    controller.settings.roaming_enabled = True
    bounds = controller.window.available_geometry()
    start_x = min(
        bounds.right() - controller.window.width() + 1,
        bounds.left() + 400,
    )
    controller.window.move(QPoint(start_x, controller.window.floor_y()))
    monkeypatch.setattr(
        controller_module.random,
        "randint",
        lambda left, right: left,
    )
    monkeypatch.setattr(controller_module.random, "uniform", lambda *_: 60.0)

    controller.start_roaming()
    assert controller.player.state_name == "walking-left"
    assert controller._target == QPoint(bounds.left(), controller.window.floor_y())

    before = controller.window.pos()
    controller._move_step()
    after = controller.window.pos()
    assert after.x() < before.x()
    assert after.y() == controller.window.floor_y()
    assert after == controller.window.clamped_position(after)


def test_sitting_holds_until_next_click(
    qtbot, tmp_path, monkeypatch, request
):
    controller = make_controller(tmp_path, monkeypatch, request)
    qtbot.addWidget(controller.window)
    sitting = next(
        interaction
        for interaction in INTERACTIONS
        if interaction.state == controller_module.SITTING_STATE
    )
    monkeypatch.setattr(controller_module.random, "choice", lambda _: sitting)
    monkeypatch.setattr(controller.audio, "play", lambda _: None)
    monkeypatch.setattr(controller.bubble, "show_message", lambda *_: None)

    controller.interact()
    assert controller._sitting_down
    controller._animation_finished(controller_module.SITTING_STATE)

    assert controller._seated
    assert controller.player.state_name == controller_module.SITTING_STATE
    assert not controller.player.timer.isActive()

    controller.interact()
    assert controller._standing_up
    assert controller.player.direction == -1
    controller._animation_finished(controller_module.SITTING_STATE)

    assert not controller._seated
    assert not controller._standing_up
    assert controller.player.state_name == "idle"


def test_tray_actions_toggle_visibility_roaming_mute_and_size(
    qtbot, tmp_path, monkeypatch, request
):
    controller = make_controller(tmp_path, monkeypatch, request)
    qtbot.addWidget(controller.window)
    tray = PetTrayIcon(controller, QIcon())

    assert controller.window.isVisible()
    tray.visibility_action.trigger()
    assert not controller.window.isVisible()
    tray.visibility_action.trigger()
    assert controller.window.isVisible()

    tray.roaming_action.setChecked(True)
    assert controller.settings.roaming_enabled
    tray.mute_action.setChecked(True)
    assert controller.settings.muted
    tray.size_actions[240].trigger()
    assert controller.window.pet_height == 240
