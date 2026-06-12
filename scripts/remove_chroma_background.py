from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image

try:
    from scripts.enhance_spritesheet import clean_transparent_edges
except ModuleNotFoundError:
    from enhance_spritesheet import clean_transparent_edges


def sample_border_color(rgb: np.ndarray, inset: int = 8) -> np.ndarray:
    height, width, _ = rgb.shape
    inset = min(inset, max(0, min(height, width) // 4))
    top = rgb[inset, inset : width - inset or width]
    bottom = rgb[height - inset - 1, inset : width - inset or width]
    left = rgb[inset : height - inset or height, inset]
    right = rgb[inset : height - inset or height, width - inset - 1]
    border = np.concatenate((top, bottom, left, right), axis=0)
    return np.median(border, axis=0)


def remove_chroma_background(
    image: Image.Image,
    *,
    transparent_distance: float = 32,
    opaque_distance: float = 220,
) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    rgb = rgba[..., :3].astype(np.float32)
    key = sample_border_color(rgb)
    distance = np.linalg.norm(rgb - key, axis=2)
    alpha = np.clip(
        (distance - transparent_distance)
        * 255
        / (opaque_distance - transparent_distance),
        0,
        255,
    ).astype(np.uint8)
    rgba[..., 3] = alpha
    keyed = Image.fromarray(rgba)
    return clean_transparent_edges(keyed, alpha_floor=6)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--transparent-distance", type=float, default=32)
    parser.add_argument("--opaque-distance", type=float, default=220)
    args = parser.parse_args()

    with Image.open(args.input) as source:
        result = remove_chroma_background(
            source,
            transparent_distance=args.transparent_distance,
            opaque_distance=args.opaque_distance,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result.save(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
