from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


def test_runtime_frames_match_animation_manifest():
    assets = Path(__file__).parents[1] / "src" / "linrong_pet" / "assets"
    manifest = json.loads(
        (assets / "animation.json").read_text(encoding="utf-8")
    )
    width = manifest["atlas"]["cell_width"]
    height = manifest["atlas"]["cell_height"]
    expected = {
        f"{state_name}-{index:02d}.webp"
        for state_name, state in manifest["states"].items()
        for index in range(state["frames"])
    }
    frame_dir = assets / "frames"
    assert {path.name for path in frame_dir.glob("*.webp")} == expected
    for path in frame_dir.glob("*.webp"):
        with Image.open(path) as frame:
            assert frame.size == (width, height)
            assert frame.convert("RGBA").getchannel("A").getbbox() is not None


def test_walking_runtime_frames_are_all_distinct():
    assets = Path(__file__).parents[1] / "src" / "linrong_pet" / "assets"
    for state in ("walking-right", "walking-left"):
        payloads = {
            (assets / "frames" / f"{state}-{index:02d}.webp").read_bytes()
            for index in range(8)
        }
        assert len(payloads) == 8
