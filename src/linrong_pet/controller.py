from __future__ import annotations

import math
import random
from dataclasses import dataclass

from PySide6.QtCore import QObject, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication

from . import autostart
from .animation import AnimationManifest, AnimationPlayer, AtlasRenderer
from .audio import AudioPlayer
from .bubble import SpeechBubble
from .paths import asset_path
from .pet_window import PetWindow
from .settings import ALLOWED_HEIGHTS, PetSettings, SettingsStore


@dataclass(frozen=True, slots=True)
class Interaction:
    state: str
    audio: str
    text: str


INTERACTIONS = (
    Interaction("waving", "hello.wav", "你好呀，我是林榕。"),
    Interaction("jumping", "happy.wav", "见到你真开心。"),
    Interaction("waiting", "found.wav", "呀，你找到我啦。"),
    Interaction("sitting", "poked.wav", "别一直戳我嘛。"),
    Interaction("review", "company.wav", "需要我陪你一会儿吗？"),
    Interaction("running", "rest.wav", "记得让眼睛休息一下哦。"),
    Interaction("heart", "love.wav", "爱你哦"),
)
SITTING_STATE = "sitting"
AMBIENT_STATES = (
    "waving",
    "jumping",
    "waiting",
    "running",
    "review",
    "heart",
)
ROAM_INTERVAL_MS = (30_000, 50_000)
AMBIENT_INTERVAL_MS = (18_000, 32_000)
ROAM_DISTANCE_PX = (160, 420)


class PetController(QObject):
    visibility_changed = Signal(bool)
    roaming_changed = Signal(bool)
    muted_changed = Signal(bool)
    size_changed = Signal(int)
    autostart_changed = Signal(bool)

    def __init__(self, store: SettingsStore | None = None) -> None:
        super().__init__()
        self.store = store or SettingsStore()
        self.settings: PetSettings = self.store.load()
        self.settings.autostart_enabled = autostart.is_enabled()

        self.manifest = AnimationManifest.load(asset_path("animation.json"))
        self.renderer = AtlasRenderer(asset_path("spritesheet.webp"), self.manifest)
        self.window = PetWindow(self.settings.pet_height)
        self.player = AnimationPlayer(
            self.manifest, self.renderer, lambda: self.window.pet_height
        )
        self.audio = AudioPlayer(asset_path("audio"))
        self.audio.muted = self.settings.muted
        self.bubble = SpeechBubble()

        self._interaction_active = False
        self._dragging = False
        self._seated = False
        self._sitting_down = False
        self._standing_up = False
        self._target: QPoint | None = None
        self._speed = 0.0
        self._move_origin = QPoint()
        self._move_progress = 0.0
        self._move_distance = 0.0
        self._last_ambient_state: str | None = None

        self.move_timer = QTimer(self)
        self.move_timer.setTimerType(Qt.PreciseTimer)
        self.move_timer.setInterval(16)
        self.move_timer.timeout.connect(self._move_step)
        self.roam_timer = QTimer(self)
        self.roam_timer.setSingleShot(True)
        self.roam_timer.timeout.connect(self.start_roaming)
        self.ambient_timer = QTimer(self)
        self.ambient_timer.setSingleShot(True)
        self.ambient_timer.timeout.connect(self._start_ambient_action)
        self.resume_timer = QTimer(self)
        self.resume_timer.setSingleShot(True)
        self.resume_timer.timeout.connect(self._resume_autonomous_activity)
        self.hover_timer = QTimer(self)
        self.hover_timer.setSingleShot(True)
        self.hover_timer.timeout.connect(self._hover_reaction)

        self.player.frame_changed.connect(self.window.set_frame)
        self.player.finished.connect(self._animation_finished)
        self.window.clicked.connect(self.interact)
        self.window.drag_started.connect(self._drag_started)
        self.window.drag_finished.connect(self._drag_finished)
        self.window.hover_started.connect(lambda: self.hover_timer.start(800))
        self.window.hover_ended.connect(self.hover_timer.stop)
        self.window.destroyed.connect(self._stop_runtime)

        screen = QGuiApplication.primaryScreen()
        screen.availableGeometryChanged.connect(self._screen_changed)
        screen.geometryChanged.connect(self._screen_changed)

        self.window.setWindowIcon(QGuiApplication.windowIcon())
        self._restore_position()
        self.player.play("idle", repeat=True)
        self.window.show()
        self.window.raise_()
        self.schedule_roaming()
        self.schedule_ambient_action()

    def _restore_position(self) -> None:
        bounds = self.window.available_geometry()
        if self.settings.last_x is None or self.settings.last_y is None:
            requested = QPoint(
                bounds.right() - self.window.width() - 79,
                bounds.bottom() - self.window.height() + 1,
            )
        else:
            requested = QPoint(self.settings.last_x, self.settings.last_y)
        self.window.move(self.window.clamped_position(requested))

    def save(self) -> None:
        self.settings.last_x = self.window.x()
        self.settings.last_y = self.window.y()
        self.store.save(self.settings)

    def _stop_runtime(self) -> None:
        self.move_timer.stop()
        self.roam_timer.stop()
        self.ambient_timer.stop()
        self.resume_timer.stop()
        self.hover_timer.stop()
        self.player.timer.stop()
        self.audio.stop()

    def shutdown(self) -> None:
        self._stop_runtime()
        self.bubble.close()
        self.save()

    def schedule_roaming(self) -> None:
        self.roam_timer.stop()
        if (
            self.settings.roaming_enabled
            and self.window.isVisible()
            and not self._interaction_active
            and not self._dragging
            and not self._seated
            and not self._sitting_down
            and not self._standing_up
        ):
            self.roam_timer.start(random.randint(*ROAM_INTERVAL_MS))

    def schedule_ambient_action(self) -> None:
        self.ambient_timer.stop()
        if (
            self.window.isVisible()
            and not self._interaction_active
            and not self._dragging
            and not self._seated
            and not self._sitting_down
            and not self._standing_up
            and not self.move_timer.isActive()
        ):
            self.ambient_timer.start(random.randint(*AMBIENT_INTERVAL_MS))

    def _resume_autonomous_activity(self) -> None:
        self.schedule_roaming()
        self.schedule_ambient_action()

    def start_roaming(self) -> None:
        if (
            not self.settings.roaming_enabled
            or not self.window.isVisible()
            or self._interaction_active
            or self._dragging
            or self._seated
            or self._sitting_down
            or self._standing_up
        ):
            return
        bounds = self.window.available_geometry()
        min_x = bounds.left()
        max_x = bounds.right() - self.window.width() + 1
        if max_x <= min_x:
            self.schedule_roaming()
            return
        current_x = self.window.x()
        available_span = max_x - min_x
        minimum_distance = min(ROAM_DISTANCE_PX[0], available_span)
        maximum_distance = min(ROAM_DISTANCE_PX[1], available_span)
        offsets = (
            random.randint(-maximum_distance, maximum_distance),
            random.randint(-maximum_distance, maximum_distance),
        )
        candidates = [
            max(min_x, min(max_x, current_x + offset))
            for offset in offsets
            if abs(offset) >= minimum_distance
        ]
        candidates = [
            target_x
            for target_x in candidates
            if abs(target_x - current_x) >= minimum_distance
        ]
        if candidates:
            target_x = candidates[0]
        else:
            left_room = current_x - min_x
            right_room = max_x - current_x
            if right_room >= left_room:
                target_x = current_x + min(maximum_distance, right_room)
            else:
                target_x = current_x - min(maximum_distance, left_room)
        self._target = QPoint(target_x, self.window.floor_y())
        self._speed = random.uniform(45.0, 75.0)
        self._move_origin = self.window.pos()
        self._move_progress = 0.0
        self._move_distance = math.hypot(
            self._target.x() - self._move_origin.x(),
            self._target.y() - self._move_origin.y(),
        )
        self.player.play(
            "walking-right" if target_x >= current_x else "walking-left",
            repeat=True,
        )
        self.ambient_timer.stop()
        self.move_timer.start()

    def _move_step(self) -> None:
        if self._target is None:
            self._stop_roaming()
            return
        if self._move_distance <= 0:
            self.window.move(self.window.clamped_position(self._target))
            self._stop_roaming()
            return
        self._move_progress = min(
            self._move_distance,
            self._move_progress
            + self._speed * self.move_timer.interval() / 1000.0,
        )
        if self._move_progress >= self._move_distance:
            self.window.move(self.window.clamped_position(self._target))
            self._stop_roaming()
            return
        ratio = self._move_progress / self._move_distance
        next_pos = QPoint(
            round(
                self._move_origin.x()
                + (self._target.x() - self._move_origin.x()) * ratio
            ),
            round(
                self._move_origin.y()
                + (self._target.y() - self._move_origin.y()) * ratio
            ),
        )
        self.window.move(self.window.clamped_position(next_pos))

    def _stop_roaming(self) -> None:
        self.move_timer.stop()
        self._target = None
        if not self._interaction_active and not self._seated:
            self.player.play("idle", repeat=True)
        self.save()
        self.schedule_roaming()
        self.schedule_ambient_action()

    def _start_ambient_action(self) -> None:
        if (
            not self.window.isVisible()
            or self._interaction_active
            or self._dragging
            or self._seated
            or self._sitting_down
            or self._standing_up
            or self.move_timer.isActive()
        ):
            self.schedule_ambient_action()
            return
        choices = tuple(
            state
            for state in AMBIENT_STATES
            if state != self._last_ambient_state
        )
        state = random.choice(choices or AMBIENT_STATES)
        self._last_ambient_state = state
        self.roam_timer.stop()
        self._interaction_active = True
        self.player.play(state, repeat=False)

    def interact(self) -> None:
        if self._sitting_down or self._standing_up:
            return
        if self._seated:
            self._stand_up()
            return
        self.move_timer.stop()
        self.roam_timer.stop()
        self.ambient_timer.stop()
        self._target = None
        self._interaction_active = True
        interaction = random.choice(INTERACTIONS)
        self.audio.play(interaction.audio)
        self.bubble.show_message(interaction.text, self.window.geometry())
        if interaction.state == SITTING_STATE:
            self._sitting_down = True
        self.player.play(interaction.state, repeat=False)

    def _stand_up(self) -> None:
        self.move_timer.stop()
        self.roam_timer.stop()
        self.ambient_timer.stop()
        self.resume_timer.stop()
        self._target = None
        self._seated = False
        self._standing_up = True
        self._interaction_active = True
        self.bubble.hide()
        self.audio.stop()
        self.player.play(SITTING_STATE, repeat=False, reverse=True)

    def _hover_reaction(self) -> None:
        if (
            self._interaction_active
            or self._dragging
            or self._seated
            or self._sitting_down
            or self._standing_up
            or self.move_timer.isActive()
        ):
            return
        self.roam_timer.stop()
        self.ambient_timer.stop()
        self._interaction_active = True
        self.player.play("review", repeat=False)

    def _animation_finished(self, state: str) -> None:
        if state == SITTING_STATE and self._sitting_down:
            self.player.timer.stop()
            self._sitting_down = False
            self._seated = True
            self._interaction_active = False
            return
        if state == SITTING_STATE and self._standing_up:
            self._standing_up = False
        self._interaction_active = False
        self.player.play("idle", repeat=True)
        self.schedule_roaming()
        self.schedule_ambient_action()

    def _drag_started(self) -> None:
        self._dragging = True
        self._interaction_active = False
        self._standing_up = False
        self.move_timer.stop()
        self.roam_timer.stop()
        self.ambient_timer.stop()
        self.resume_timer.stop()
        self._target = None
        self.bubble.hide()
        self.audio.stop()
        if self._sitting_down:
            self._sitting_down = False
            self._seated = True
            self.player.play(SITTING_STATE, repeat=False)
            self.player.timer.stop()
            self.player.frame_index = (
                self.manifest.states[SITTING_STATE].frames - 1
            )
            self.player.refresh_frame()
        elif not self._seated:
            self.player.play("idle", repeat=True)

    def _drag_finished(self, _position: QPoint) -> None:
        self._dragging = False
        self.window.clamp_to_primary_screen()
        self.save()
        if not self._seated:
            self.resume_timer.start(2000)

    def _screen_changed(self, _geometry=None) -> None:
        self.window.clamp_to_primary_screen()
        self.save()

    def show_pet(self) -> None:
        self.window.clamp_to_primary_screen()
        self.window.show()
        self.window.raise_()
        self.visibility_changed.emit(True)
        self.schedule_roaming()
        self.schedule_ambient_action()

    def hide_pet(self) -> None:
        self.move_timer.stop()
        self.roam_timer.stop()
        self.ambient_timer.stop()
        self.resume_timer.stop()
        self.bubble.hide()
        self.window.hide()
        self.visibility_changed.emit(False)
        self.save()

    def toggle_visibility(self) -> None:
        if self.window.isVisible():
            self.hide_pet()
        else:
            self.show_pet()

    def set_roaming_enabled(self, enabled: bool) -> None:
        self.settings.roaming_enabled = enabled
        if enabled:
            self.schedule_roaming()
        else:
            self.move_timer.stop()
            self.roam_timer.stop()
            self.resume_timer.stop()
            self._target = None
            if not self._interaction_active and not self._seated:
                self.player.play("idle", repeat=True)
        self.save()
        self.roaming_changed.emit(enabled)

    def set_muted(self, muted: bool) -> None:
        self.settings.muted = muted
        self.audio.muted = muted
        if muted:
            self.audio.stop()
        self.save()
        self.muted_changed.emit(muted)

    def set_pet_height(self, height: int) -> None:
        if height not in ALLOWED_HEIGHTS:
            return
        bottom_right = self.window.geometry().bottomRight()
        self.settings.pet_height = height
        self.window.set_pet_height(height)
        self.renderer.clear_scaled_cache()
        self.player.refresh_frame()
        self.window.move(
            self.window.clamped_position(
                QPoint(
                    bottom_right.x() - self.window.width() + 1,
                    bottom_right.y() - self.window.height() + 1,
                )
            )
        )
        self.save()
        self.size_changed.emit(height)

    def set_autostart_enabled(self, enabled: bool) -> None:
        actual = autostart.set_enabled(enabled)
        self.settings.autostart_enabled = actual
        self.save()
        self.autostart_changed.emit(actual)
