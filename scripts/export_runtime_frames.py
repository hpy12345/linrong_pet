from __future__ import annotations

import argparse
import filecmp
import json
import os
import time
from pathlib import Path

from PIL import Image


def frame_filename(state_name: str, index: int) -> str:
    return f"{state_name}-{index:02d}.webp"


def _save_frame(frame: Image.Image, destination: Path) -> None:
    temporary = destination.with_name(f".{destination.name}.tmp")
    try:
        frame.save(
            temporary,
            format="WEBP",
            lossless=True,
            method=6,
        )
        if destination.exists() and filecmp.cmp(
            temporary,
            destination,
            shallow=False,
        ):
            return
        for attempt in range(5):
            try:
                os.replace(temporary, destination)
                return
            except OSError:
                if attempt == 4:
                    raise
                time.sleep(0.05 * (attempt + 1))
    finally:
        temporary.unlink(missing_ok=True)


def export_frames(
    animation_path: Path,
    spritesheet_path: Path,
    output_dir: Path,
) -> None:
    manifest = json.loads(animation_path.read_text(encoding="utf-8"))
    atlas = manifest["atlas"]
    cell_width = int(atlas["cell_width"])
    cell_height = int(atlas["cell_height"])
    expected: set[str] = set()
    output_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(spritesheet_path) as source_image:
        source = source_image.convert("RGBA")
        for state_name, state in manifest["states"].items():
            row = int(state["row"])
            for index in range(int(state["frames"])):
                filename = frame_filename(state_name, index)
                expected.add(filename)
                frame = source.crop(
                    (
                        index * cell_width,
                        row * cell_height,
                        (index + 1) * cell_width,
                        (row + 1) * cell_height,
                    )
                )
                _save_frame(frame, output_dir / filename)

    for path in output_dir.glob("*.webp"):
        if path.name not in expected:
            path.unlink()
    print(f"exported {len(expected)} runtime frames")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--animation", type=Path, required=True)
    parser.add_argument("--spritesheet", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    export_frames(args.animation, args.spritesheet, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
