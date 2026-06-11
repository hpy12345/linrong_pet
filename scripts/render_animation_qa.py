from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def checkerboard(size: tuple[int, int], block: int = 16) -> Image.Image:
    image = Image.new("RGB", size, "#e9edf2")
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle(
                    (x, y, x + block - 1, y + block - 1),
                    fill="#cfd6df",
                )
    return image


def render(
    animation_path: Path,
    spritesheet_path: Path,
    output_dir: Path,
) -> None:
    manifest = json.loads(animation_path.read_text(encoding="utf-8"))
    atlas_data = manifest["atlas"]
    cell_width = int(atlas_data["cell_width"])
    cell_height = int(atlas_data["cell_height"])
    output_dir.mkdir(parents=True, exist_ok=True)

    with Image.open(spritesheet_path) as image:
        atlas = image.convert("RGBA")
    for state_name, state in manifest["states"].items():
        row = int(state["row"])
        durations = [int(value) for value in state["durations_ms"]]
        frames: list[Image.Image] = []
        for index in range(int(state["frames"])):
            sprite = atlas.crop(
                (
                    index * cell_width,
                    row * cell_height,
                    (index + 1) * cell_width,
                    (row + 1) * cell_height,
                )
            )
            frame = checkerboard((cell_width, cell_height))
            frame.paste(sprite, (0, 0), sprite)
            frames.append(frame)
        frames[0].save(
            output_dir / f"{state_name}.gif",
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            loop=0,
            disposal=2,
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--animation", type=Path, required=True)
    parser.add_argument("--spritesheet", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    render(args.animation, args.spritesheet, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
