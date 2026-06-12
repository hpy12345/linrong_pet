from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _fit(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    copy = image.copy()
    copy.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "#202124")
    x = (size[0] - copy.width) // 2
    y = (size[1] - copy.height) // 2
    if copy.mode == "RGBA":
        canvas.paste(copy, (x, y), copy)
    else:
        canvas.paste(copy, (x, y))
    return canvas


def _sprite_face(frame: Image.Image, reference_height: int) -> Image.Image:
    rgba = frame.convert("RGBA")
    bounds = rgba.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("cannot crop a face from an empty frame")
    left, top, right, _bottom = bounds
    side = max(48, round(reference_height * 0.24))
    center_x = (left + right) // 2
    center_y = top + side // 2
    return rgba.crop(
        (
            max(0, center_x - side // 2),
            max(0, center_y - side // 2),
            min(rgba.width, center_x + side // 2),
            min(rgba.height, center_y + side // 2),
        )
    )


def render(
    animation_path: Path,
    spritesheet_path: Path,
    reference_path: Path,
    output_path: Path,
    reference_face_box: tuple[int, int, int, int],
) -> None:
    manifest = json.loads(animation_path.read_text(encoding="utf-8"))
    atlas_data = manifest["atlas"]
    cell_width = int(atlas_data["cell_width"])
    cell_height = int(atlas_data["cell_height"])
    with Image.open(spritesheet_path) as image:
        atlas = image.convert("RGBA")
    with Image.open(reference_path) as image:
        reference = image.convert("RGB").crop(reference_face_box)

    tile_size = (160, 180)
    label_height = 20
    state_count = len(manifest["states"])
    columns = 8
    rows = state_count + 1
    sheet = Image.new(
        "RGB",
        (columns * tile_size[0], rows * tile_size[1]),
        "#111111",
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()

    reference_tile = _fit(reference, (tile_size[0], tile_size[1] - label_height))
    for column in range(columns):
        x = column * tile_size[0]
        sheet.paste(reference_tile, (x, label_height))
        draw.text((x + 4, 4), "role.png reference", fill="white", font=font)

    for row_index, (state_name, state) in enumerate(
        manifest["states"].items(),
        start=1,
    ):
        row = int(state["row"])
        frame_count = int(state["frames"])
        for index in range(frame_count):
            frame = atlas.crop(
                (
                    index * cell_width,
                    row * cell_height,
                    (index + 1) * cell_width,
                    (row + 1) * cell_height,
                )
            )
            face = _sprite_face(frame, reference_height=398)
            tile = _fit(face, (tile_size[0], tile_size[1] - label_height))
            x = index * tile_size[0]
            y = row_index * tile_size[1]
            sheet.paste(tile, (x, y + label_height))
            draw.text(
                (x + 4, y + 4),
                f"{state_name}[{index}]",
                fill="white",
                font=font,
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--animation", type=Path, required=True)
    parser.add_argument("--spritesheet", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--reference-face-box",
        type=int,
        nargs=4,
        default=(500, 350, 1040, 900),
    )
    args = parser.parse_args()
    render(
        args.animation,
        args.spritesheet,
        args.reference,
        args.output,
        tuple(args.reference_face_box),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
