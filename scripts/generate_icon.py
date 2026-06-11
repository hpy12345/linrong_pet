from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def make_icon(spritesheet: Path, animation: Path, output: Path) -> None:
    manifest = json.loads(animation.read_text(encoding="utf-8"))
    cell_width = int(manifest["atlas"]["cell_width"])
    cell_height = int(manifest["atlas"]["cell_height"])
    with Image.open(spritesheet) as source:
        frame = source.convert("RGBA").crop((0, 0, cell_width, cell_height))
    alpha = frame.getchannel("A")
    bounds = alpha.getbbox()
    if bounds is None:
        raise ValueError("first idle frame is empty")
    subject = frame.crop(bounds)
    side = max(subject.width, subject.height)
    padding = max(8, round(side * 0.08))
    canvas = Image.new("RGBA", (side + padding * 2, side + padding * 2))
    canvas.alpha_composite(
        subject,
        (
            (canvas.width - subject.width) // 2,
            (canvas.height - subject.height) // 2,
        ),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(
        output,
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spritesheet", type=Path, required=True)
    parser.add_argument("--animation", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    make_icon(args.spritesheet, args.animation, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
