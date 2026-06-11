from __future__ import annotations

import json
import time
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QPixmap


@dataclass(frozen=True, slots=True)
class AnimationState:
    row: int
    frames: int
    durations_ms: tuple[int, ...]
    loop: bool


@dataclass(frozen=True, slots=True)
class AnimationManifest:
    columns: int
    rows: int
    cell_width: int
    cell_height: int
    states: dict[str, AnimationState]

    @classmethod
    def load(cls, path: Path) -> "AnimationManifest":
        raw = json.loads(path.read_text(encoding="utf-8"))
        atlas = raw["atlas"]
        states: dict[str, AnimationState] = {}
        for name, value in raw["states"].items():
            frames = int(value["frames"])
            durations = tuple(int(item) for item in value["durations_ms"])
            if len(durations) != frames or any(item <= 0 for item in durations):
                raise ValueError(f"invalid frame durations for {name}")
            states[name] = AnimationState(
                row=int(value["row"]),
                frames=frames,
                durations_ms=durations,
                loop=bool(value["loop"]),
            )
        manifest = cls(
            columns=int(atlas["columns"]),
            rows=int(atlas["rows"]),
            cell_width=int(atlas["cell_width"]),
            cell_height=int(atlas["cell_height"]),
            states=states,
        )
        manifest.validate()
        return manifest

    def validate(self) -> None:
        if (self.columns, self.rows) != (8, 9):
            raise ValueError("animation atlas contract must use 8x9 cells")
        if self.cell_width < 192 or self.cell_height < 208:
            raise ValueError("animation cells must be at least 192x208")
        if self.cell_width * 208 != self.cell_height * 192:
            raise ValueError("animation cells must preserve the 12:13 aspect ratio")
        for name, state in self.states.items():
            if not 0 <= state.row < self.rows:
                raise ValueError(f"row out of range for {name}")
            if not 1 <= state.frames <= self.columns:
                raise ValueError(f"frame count out of range for {name}")


class AtlasRenderer:
    MAX_CACHED_FRAMES = 24

    def __init__(self, atlas_path: Path, manifest: AnimationManifest) -> None:
        self.manifest = manifest
        self.frame_dir = atlas_path.parent / "frames"
        self.atlas: QPixmap | None = None
        expected = QSize(
            manifest.columns * manifest.cell_width,
            manifest.rows * manifest.cell_height,
        )
        first_frame = self.frame_dir / "idle-00.webp"
        if not first_frame.exists():
            self.atlas = QPixmap(str(atlas_path))
            if self.atlas.isNull() or self.atlas.size() != expected:
                raise ValueError(
                    f"invalid atlas: expected {expected.width()}x{expected.height()}"
                )
        self._cache: OrderedDict[tuple[str, int, int], QPixmap] = OrderedDict()

    def frame(self, state_name: str, index: int, height: int) -> QPixmap:
        key = (state_name, index, height)
        cached = self._cache.get(key)
        if cached is not None:
            self._cache.move_to_end(key)
            return cached
        state = self.manifest.states[state_name]
        if self.atlas is None:
            source_frame = QPixmap(
                str(self.frame_dir / f"{state_name}-{index:02d}.webp")
            )
            expected = QSize(
                self.manifest.cell_width,
                self.manifest.cell_height,
            )
            if source_frame.isNull() or source_frame.size() != expected:
                raise ValueError(
                    f"invalid runtime frame: {state_name}[{index}]"
                )
        else:
            source = QRect(
                index * self.manifest.cell_width,
                state.row * self.manifest.cell_height,
                self.manifest.cell_width,
                self.manifest.cell_height,
            )
            source_frame = self.atlas.copy(source)
        frame = source_frame.scaledToHeight(
            height,
            mode=Qt.SmoothTransformation,
        )
        self._cache[key] = frame
        self._cache.move_to_end(key)
        while len(self._cache) > self.MAX_CACHED_FRAMES:
            self._cache.popitem(last=False)
        return frame

    def prefetch_state(self, state_name: str, height: int) -> None:
        state = self.manifest.states[state_name]
        for index in range(state.frames):
            self.frame(state_name, index, height)

    def clear_scaled_cache(self) -> None:
        self._cache.clear()


class AnimationPlayer(QObject):
    frame_changed = Signal(QPixmap)
    state_changed = Signal(str)
    finished = Signal(str)

    def __init__(
        self,
        manifest: AnimationManifest,
        renderer: AtlasRenderer,
        height_provider: Callable[[], int],
    ) -> None:
        super().__init__()
        self.manifest = manifest
        self.renderer = renderer
        self.height_provider = height_provider
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self._advance)
        self.state_name = "idle"
        self.frame_index = 0
        self.repeat = True
        self.direction = 1
        self._deadline_ns: int | None = None

    def play(
        self,
        state_name: str,
        repeat: bool | None = None,
        reverse: bool = False,
    ) -> None:
        if state_name not in self.manifest.states:
            raise KeyError(state_name)
        state = self.manifest.states[state_name]
        self.timer.stop()
        self.renderer.prefetch_state(state_name, self.height_provider())
        self.state_name = state_name
        self.direction = -1 if reverse else 1
        self.frame_index = state.frames - 1 if reverse else 0
        self.repeat = state.loop if repeat is None else repeat
        self._deadline_ns = None
        self.state_changed.emit(state_name)
        self._emit_frame()

    def refresh_frame(self) -> None:
        self._emit_frame(schedule=False)

    def _emit_frame(self, schedule: bool = True) -> None:
        state = self.manifest.states[self.state_name]
        self.frame_changed.emit(
            self.renderer.frame(
                self.state_name, self.frame_index, self.height_provider()
            )
        )
        if schedule:
            duration_ms = state.durations_ms[self.frame_index]
            now = time.monotonic_ns()
            self._deadline_ns = now + duration_ms * 1_000_000
            self.timer.start(duration_ms)

    def _advance(self) -> None:
        state = self.manifest.states[self.state_name]
        now = time.monotonic_ns()
        next_index = self.frame_index + self.direction
        if not 0 <= next_index < state.frames:
            if not self.repeat:
                self._deadline_ns = None
                self.finished.emit(self.state_name)
                return
            next_index = 0 if self.direction > 0 else state.frames - 1

        self.frame_index = next_index
        self.frame_changed.emit(
            self.renderer.frame(
                self.state_name, self.frame_index, self.height_provider()
            )
        )
        duration_ms = state.durations_ms[self.frame_index]
        deadline = now + duration_ms * 1_000_000
        self._deadline_ns = deadline
        self.timer.start(duration_ms)
