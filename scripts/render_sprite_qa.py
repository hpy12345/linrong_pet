from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw


def checkerboard(size: tuple[int, int], block: int = 12) -> Image.Image:
    image = Image.new("RGB", size, "#e9edf2")
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], block):
        for x in range(0, size[0], block):
            if (x // block + y // block) % 2:
                draw.rectangle(
                    (x, y, min(x + block - 1, size[0]), min(y + block - 1, size[1])),
                    fill="#cfd6df",
                )
    return image


def render(animation_path: Path, spritesheet_path: Path, output_path: Path) -> None:
    manifest = json.loads(animation_path.read_text(encoding="utf-8"))
    atlas = manifest["atlas"]
    columns = int(atlas["columns"])
    rows = int(atlas["rows"])
    cell_width = int(atlas["cell_width"])
    cell_height = int(atlas["cell_height"])
    preview_width = cell_width // 2
    preview_height = cell_height // 2

    with Image.open(spritesheet_path) as source_image:
        source = source_image.convert("RGBA")
    contact = checkerboard(
        (columns * preview_width, rows * preview_height),
    )
    for row in range(rows):
        for column in range(columns):
            frame = source.crop(
                (
                    column * cell_width,
                    row * cell_height,
                    (column + 1) * cell_width,
                    (row + 1) * cell_height,
                )
            ).resize(
                (preview_width, preview_height),
                Image.Resampling.LANCZOS,
            )
            contact.paste(
                frame,
                (column * preview_width, row * preview_height),
                frame,
            )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    contact.save(output_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--animation", type=Path, required=True)
    parser.add_argument("--spritesheet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(args.animation, args.spritesheet, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
