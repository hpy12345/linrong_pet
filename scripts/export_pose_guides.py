from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def _checkerboard(size: tuple[int, int], block: int = 16) -> Image.Image:
    image = Image.new("RGB", size, "#eef1f5")
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle(
                    (x, y, x + block - 1, y + block - 1),
                    fill="#d8dee7",
                )
    return image


def export(
    animation_path: Path,
    spritesheet_path: Path,
    output_dir: Path,
) -> None:
    manifest = json.loads(animation_path.read_text(encoding="utf-8"))
    atlas_data = manifest["atlas"]
    cell_width = int(atlas_data["cell_width"])
    cell_height = int(atlas_data["cell_height"])
    with Image.open(spritesheet_path) as image:
        atlas = image.convert("RGBA")
    output_dir.mkdir(parents=True, exist_ok=True)

    for state_name, state in manifest["states"].items():
        frames = int(state["frames"])
        row = int(state["row"])
        guide = _checkerboard((frames * cell_width, cell_height))
        for index in range(frames):
            frame = atlas.crop(
                (
                    index * cell_width,
                    row * cell_height,
                    (index + 1) * cell_width,
                    (row + 1) * cell_height,
                )
            )
            guide.paste(frame, (index * cell_width, 0), frame)
        guide.save(output_dir / f"{state_name}.png")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--animation", type=Path, required=True)
    parser.add_argument("--spritesheet", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    export(args.animation, args.spritesheet, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
