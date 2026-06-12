import json

from PIL import Image

import scripts.export_runtime_frames as export_module
from scripts.export_runtime_frames import export_frames


def test_export_frames_replaces_existing_files_atomically(tmp_path):
    animation = tmp_path / "animation.json"
    animation.write_text(
        json.dumps(
            {
                "atlas": {
                    "cell_width": 16,
                    "cell_height": 20,
                },
                "states": {
                    "idle": {
                        "row": 0,
                        "frames": 1,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    atlas = Image.new("RGBA", (16, 20), (40, 80, 120, 255))
    spritesheet = tmp_path / "spritesheet.webp"
    atlas.save(spritesheet, format="WEBP", lossless=True)
    output = tmp_path / "frames"
    output.mkdir()
    existing = output / "idle-00.webp"
    existing.write_bytes(b"old")

    export_frames(animation, spritesheet, output)

    with Image.open(existing) as frame:
        assert frame.size == (16, 20)
        assert frame.convert("RGBA").getpixel((0, 0)) == (40, 80, 120, 255)
    assert not list(output.glob("*.tmp"))


def test_export_frames_does_not_replace_identical_files(
    tmp_path,
    monkeypatch,
):
    animation = tmp_path / "animation.json"
    animation.write_text(
        json.dumps(
            {
                "atlas": {
                    "cell_width": 16,
                    "cell_height": 20,
                },
                "states": {
                    "idle": {
                        "row": 0,
                        "frames": 1,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    spritesheet = tmp_path / "spritesheet.webp"
    Image.new("RGBA", (16, 20), (40, 80, 120, 255)).save(
        spritesheet,
        format="WEBP",
        lossless=True,
    )
    output = tmp_path / "frames"

    export_frames(animation, spritesheet, output)
    monkeypatch.setattr(
        export_module.os,
        "replace",
        lambda *_: (_ for _ in ()).throw(
            AssertionError("identical frame should not be replaced")
        ),
    )

    export_frames(animation, spritesheet, output)

    assert not list(output.glob("*.tmp"))
