from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image
import numpy as np

try:
    from scripts.enhance_spritesheet import suspicious_edge_color
except ModuleNotFoundError:
    from enhance_spritesheet import suspicious_edge_color


EXPECTED = {
    "idle": (0, 6),
    "walking-right": (1, 8),
    "walking-left": (2, 8),
    "waving": (3, 4),
    "jumping": (4, 5),
    "sitting": (5, 8),
    "waiting": (6, 6),
    "running": (7, 6),
    "review": (8, 6),
}


def validate(animation_path: Path, spritesheet_path: Path) -> list[str]:
    errors: list[str] = []
    manifest = json.loads(animation_path.read_text(encoding="utf-8"))
    atlas = manifest.get("atlas", {})
    columns = int(atlas.get("columns", 0))
    rows = int(atlas.get("rows", 0))
    cell_width = int(atlas.get("cell_width", 0))
    cell_height = int(atlas.get("cell_height", 0))
    if (columns, rows) != (8, 9):
        errors.append("animation.json atlas contract is invalid")
    if cell_width < 384 or cell_height < 416:
        errors.append("animation atlas is below the 2x HD cell contract")
    if cell_width * 208 != cell_height * 192:
        errors.append("animation cell aspect ratio is invalid")
    states = manifest.get("states", {})
    for name, (row, frames) in EXPECTED.items():
        value = states.get(name)
        if value is None:
            errors.append(f"missing state: {name}")
            continue
        if value.get("row") != row or value.get("frames") != frames:
            errors.append(f"invalid row/frame metadata for {name}")
        if len(value.get("durations_ms", [])) != frames:
            errors.append(f"invalid durations for {name}")

    try:
        with Image.open(spritesheet_path) as image:
            rgba = image.convert("RGBA")
    except (FileNotFoundError, OSError) as exc:
        errors.append(f"cannot open spritesheet: {exc}")
        return errors
    expected_size = (columns * cell_width, rows * cell_height)
    if rgba.size != expected_size:
        errors.append(
            f"spritesheet size is {rgba.size}, expected "
            f"{expected_size[0]}x{expected_size[1]}"
        )
        return errors

    state_frames: dict[str, list[Image.Image]] = {}
    for name, (row, frames) in EXPECTED.items():
        state_frames[name] = []
        for column in range(frames):
            frame = rgba.crop(
                (
                    column * cell_width,
                    row * cell_height,
                    (column + 1) * cell_width,
                    (row + 1) * cell_height,
                )
            )
            state_frames[name].append(frame)
            alpha = frame.getchannel("A")
            if alpha.getbbox() is None:
                errors.append(f"empty used cell: {name}[{column}]")
        for column in range(frames, 8):
            alpha = rgba.crop(
                (
                    column * cell_width,
                    row * cell_height,
                    (column + 1) * cell_width,
                    (row + 1) * cell_height,
                )
            ).getchannel("A")
            if alpha.getbbox() is not None:
                errors.append(f"non-transparent unused cell: {name}[{column}]")

    for name in ("walking-right", "walking-left"):
        digests = {
            hashlib.sha256(frame.tobytes()).digest()
            for frame in state_frames[name]
        }
        if len(digests) != EXPECTED[name][1]:
            errors.append(f"{name} contains duplicated or missing keyframes")

    sitting_widths = []
    for frame in state_frames["sitting"]:
        bounds = frame.getchannel("A").getbbox()
        if bounds is not None:
            sitting_widths.append(bounds[2] - bounds[0])
    if sitting_widths and max(sitting_widths) > min(sitting_widths) * 1.25:
        errors.append("sitting character scale changes excessively")

    pixels = np.asarray(rgba, dtype=np.uint8)
    alpha = pixels[..., 3]
    cast = suspicious_edge_color(pixels[..., :3]) & (alpha > 0)
    if cast.any():
        errors.append(f"{int(cast.sum())} green/cyan cast pixels remain")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--animation", type=Path, required=True)
    parser.add_argument("--spritesheet", type=Path, required=True)
    args = parser.parse_args()
    errors = validate(args.animation, args.spritesheet)
    if errors:
        print("\n".join(errors))
        return 1
    print("asset validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
