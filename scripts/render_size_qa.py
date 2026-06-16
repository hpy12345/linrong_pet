from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def render(
    animation_path: Path,
    spritesheet_path: Path,
    output_dir: Path,
    heights: tuple[int, ...],
) -> None:
    manifest = json.loads(animation_path.read_text(encoding="utf-8"))
    atlas_data = manifest["atlas"]
    cell_width = int(atlas_data["cell_width"])
    cell_height = int(atlas_data["cell_height"])
    with Image.open(spritesheet_path) as image:
        atlas = image.convert("RGBA")
    output_dir.mkdir(parents=True, exist_ok=True)
    font = ImageFont.load_default()

    for height in heights:
        width = round(height * 192 / 208)
        states = list(manifest["states"].items())
        sheet = Image.new("RGB", (width * 4, height * 3), "#30343a")
        draw = ImageDraw.Draw(sheet)
        for slot, (state_name, state) in enumerate(states):
            if state_name == "sitting":
                index = int(state["frames"]) - 1
            elif state_name in {"heart", "hug"}:
                index = 5
            else:
                index = 0
            row = int(state["row"])
            frame = atlas.crop(
                (
                    index * cell_width,
                    row * cell_height,
                    (index + 1) * cell_width,
                    (row + 1) * cell_height,
                )
            ).resize((width, height), Image.Resampling.LANCZOS)
            x = slot % 4 * width
            y = slot // 4 * height
            sheet.paste(frame, (x, y), frame)
            draw.text((x + 3, y + 3), state_name, fill="white", font=font)
        sheet.save(output_dir / f"runtime-{height}px.png")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--animation", type=Path, required=True)
    parser.add_argument("--spritesheet", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--heights", nargs="+", type=int, default=(240, 320, 400))
    args = parser.parse_args()
    render(
        args.animation,
        args.spritesheet,
        args.output_dir,
        tuple(args.heights),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
