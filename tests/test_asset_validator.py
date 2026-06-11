import json

from PIL import Image

from scripts.validate_assets import validate


def test_validator_accepts_contract(tmp_path):
    animation = tmp_path / "animation.json"
    source = (
        __import__("pathlib").Path(__file__).parents[1]
        / "src"
        / "linrong_pet"
        / "assets"
        / "animation.json"
    )
    animation.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    manifest = json.loads(animation.read_text(encoding="utf-8"))
    atlas_info = manifest["atlas"]
    width = atlas_info["cell_width"]
    height = atlas_info["cell_height"]
    atlas = Image.new(
        "RGBA",
        (atlas_info["columns"] * width, atlas_info["rows"] * height),
    )
    for state_name, state in manifest["states"].items():
        for column in range(state["frames"]):
            color = (
                80 + column * 3,
                70 + state["row"] * 2,
                60 + len(state_name),
                255,
            )
            x = column * width + 10
            y = state["row"] * height + 10
            for offset_y in range(10):
                for offset_x in range(10):
                    atlas.putpixel((x + offset_x, y + offset_y), color)
    spritesheet = tmp_path / "spritesheet.webp"
    atlas.save(spritesheet, lossless=True)

    assert validate(animation, spritesheet) == []
