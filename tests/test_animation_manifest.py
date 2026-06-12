from pathlib import Path

from PySide6.QtGui import QPixmap

import linrong_pet.animation as animation_module
from linrong_pet.animation import (
    AnimationManifest,
    AnimationPlayer,
    AnimationState,
)


def test_production_animation_manifest():
    path = (
        Path(__file__).parents[1]
        / "src"
        / "linrong_pet"
        / "assets"
        / "animation.json"
    )
    manifest = AnimationManifest.load(path)
    assert (manifest.columns, manifest.rows) == (8, 9)
    assert (manifest.cell_width, manifest.cell_height) == (384, 416)
    assert manifest.states["idle"].frames == 6
    assert manifest.states["walking-right"].frames == 8
    assert manifest.states["walking-left"].frames == 8
    assert manifest.states["review"].row == 8
    idle_durations = manifest.states["idle"].durations_ms
    assert 5800 <= sum(idle_durations) <= 6500
    assert idle_durations[0] >= 5000
    assert max(idle_durations[1:]) <= 100


def test_animation_player_can_reverse_to_the_first_frame(qtbot):
    class Renderer:
        def prefetch_state(self, _state: str, _height: int) -> None:
            return

        def frame(self, _state: str, _index: int, _height: int) -> QPixmap:
            return QPixmap(1, 1)

    manifest = AnimationManifest(
        columns=8,
        rows=9,
        cell_width=384,
        cell_height=416,
        states={
            "sitting": AnimationState(
                row=5,
                frames=3,
                durations_ms=(100, 100, 100),
                loop=False,
            )
        },
    )
    player = AnimationPlayer(manifest, Renderer(), lambda: 320)
    finished = []
    player.finished.connect(finished.append)

    player.play("sitting", repeat=False, reverse=True)
    assert player.frame_index == 2
    player._advance()
    assert player.frame_index == 1
    player._advance()
    assert player.frame_index == 0
    player._advance()

    assert finished == ["sitting"]


def test_animation_player_never_skips_frames_after_a_long_delay(
    qtbot, monkeypatch
):
    class Renderer:
        def prefetch_state(self, _state: str, _height: int) -> None:
            return

        def frame(self, _state: str, _index: int, _height: int) -> QPixmap:
            return QPixmap(1, 1)

    manifest = AnimationManifest(
        columns=8,
        rows=9,
        cell_width=384,
        cell_height=416,
        states={
            "walking-right": AnimationState(
                row=1,
                frames=8,
                durations_ms=(95,) * 8,
                loop=True,
            )
        },
    )
    timestamps = iter((0, 1_000_000_000))
    monkeypatch.setattr(
        animation_module.time,
        "monotonic_ns",
        lambda: next(timestamps),
    )
    player = AnimationPlayer(manifest, Renderer(), lambda: 320)

    player.play("walking-right", repeat=True)
    player._advance()

    assert player.frame_index == 1
