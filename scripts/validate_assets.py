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

    idle_bounds = [
        frame.getchannel("A").getbbox()
        for frame in state_frames["idle"]
    ]
    idle_heights = [
        bounds[3] - bounds[1]
        for bounds in idle_bounds
        if bounds is not None
    ]
    sitting_bounds = [
        frame.getchannel("A").getbbox()
        for frame in state_frames["sitting"]
    ]
    if idle_heights and sitting_bounds[0] is not None:
        idle_height = float(np.median(idle_heights))
        sitting_first_height = sitting_bounds[0][3] - sitting_bounds[0][1]
        if (
            idle_height > cell_height * 0.5
            and abs(sitting_first_height - idle_height) / idle_height > 0.02
        ):
            errors.append("sitting first frame scale does not match idle")

    production_sitting = [
        bounds for bounds in sitting_bounds if bounds is not None
    ]
    if (
        idle_heights
        and float(np.median(idle_heights)) > cell_height * 0.5
        and production_sitting
    ):
        baselines = [bounds[3] for bounds in production_sitting]
        if max(baselines) - min(baselines) > 2:
            errors.append("sitting baseline changes between frames")
        head_widths = [
            _head_width(frame, bounds, round(float(np.median(idle_heights))))
            for frame, bounds in zip(
                state_frames["sitting"],
                sitting_bounds,
                strict=True,
            )
            if bounds is not None
        ]
        if (
            head_widths
            and min(head_widths) > 0
            and max(head_widths) > min(head_widths) * 1.18
        ):
            errors.append("sitting face scale changes excessively")

    idle_hair_widths = [
        _dark_head_width(frame)
        for frame in state_frames["idle"]
    ]
    jumping_hair_widths = [
        _dark_head_width(frame)
        for frame in state_frames["jumping"]
    ]
    if (
        min(idle_hair_widths, default=0) > 0
        and min(jumping_hair_widths, default=0) > 0
    ):
        idle_hair_width = float(np.median(idle_hair_widths))
        jumping_hair_width = float(np.median(jumping_hair_widths))
        if abs(jumping_hair_width - idle_hair_width) / idle_hair_width > 0.15:
            errors.append("jumping face scale does not match idle")
        if max(jumping_hair_widths) > min(jumping_hair_widths) * 1.18:
            errors.append("jumping face scale changes excessively")

    pixels = np.asarray(rgba, dtype=np.uint8)
    alpha = pixels[..., 3]
    cast = suspicious_edge_color(pixels[..., :3]) & (alpha > 0)
    if cast.any():
        errors.append(f"{int(cast.sum())} green/cyan cast pixels remain")
    return errors


def _head_width(
    frame: Image.Image,
    bounds: tuple[int, int, int, int],
    reference_height: int,
) -> int:
    alpha = np.asarray(frame.getchannel("A"), dtype=np.uint8)
    left, top, right, _bottom = bounds
    sample_bottom = min(alpha.shape[0], top + round(reference_height * 0.22))
    region = alpha[top:sample_bottom, left:right] > 16
    columns = np.where(region.any(axis=0))[0]
    if columns.size == 0:
        return 0
    return int(columns[-1] - columns[0] + 1)


def _dark_head_width(frame: Image.Image) -> int:
    bounds = frame.getchannel("A").getbbox()
    if bounds is None:
        return 0
    crop = np.asarray(frame.crop(bounds).convert("RGBA"), dtype=np.uint8)
    sample_height = min(
        crop.shape[0],
        max(1, round(crop.shape[1] * 0.42)),
    )
    sample = crop[:sample_height]
    dark_hair = (
        (sample[..., :3].mean(axis=2) < 90)
        & (sample[..., 3] > 128)
    )
    columns = np.where(dark_hair.any(axis=0))[0]
    if columns.size == 0:
        return 0
    return int(columns[-1] - columns[0] + 1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--animation", type=Path, required=True)
    parser.add_argument("--spritesheet", type=Path, required=True)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    errors = validate(args.animation, args.spritesheet)
    if args.json_out:
        with Image.open(args.spritesheet) as image:
            atlas_size = image.size
        report = {
            "ok": not errors,
            "animation": str(args.animation),
            "spritesheet": str(args.spritesheet),
            "atlas_size": list(atlas_size),
            "errors": errors,
        }
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if errors:
        print("\n".join(errors))
        return 1
    print("asset validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
