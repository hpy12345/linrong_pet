from __future__ import annotations

import argparse
import json
import shutil
from collections import deque
from pathlib import Path

import numpy as np
from PIL import Image

try:
    from scripts.enhance_spritesheet import clean_transparent_edges
except ModuleNotFoundError:
    from enhance_spritesheet import clean_transparent_edges


def _cluster_centers(mask: np.ndarray, count: int) -> np.ndarray:
    height, width = mask.shape
    y0 = round(height * 0.12)
    y1 = round(height * 0.62)
    _, xs = np.where(mask[y0:y1])
    if xs.size == 0:
        raise ValueError("animation strip has no visible subject pixels")
    centers = np.linspace(width / (count * 2), width - width / (count * 2), count)
    sample = xs.astype(np.float64)
    for _ in range(30):
        labels = np.abs(sample[:, None] - centers[None, :]).argmin(axis=1)
        updated = np.array(
            [
                sample[labels == index].mean()
                if np.any(labels == index)
                else centers[index]
                for index in range(count)
            ]
        )
        if np.allclose(updated, centers, atol=0.05):
            break
        centers = updated
    return np.sort(centers)


def _split_subjects(strip: Image.Image, count: int) -> list[Image.Image]:
    rgba = np.asarray(strip.convert("RGBA"), dtype=np.uint8)
    visible = rgba[..., 3] > 24
    centers = _cluster_centers(visible, count)
    labels = np.full(visible.shape, -1, dtype=np.int16)
    queue: deque[tuple[int, int]] = deque()
    seed_top = round(strip.height * 0.12)
    seed_bottom = round(strip.height * 0.62)
    seed_half_width = max(28, round(strip.width / count * 0.18))

    for index, center in enumerate(centers):
        center_x = round(center)
        left = max(0, center_x - seed_half_width)
        right = min(strip.width, center_x + seed_half_width + 1)
        seed = visible[seed_top:seed_bottom, left:right]
        for relative_y, relative_x in np.argwhere(seed):
            y = seed_top + int(relative_y)
            x = left + int(relative_x)
            labels[y, x] = index
            queue.append((y, x))

    while queue:
        y, x = queue.popleft()
        label = labels[y, x]
        for next_y, next_x in (
            (y - 1, x),
            (y + 1, x),
            (y, x - 1),
            (y, x + 1),
        ):
            if not (
                0 <= next_y < strip.height
                and 0 <= next_x < strip.width
                and visible[next_y, next_x]
                and labels[next_y, next_x] < 0
            ):
                continue
            labels[next_y, next_x] = label
            queue.append((next_y, next_x))

    unassigned_y, unassigned_x = np.where(visible & (labels < 0))
    if unassigned_x.size:
        nearest = np.abs(
            unassigned_x[:, None].astype(np.float64) - centers[None, :]
        ).argmin(axis=1)
        labels[unassigned_y, unassigned_x] = nearest.astype(np.int16)

    subjects: list[Image.Image] = []
    for index in range(count):
        isolated = rgba.copy()
        isolated[labels != index] = 0
        image = Image.fromarray(isolated)
        bounds = image.getchannel("A").getbbox()
        if bounds is None:
            raise ValueError(f"empty animation frame {index}")
        subjects.append(image.crop(bounds))
    return subjects


def extract_sequence_frames(
    strip: Image.Image,
    count: int,
    cell_size: tuple[int, int],
    first_frame_height: int,
) -> list[Image.Image]:
    subjects = _split_subjects(strip, count)
    cell_width, cell_height = cell_size
    common_scale = first_frame_height / subjects[0].height
    common_scale = min(
        common_scale,
        min(cell_width * 0.9 / subject.width for subject in subjects),
    )
    baseline = cell_height - 9
    frames: list[Image.Image] = []

    for subject in subjects:
        resized = subject.resize(
            (
                max(1, round(subject.width * common_scale)),
                max(1, round(subject.height * common_scale)),
            ),
            Image.Resampling.LANCZOS,
        )
        canvas = Image.new("RGBA", cell_size)
        x = (cell_width - resized.width) // 2
        y = baseline - resized.height
        canvas.alpha_composite(resized, (x, y))
        frames.append(clean_transparent_edges(canvas, alpha_floor=6))
    return frames


def _replace_row(
    atlas: Image.Image,
    row: int,
    frames: list[Image.Image],
    cell_size: tuple[int, int],
) -> None:
    cell_width, cell_height = cell_size
    for index in range(8):
        atlas.paste(
            Image.new("RGBA", cell_size),
            (index * cell_width, row * cell_height),
        )
    for index, frame in enumerate(frames):
        atlas.alpha_composite(
            frame,
            (index * cell_width, row * cell_height),
        )


def build_assets(
    animation_path: Path,
    atlas_path: Path,
    walking_strip_path: Path,
    sitting_strip_path: Path,
    output_path: Path,
) -> None:
    manifest = json.loads(animation_path.read_text(encoding="utf-8"))
    atlas_data = manifest["atlas"]
    cell_size = (
        int(atlas_data["cell_width"]),
        int(atlas_data["cell_height"]),
    )
    states = manifest["states"]

    with Image.open(atlas_path) as image:
        atlas = image.convert("RGBA")
    with Image.open(walking_strip_path) as image:
        walking_strip = image.convert("RGBA")
    with Image.open(sitting_strip_path) as image:
        sitting_strip = image.convert("RGBA")

    walking_right = extract_sequence_frames(
        walking_strip,
        count=8,
        cell_size=cell_size,
        first_frame_height=370,
    )
    walking_left = [
        frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        for frame in walking_right
    ]
    sitting = extract_sequence_frames(
        sitting_strip,
        count=8,
        cell_size=cell_size,
        first_frame_height=398,
    )

    _replace_row(
        atlas,
        int(states["walking-right"]["row"]),
        walking_right,
        cell_size,
    )
    _replace_row(
        atlas,
        int(states["walking-left"]["row"]),
        walking_left,
        cell_size,
    )
    _replace_row(
        atlas,
        int(states["sitting"]["row"]),
        sitting,
        cell_size,
    )

    cleaned = Image.new("RGBA", atlas.size)
    for state in states.values():
        row = int(state["row"])
        for index in range(int(state["frames"])):
            box = (
                index * cell_size[0],
                row * cell_size[1],
                (index + 1) * cell_size[0],
                (row + 1) * cell_size[1],
            )
            frame = clean_transparent_edges(atlas.crop(box), alpha_floor=2)
            cleaned.alpha_composite(
                frame,
                (index * cell_size[0], row * cell_size[1]),
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".tmp.webp")
    cleaned.save(temporary, format="WEBP", lossless=True, method=6)
    shutil.move(temporary, output_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--animation", type=Path, required=True)
    parser.add_argument("--atlas", type=Path, required=True)
    parser.add_argument("--walking-strip", type=Path, required=True)
    parser.add_argument("--sitting-strip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    build_assets(
        args.animation,
        args.atlas,
        args.walking_strip,
        args.sitting_strip,
        args.output,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
