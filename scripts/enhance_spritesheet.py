from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import tempfile
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


def suspicious_edge_color(rgb: np.ndarray) -> np.ndarray:
    red = rgb[..., 0].astype(np.int16)
    green = rgb[..., 1].astype(np.int16)
    blue = rgb[..., 2].astype(np.int16)
    green_cast = (green > red + 22) & (green > blue + 12)
    cyan_cast = (
        (green > red + 24)
        & (blue > red + 24)
        & (np.abs(green - blue) < 96)
    )
    return green_cast | cyan_cast


def nearest_trusted_colors(
    rgb: np.ndarray,
    active: np.ndarray,
    trusted: np.ndarray,
) -> np.ndarray:
    height, width = active.shape
    filled = rgb.copy()
    visited = trusted.copy()
    queue: deque[tuple[int, int]] = deque(
        (int(y), int(x)) for y, x in np.argwhere(trusted)
    )
    if not queue:
        raise ValueError("frame contains no trustworthy opaque pixels")

    while queue:
        y, x = queue.popleft()
        color = filled[y, x]
        for next_y, next_x in (
            (y - 1, x),
            (y + 1, x),
            (y, x - 1),
            (y, x + 1),
        ):
            if not (0 <= next_y < height and 0 <= next_x < width):
                continue
            if visited[next_y, next_x] or not active[next_y, next_x]:
                continue
            filled[next_y, next_x] = color
            visited[next_y, next_x] = True
            queue.append((next_y, next_x))
    return filled


def keep_largest_component(rgba: np.ndarray) -> None:
    alpha = rgba[..., 3]
    active = alpha > 0
    height, width = active.shape
    visited = np.zeros(active.shape, dtype=bool)
    largest: list[tuple[int, int]] = []

    for start_y, start_x in np.argwhere(active):
        y = int(start_y)
        x = int(start_x)
        if visited[y, x]:
            continue
        visited[y, x] = True
        queue = [(y, x)]
        component: list[tuple[int, int]] = []
        while queue:
            current_y, current_x = queue.pop()
            component.append((current_y, current_x))
            for offset_y in (-1, 0, 1):
                for offset_x in (-1, 0, 1):
                    next_y = current_y + offset_y
                    next_x = current_x + offset_x
                    if not (0 <= next_y < height and 0 <= next_x < width):
                        continue
                    if visited[next_y, next_x] or not active[next_y, next_x]:
                        continue
                    visited[next_y, next_x] = True
                    queue.append((next_y, next_x))
        if len(component) > len(largest):
            largest = component

    if not largest:
        return
    keep = np.zeros(active.shape, dtype=bool)
    rows, columns = zip(*largest)
    keep[rows, columns] = True
    rgba[active & ~keep] = 0


def clean_transparent_edges(
    image: Image.Image,
    alpha_floor: int,
    *,
    keep_largest: bool = True,
) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    rgb = rgba[..., :3]
    alpha = rgba[..., 3]

    alpha[alpha <= alpha_floor] = 0
    if keep_largest:
        keep_largest_component(rgba)
    remaining = alpha > 0
    if not remaining.any():
        return Image.fromarray(rgba)

    cast = suspicious_edge_color(rgb)
    trusted = (alpha >= 248) & ~cast
    replacement = remaining & ((alpha < 248) | cast)
    filled = nearest_trusted_colors(rgb, remaining, trusted)
    rgb[replacement] = filled[replacement]

    nonzero = alpha > 0
    alpha[nonzero] = np.clip(
        (alpha[nonzero].astype(np.int32) - alpha_floor)
        * 255
        // (255 - alpha_floor),
        1,
        255,
    ).astype(np.uint8)
    rgb[alpha == 0] = 0
    return Image.fromarray(rgba)


def enhance_frame(
    frame: Image.Image,
    executable: Path,
    models: Path,
    work_dir: Path,
    name: str,
) -> Image.Image:
    input_dir = work_dir / f"{name}-inputs"
    output_dir = work_dir / f"{name}-outputs"
    input_dir.mkdir()
    output_dir.mkdir()
    cropped, crop_box = prepare_frame(frame, input_dir / f"{name}.png")
    run_realesrgan(executable, models, input_dir, output_dir)
    return finish_frame(
        cropped,
        output_dir / f"{name}.png",
        crop_box,
        frame.size,
    )


def prepare_frame(
    frame: Image.Image,
    input_path: Path,
) -> tuple[Image.Image, tuple[int, int, int, int]]:
    cleaned = clean_transparent_edges(frame, alpha_floor=20)
    bounds = cleaned.getchannel("A").getbbox()
    if bounds is None:
        raise ValueError(f"empty frame: {input_path.stem}")
    left, top, right, bottom = bounds
    padding = 8
    crop_box = (
        max(0, left - padding),
        max(0, top - padding),
        min(cleaned.width, right + padding),
        min(cleaned.height, bottom + padding),
    )
    cropped = cleaned.crop(crop_box)
    matte = Image.new("RGBA", cropped.size, (96, 96, 96, 255))
    matte.alpha_composite(cropped)
    matte.convert("RGB").save(input_path)
    return cropped, crop_box


def run_realesrgan(
    executable: Path,
    models: Path,
    input_path: Path,
    output_path: Path,
) -> None:
    command = [
        str(executable),
        "-i",
        str(input_path),
        "-o",
        str(output_path),
        "-m",
        str(models),
        "-n",
        "realesrgan-x4plus",
        "-s",
        "4",
        "-t",
        "128",
        "-f",
        "png",
    ]
    subprocess.run(command, check=True, capture_output=True, text=True)


def finish_frame(
    cropped: Image.Image,
    output_path: Path,
    crop_box: tuple[int, int, int, int],
    frame_size: tuple[int, int],
) -> Image.Image:
    with Image.open(output_path) as upscaled:
        upscaled_rgb = upscaled.convert("RGB").resize(
            (cropped.width * 2, cropped.height * 2),
            Image.Resampling.LANCZOS,
        )
    alpha = cropped.getchannel("A").resize(
        upscaled_rgb.size,
        Image.Resampling.LANCZOS,
    )
    result = upscaled_rgb.convert("RGBA")
    result.putalpha(alpha)
    result = clean_transparent_edges(result, alpha_floor=8)
    sharpened_rgb = result.convert("RGB").filter(
        ImageFilter.UnsharpMask(radius=0.65, percent=45, threshold=4)
    )
    sharpened = sharpened_rgb.convert("RGBA")
    sharpened.putalpha(result.getchannel("A"))
    sharpened = clean_transparent_edges(sharpened, alpha_floor=0)
    array = np.asarray(sharpened, dtype=np.uint8).copy()
    array[array[..., 3] == 0, :3] = 0
    canvas = Image.new("RGBA", (frame_size[0] * 2, frame_size[1] * 2))
    canvas.alpha_composite(
        Image.fromarray(array),
        (crop_box[0] * 2, crop_box[1] * 2),
    )
    return canvas


def enhance(
    animation_path: Path,
    spritesheet_path: Path,
    output_path: Path,
    executable: Path,
    models: Path,
) -> None:
    manifest = json.loads(animation_path.read_text(encoding="utf-8"))
    atlas = manifest["atlas"]
    columns = int(atlas["columns"])
    rows = int(atlas["rows"])
    cell_width = int(atlas["cell_width"])
    cell_height = int(atlas["cell_height"])

    with Image.open(spritesheet_path) as source_image:
        source = source_image.convert("RGBA")
    expected = (columns * cell_width, rows * cell_height)
    legacy_size = (expected[0] // 2, expected[1] // 2)
    if source.size != legacy_size:
        raise ValueError(
            f"source atlas is {source.size}, expected legacy atlas {legacy_size}"
        )
    source_cell_width = cell_width // 2
    source_cell_height = cell_height // 2

    destination = Image.new("RGBA", expected)
    with tempfile.TemporaryDirectory(prefix="linrong-enhance-") as temp:
        work_dir = Path(temp)
        input_dir = work_dir / "input"
        output_dir = work_dir / "output"
        input_dir.mkdir()
        output_dir.mkdir()
        prepared: list[
            tuple[
                str,
                int,
                int,
                Image.Image,
                tuple[int, int, int, int],
                tuple[int, int],
            ]
        ] = []
        for state_name, state in manifest["states"].items():
            row = int(state["row"])
            for column in range(int(state["frames"])):
                box = (
                    column * source_cell_width,
                    row * source_cell_height,
                    (column + 1) * source_cell_width,
                    (row + 1) * source_cell_height,
                )
                frame = source.crop(box)
                stem = f"{row:02d}-{column:02d}"
                cropped, crop_box = prepare_frame(
                    frame,
                    input_dir / f"{stem}.png",
                )
                prepared.append(
                    (
                        state_name,
                        row,
                        column,
                        cropped,
                        crop_box,
                        frame.size,
                    )
                )

        print(f"enhancing {len(prepared)} frames with Real-ESRGAN")
        run_realesrgan(executable, models, input_dir, output_dir)
        for state_name, row, column, cropped, crop_box, frame_size in prepared:
                enhanced = finish_frame(
                    cropped,
                    output_dir / f"{row:02d}-{column:02d}.png",
                    crop_box,
                    frame_size,
                )
                destination.alpha_composite(
                    enhanced,
                    (column * cell_width, row * cell_height),
                )
                print(f"assembled {state_name}[{column + 1}]")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output_path.with_suffix(".tmp.webp")
    destination.save(temporary_output, format="WEBP", lossless=True, method=6)
    shutil.move(temporary_output, output_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--animation", type=Path, required=True)
    parser.add_argument("--spritesheet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    args = parser.parse_args()
    enhance(
        args.animation,
        args.spritesheet,
        args.output,
        args.executable.resolve(),
        args.models.resolve(),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
