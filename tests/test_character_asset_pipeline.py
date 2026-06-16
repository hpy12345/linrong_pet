from pathlib import Path

from PIL import Image, ImageDraw

from scripts.refine_character_assets import (
    _dark_head_width,
    _largest_component_bounds,
    _normalize_transparent_pixels,
    build_assets_from_manifest,
    extract_sequence_frames,
)
from scripts.remove_chroma_background import remove_chroma_background


def _strip(subject_sizes: list[tuple[int, int]]) -> Image.Image:
    slot_width = 240
    strip = Image.new("RGBA", (slot_width * len(subject_sizes), 700))
    draw = ImageDraw.Draw(strip)
    for index, (width, height) in enumerate(subject_sizes):
        left = index * slot_width + (slot_width - width) // 2
        top = 680 - height
        draw.rectangle(
            (left, top, left + width - 1, top + height - 1),
            fill=(220, 180, 150, 255),
        )
    return strip


def test_extract_sequence_frames_downsamples_with_one_common_scale():
    strip = _strip([(120, 600), (120, 450), (130, 330)])
    frames = extract_sequence_frames(
        strip,
        count=3,
        cell_size=(384, 416),
        first_frame_height=398,
    )
    bounds = [frame.getchannel("A").getbbox() for frame in frames]
    heights = [bound[3] - bound[1] for bound in bounds if bound is not None]

    assert heights == [398, 298, 219]
    assert {bound[3] for bound in bounds if bound is not None} == {407}


def test_tallest_pose_limits_the_common_row_scale():
    strip = _strip([(100, 400), (120, 600)])
    frames = extract_sequence_frames(
        strip,
        count=2,
        cell_size=(384, 416),
        first_frame_height=398,
    )
    bounds = [frame.getchannel("A").getbbox() for frame in frames]
    heights = [bound[3] - bound[1] for bound in bounds if bound is not None]

    assert heights == [265, 398]
    assert {bound[3] for bound in bounds if bound is not None} == {407}


def test_manifest_build_mirrors_without_reversing_frame_order(tmp_path):
    strip = _strip([(90, 600), (120, 570)])
    strip_path = tmp_path / "right.png"
    strip.save(strip_path)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        """
        {
          "atlas": {
            "columns": 2,
            "rows": 2,
            "cell_width": 384,
            "cell_height": 416
          },
          "states": {
            "right": {
              "row": 0,
              "frames": 2,
              "source": "right.png",
              "target_first_frame_height": 398
            },
            "left": {
              "row": 1,
              "frames": 2,
              "mirror_of": "right",
              "target_first_frame_height": 398
            }
          }
        }
        """,
        encoding="utf-8",
    )
    output = tmp_path / "atlas.webp"
    build_assets_from_manifest(manifest, output)

    with Image.open(output) as image:
        atlas = image.convert("RGBA")
    right_zero = atlas.crop((0, 0, 384, 416))
    right_one = atlas.crop((384, 0, 768, 416))
    left_zero = atlas.crop((0, 416, 384, 832))
    left_one = atlas.crop((384, 416, 768, 832))
    assert left_zero.tobytes() == right_zero.transpose(
        Image.Transpose.FLIP_LEFT_RIGHT
    ).tobytes()
    assert left_one.tobytes() == right_one.transpose(
        Image.Transpose.FLIP_LEFT_RIGHT
    ).tobytes()


def test_manifest_build_accepts_individual_frame_sources(tmp_path):
    frame_paths = []
    for index, height in enumerate((600, 450)):
        frame = _strip([(90, height)])
        path = tmp_path / f"frame-{index}.png"
        frame.save(path)
        frame_paths.append(path.name)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        f"""
        {{
          "atlas": {{
            "columns": 2,
            "rows": 1,
            "cell_width": 384,
            "cell_height": 416
          }},
          "states": {{
            "pose": {{
              "row": 0,
              "frames": 2,
              "frame_sources": {frame_paths!r},
              "target_first_frame_height": 398
            }}
          }}
        }}
        """.replace("'", '"'),
        encoding="utf-8",
    )
    output = tmp_path / "atlas.webp"
    build_assets_from_manifest(manifest, output)

    with Image.open(output) as image:
        atlas = image.convert("RGBA")
    first = atlas.crop((0, 0, 384, 416)).getchannel("A").getbbox()
    second = atlas.crop((384, 0, 768, 416)).getchannel("A").getbbox()
    assert first is not None and second is not None
    assert first[3] - first[1] == 398
    assert second[3] - second[1] == 298


def test_individual_frame_source_scales_normalize_pixel_density(tmp_path):
    frame_paths = []
    for index, (width, height) in enumerate(((100, 600), (200, 1200))):
        frame = Image.new("RGBA", (320, 1300))
        draw = ImageDraw.Draw(frame)
        left = (frame.width - width) // 2
        draw.rectangle(
            (left, 1280 - height, left + width - 1, 1279),
            fill=(220, 180, 150, 255),
        )
        path = tmp_path / f"frame-{index}.png"
        frame.save(path)
        frame_paths.append(path.name)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        f"""
        {{
          "atlas": {{
            "columns": 2,
            "rows": 1,
            "cell_width": 384,
            "cell_height": 416
          }},
          "states": {{
            "pose": {{
              "row": 0,
              "frames": 2,
              "frame_sources": {frame_paths!r},
              "frame_source_scales": [1.0, 0.5],
              "target_first_frame_height": 398
            }}
          }}
        }}
        """.replace("'", '"'),
        encoding="utf-8",
    )
    output = tmp_path / "atlas.webp"
    build_assets_from_manifest(manifest, output)

    with Image.open(output) as image:
        atlas = image.convert("RGBA")
    first = atlas.crop((0, 0, 384, 416)).getchannel("A").getbbox()
    second = atlas.crop((384, 0, 768, 416)).getchannel("A").getbbox()
    assert first is not None and second is not None
    assert first[3] - first[1] == second[3] - second[1] == 398
    assert first[2] - first[0] == second[2] - second[0]


def test_target_head_width_caps_row_scale_and_applies_baseline_offsets():
    subjects = []
    for width, height in ((100, 600), (100, 400)):
        subject = Image.new("RGBA", (width, height), (210, 170, 140, 255))
        draw = ImageDraw.Draw(subject)
        draw.rectangle((25, 0, 74, 80), fill=(20, 20, 20, 255))
        subjects.append(subject)

    from scripts.refine_character_assets import _render_subjects

    frames = _render_subjects(
        subjects,
        cell_size=(384, 416),
        first_frame_height=398,
        baseline=407,
        baseline_offsets=[0, -40],
        target_head_width=25,
    )
    bounds = [frame.getchannel("A").getbbox() for frame in frames]

    assert _dark_head_width(subjects[0]) == 50
    assert bounds[0] is not None and bounds[1] is not None
    assert bounds[0][3] == 407
    assert bounds[1][3] == 367
    assert bounds[0][3] - bounds[0][1] == 300
    assert bounds[1][3] - bounds[1][1] == 200


def test_source_density_factor_can_exceed_one_when_final_scale_downsamples():
    subject = Image.new("RGBA", (100, 500), (210, 170, 140, 255))

    from scripts.refine_character_assets import _render_subjects

    frames = _render_subjects(
        [subject],
        cell_size=(384, 416),
        first_frame_height=398,
        subject_scales=[1.1],
    )
    bounds = frames[0].getchannel("A").getbbox()

    assert bounds is not None
    assert bounds[3] - bounds[1] == 398


def test_pipeline_rejects_source_below_target_resolution():
    strip = _strip([(80, 200)])
    try:
        extract_sequence_frames(
            strip,
            count=1,
            cell_size=(384, 416),
            first_frame_height=398,
        )
    except ValueError as exc:
        assert "only downsampling is allowed" in str(exc)
    else:
        raise AssertionError("low-resolution source was accepted")


def test_nearly_transparent_pixels_are_fully_normalized():
    image = Image.new("RGBA", (2, 1))
    image.putpixel((0, 0), (0, 255, 255, 4))
    image.putpixel((1, 0), (20, 30, 40, 7))

    normalized = _normalize_transparent_pixels(image)

    assert normalized.getpixel((0, 0)) == (0, 0, 0, 0)
    assert normalized.getpixel((1, 0)) == (20, 30, 40, 7)


def test_chroma_key_removes_background_and_keeps_subject():
    image = Image.new("RGB", (40, 40), (5, 248, 252))
    draw = ImageDraw.Draw(image)
    draw.rectangle((12, 8, 27, 35), fill=(50, 35, 28))

    keyed = remove_chroma_background(image)

    assert keyed.getpixel((0, 0))[3] == 0
    assert keyed.getpixel((20, 20))[3] == 255
    assert keyed.getchannel("A").getbbox() == (12, 8, 28, 36)


def test_largest_component_geometry_keeps_detached_effects_from_scaling_person():
    subject = Image.new("RGBA", (300, 650))
    draw = ImageDraw.Draw(subject)
    draw.rectangle((100, 50, 199, 649), fill=(210, 170, 140, 255))
    for x, y in ((20, 40), (260, 80), (25, 300), (270, 360)):
        draw.rectangle((x, y, x + 11, y + 11), fill=(255, 80, 110, 255))
    subject = subject.crop(subject.getchannel("A").getbbox())

    from scripts.refine_character_assets import _render_subjects

    frames = _render_subjects(
        [subject],
        cell_size=(384, 416),
        first_frame_height=398,
        scale_by_largest_component=True,
        preserve_detached_effects=True,
        max_detached_effects=4,
    )
    person_bounds = _largest_component_bounds(frames[0])
    full_bounds = frames[0].getchannel("A").getbbox()

    assert abs((person_bounds[3] - person_bounds[1]) - 398) <= 1
    assert full_bounds is not None
    assert full_bounds[0] < person_bounds[0]
    assert full_bounds[2] > person_bounds[2]
