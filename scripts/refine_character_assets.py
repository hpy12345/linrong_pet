from __future__ import annotations

import argparse
import json
import shutil
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

try:
    from scripts.enhance_spritesheet import clean_transparent_edges
except ModuleNotFoundError:
    from enhance_spritesheet import clean_transparent_edges


@dataclass(frozen=True, slots=True)
class RowSpec:
    row: int
    frames: int
    source: Path | None
    frame_sources: tuple[Path, ...]
    frame_source_scales: tuple[float, ...]
    frame_baseline_offsets: tuple[int, ...]
    mirror_of: str | None
    scale_reference: str | None
    first_frame_from: str | None
    target_first_frame_height: int
    baseline: int
    max_width_ratio: float
    target_head_width: int | None
    scale_by_largest_component: bool
    preserve_detached_effects: bool
    max_detached_effects: int | None
    detached_effect_min_area: int


def _cluster_centers(mask: np.ndarray, count: int) -> np.ndarray:
    height, width = mask.shape
    y0 = round(height * 0.05)
    y1 = round(height * 0.95)
    _, xs = np.where(mask[y0:y1])
    if xs.size == 0:
        raise ValueError("animation strip has no visible subject pixels")
    centers = np.linspace(width / (count * 2), width - width / (count * 2), count)
    sample = xs.astype(np.float64)
    for _ in range(40):
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
    slot_width = strip.width / count
    seed_half_width = max(12, round(slot_width * 0.28))

    for index, center in enumerate(centers):
        center_x = round(center)
        left = max(0, center_x - seed_half_width)
        right = min(strip.width, center_x + seed_half_width + 1)
        for y, x in np.argwhere(visible[:, left:right]):
            absolute_x = left + int(x)
            labels[int(y), absolute_x] = index
            queue.append((int(y), absolute_x))

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
    *,
    baseline: int | None = None,
    max_width_ratio: float = 0.9,
    scale_reference_height: int | None = None,
) -> list[Image.Image]:
    subjects = _split_subjects(strip, count)
    return _render_subjects(
        subjects,
        cell_size,
        first_frame_height,
        baseline=baseline,
        max_width_ratio=max_width_ratio,
        scale_reference_height=scale_reference_height,
    )


def _render_subjects(
    subjects: list[Image.Image],
    cell_size: tuple[int, int],
    first_frame_height: int,
    *,
    baseline: int | None = None,
    max_width_ratio: float = 0.9,
    scale_reference_height: int | None = None,
    subject_scales: list[float] | None = None,
    baseline_offsets: list[int] | None = None,
    target_head_width: int | None = None,
    scale_by_largest_component: bool = False,
    preserve_detached_effects: bool = False,
    max_detached_effects: int | None = None,
    detached_effect_min_area: int = 8,
) -> list[Image.Image]:
    cell_width, cell_height = cell_size
    resolved_subject_scales = subject_scales or [1.0] * len(subjects)
    if len(resolved_subject_scales) != len(subjects):
        raise ValueError("subject scale count does not match frame count")
    if any(scale <= 0 for scale in resolved_subject_scales):
        raise ValueError("subject scales must be positive")
    if preserve_detached_effects:
        subjects = [
            _filter_detached_components(
                subject,
                max_detached=max_detached_effects,
                min_detached_area=detached_effect_min_area,
            )
            for subject in subjects
        ]
    geometry_bounds = [
        (
            _largest_component_bounds(subject)
            if scale_by_largest_component
            else (0, 0, subject.width, subject.height)
        )
        for subject in subjects
    ]
    normalized_sizes = [
        (
            (bounds[2] - bounds[0]) * scale,
            (bounds[3] - bounds[1]) * scale,
        )
        for bounds, scale in zip(
            geometry_bounds,
            resolved_subject_scales,
            strict=True,
        )
    ]
    reference_height = (
        scale_reference_height or normalized_sizes[0][1]
    )
    common_scale = first_frame_height / reference_height
    if target_head_width is not None:
        normalized_head_widths = [
            _dark_head_width(subject) * scale
            for subject, scale in zip(
                subjects,
                resolved_subject_scales,
            )
        ]
        if min(normalized_head_widths) <= 0:
            raise ValueError("cannot measure subject head width")
        common_scale = min(
            common_scale,
            target_head_width / float(np.median(normalized_head_widths)),
        )
    common_scale = min(
        common_scale,
        min(
            cell_width * max_width_ratio / width
            for width, _ in normalized_sizes
        ),
        min(
            (cell_height - 18) / height
            for _, height in normalized_sizes
        ),
    )
    effective_scales = [
        common_scale * scale for scale in resolved_subject_scales
    ]
    if any(scale >= 1 for scale in effective_scales):
        raise ValueError(
            "source strip is below target resolution; only downsampling is allowed"
        )
    resolved_baseline = baseline if baseline is not None else cell_height - 9
    resolved_offsets = baseline_offsets or [0] * len(subjects)
    if len(resolved_offsets) != len(subjects):
        raise ValueError("baseline offset count does not match frame count")
    frames: list[Image.Image] = []

    for subject, geometry, effective_scale, baseline_offset in zip(
        subjects,
        geometry_bounds,
        effective_scales,
        resolved_offsets,
        strict=True,
    ):
        resized = subject.resize(
            (
                max(1, round(subject.width * effective_scale)),
                max(1, round(subject.height * effective_scale)),
            ),
            Image.Resampling.LANCZOS,
        )
        canvas = Image.new("RGBA", cell_size)
        geometry_left = round(geometry[0] * effective_scale)
        geometry_right = round(geometry[2] * effective_scale)
        geometry_bottom = round(geometry[3] * effective_scale)
        geometry_width = geometry_right - geometry_left
        x = (cell_width - geometry_width) // 2 - geometry_left
        y = resolved_baseline + baseline_offset - geometry_bottom
        if (
            x < 0
            or y < 0
            or x + resized.width > cell_width
            or y + resized.height > cell_height
        ):
            raise ValueError("scaled subject or effects exceed the target cell")
        canvas.alpha_composite(resized, (x, y))
        frames.append(
            clean_transparent_edges(
                canvas,
                alpha_floor=6,
                keep_largest=not preserve_detached_effects,
            )
        )
    return frames


def _filter_detached_components(
    subject: Image.Image,
    *,
    max_detached: int | None,
    min_detached_area: int,
) -> Image.Image:
    rgba = np.asarray(subject.convert("RGBA"), dtype=np.uint8).copy()
    visible = rgba[..., 3] > 24
    visited = np.zeros(visible.shape, dtype=bool)
    components: list[list[tuple[int, int]]] = []

    for seed_y, seed_x in np.argwhere(visible):
        y = int(seed_y)
        x = int(seed_x)
        if visited[y, x]:
            continue
        queue = deque([(y, x)])
        visited[y, x] = True
        pixels: list[tuple[int, int]] = []
        while queue:
            current_y, current_x = queue.popleft()
            pixels.append((current_y, current_x))
            for next_y, next_x in (
                (current_y - 1, current_x),
                (current_y + 1, current_x),
                (current_y, current_x - 1),
                (current_y, current_x + 1),
            ):
                if (
                    0 <= next_y < visible.shape[0]
                    and 0 <= next_x < visible.shape[1]
                    and visible[next_y, next_x]
                    and not visited[next_y, next_x]
                ):
                    visited[next_y, next_x] = True
                    queue.append((next_y, next_x))

        components.append(pixels)

    if not components:
        raise ValueError("subject has no visible component")
    components.sort(key=len, reverse=True)
    detached = [
        component
        for component in components[1:]
        if len(component) >= min_detached_area
    ]
    if max_detached is not None:
        detached = detached[:max_detached]
    keep = np.zeros(visible.shape, dtype=bool)
    for component in [components[0], *detached]:
        rows, columns = zip(*component)
        keep[rows, columns] = True
    rgba[~keep] = 0
    bounds = Image.fromarray(rgba).getchannel("A").getbbox()
    if bounds is None:
        raise ValueError("component filtering removed the subject")
    return Image.fromarray(rgba).crop(bounds)


def _largest_component_bounds(
    subject: Image.Image,
) -> tuple[int, int, int, int]:
    visible = np.asarray(subject.getchannel("A"), dtype=np.uint8) > 24
    visited = np.zeros(visible.shape, dtype=bool)
    best_area = 0
    best_bounds: tuple[int, int, int, int] | None = None

    for seed_y, seed_x in np.argwhere(visible):
        y = int(seed_y)
        x = int(seed_x)
        if visited[y, x]:
            continue
        queue = deque([(y, x)])
        visited[y, x] = True
        area = 0
        left = right = x
        top = bottom = y
        while queue:
            current_y, current_x = queue.popleft()
            area += 1
            left = min(left, current_x)
            right = max(right, current_x)
            top = min(top, current_y)
            bottom = max(bottom, current_y)
            for next_y, next_x in (
                (current_y - 1, current_x),
                (current_y + 1, current_x),
                (current_y, current_x - 1),
                (current_y, current_x + 1),
            ):
                if (
                    0 <= next_y < visible.shape[0]
                    and 0 <= next_x < visible.shape[1]
                    and visible[next_y, next_x]
                    and not visited[next_y, next_x]
                ):
                    visited[next_y, next_x] = True
                    queue.append((next_y, next_x))
        if area > best_area:
            best_area = area
            best_bounds = (left, top, right + 1, bottom + 1)

    if best_bounds is None:
        raise ValueError("subject has no visible component")
    return best_bounds


def _dark_head_width(subject: Image.Image) -> int:
    rgba = np.asarray(subject.convert("RGBA"), dtype=np.uint8)
    sample_height = min(
        subject.height,
        max(1, round(subject.width * 0.42)),
    )
    sample = rgba[:sample_height]
    dark_hair = (
        (sample[..., :3].mean(axis=2) < 90)
        & (sample[..., 3] > 128)
    )
    columns = np.where(dark_hair.any(axis=0))[0]
    if columns.size == 0:
        return 0
    return int(columns[-1] - columns[0] + 1)


def _replace_row(
    atlas: Image.Image,
    row: int,
    frames: list[Image.Image],
    cell_size: tuple[int, int],
) -> None:
    cell_width, cell_height = cell_size
    for index, frame in enumerate(frames):
        atlas.alpha_composite(
            frame,
            (index * cell_width, row * cell_height),
        )


def _normalize_transparent_pixels(image: Image.Image) -> Image.Image:
    rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    invisible = rgba[..., 3] <= 6
    rgba[invisible] = 0
    return Image.fromarray(rgba)


def _resolve_path(manifest_path: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (manifest_path.parent / path).resolve()


def _load_manifest(
    manifest_path: Path,
) -> tuple[tuple[int, int], int, int, dict[str, RowSpec]]:
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    atlas = raw["atlas"]
    columns = int(atlas["columns"])
    rows = int(atlas["rows"])
    cell_size = (int(atlas["cell_width"]), int(atlas["cell_height"]))
    default_baseline = int(raw.get("baseline", cell_size[1] - 9))
    specs: dict[str, RowSpec] = {}
    for name, value in raw["states"].items():
        source_value = value.get("source")
        specs[name] = RowSpec(
            row=int(value["row"]),
            frames=int(value["frames"]),
            source=(
                _resolve_path(manifest_path, source_value)
                if source_value
                else None
            ),
            frame_sources=tuple(
                _resolve_path(manifest_path, source)
                for source in value.get("frame_sources", [])
            ),
            frame_source_scales=tuple(
                float(scale)
                for scale in value.get("frame_source_scales", [])
            ),
            frame_baseline_offsets=tuple(
                int(offset)
                for offset in value.get("frame_baseline_offsets", [])
            ),
            mirror_of=value.get("mirror_of"),
            scale_reference=value.get("scale_reference"),
            first_frame_from=value.get("first_frame_from"),
            target_first_frame_height=int(
                value.get("target_first_frame_height", 398)
            ),
            baseline=int(value.get("baseline", default_baseline)),
            max_width_ratio=float(value.get("max_width_ratio", 0.9)),
            target_head_width=(
                int(value["target_head_width"])
                if "target_head_width" in value
                else None
            ),
            scale_by_largest_component=bool(
                value.get("scale_by_largest_component", False)
            ),
            preserve_detached_effects=bool(
                value.get("preserve_detached_effects", False)
            ),
            max_detached_effects=(
                int(value["max_detached_effects"])
                if "max_detached_effects" in value
                else None
            ),
            detached_effect_min_area=int(
                value.get("detached_effect_min_area", 8)
            ),
        )
    return cell_size, columns, rows, specs


def build_assets_from_manifest(
    manifest_path: Path,
    output_path: Path,
) -> None:
    cell_size, columns, rows, specs = _load_manifest(manifest_path)
    atlas = Image.new(
        "RGBA",
        (columns * cell_size[0], rows * cell_size[1]),
    )
    generated: dict[str, list[Image.Image]] = {}
    subjects_by_state: dict[str, list[Image.Image]] = {}

    for name, spec in specs.items():
        if spec.frame_sources:
            if len(spec.frame_sources) != spec.frames:
                raise ValueError(
                    f"{name} has {len(spec.frame_sources)} frame sources, "
                    f"expected {spec.frames}"
                )
            if spec.frame_source_scales and (
                len(spec.frame_source_scales) != spec.frames
            ):
                raise ValueError(
                    f"{name} has {len(spec.frame_source_scales)} frame "
                    f"source scales, expected {spec.frames}"
                )
            if spec.frame_baseline_offsets and (
                len(spec.frame_baseline_offsets) != spec.frames
            ):
                raise ValueError(
                    f"{name} has {len(spec.frame_baseline_offsets)} frame "
                    f"baseline offsets, expected {spec.frames}"
                )
            subjects = []
            for source in spec.frame_sources:
                with Image.open(source) as image:
                    rgba = image.convert("RGBA")
                bounds = rgba.getchannel("A").getbbox()
                if bounds is None:
                    raise ValueError(f"{name} has an empty frame source")
                subjects.append(rgba.crop(bounds))
            subjects_by_state[name] = subjects
        elif spec.source is not None:
            with Image.open(spec.source) as image:
                subjects_by_state[name] = _split_subjects(
                    image.convert("RGBA"),
                    spec.frames,
                )

    for name, spec in specs.items():
        if spec.mirror_of:
            source_frames = generated.get(spec.mirror_of)
            if source_frames is None:
                raise ValueError(
                    f"{name} mirrors unavailable state {spec.mirror_of}"
                )
            frames = [
                frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                for frame in source_frames
            ]
        else:
            subjects = subjects_by_state.get(name)
            if subjects is None:
                raise ValueError(f"{name} has no source strip")
            reference_height = None
            if spec.scale_reference:
                reference_subjects = subjects_by_state.get(spec.scale_reference)
                if reference_subjects is None:
                    raise ValueError(
                        f"{name} has unavailable scale reference "
                        f"{spec.scale_reference}"
                    )
                reference_height = reference_subjects[0].height
            frames = _render_subjects(
                subjects,
                cell_size,
                spec.target_first_frame_height,
                baseline=spec.baseline,
                max_width_ratio=spec.max_width_ratio,
                scale_reference_height=reference_height,
                subject_scales=(
                    list(spec.frame_source_scales)
                    if spec.frame_source_scales
                    else None
                ),
                baseline_offsets=(
                    list(spec.frame_baseline_offsets)
                    if spec.frame_baseline_offsets
                    else None
                ),
                target_head_width=spec.target_head_width,
                scale_by_largest_component=spec.scale_by_largest_component,
                preserve_detached_effects=spec.preserve_detached_effects,
                max_detached_effects=spec.max_detached_effects,
                detached_effect_min_area=spec.detached_effect_min_area,
            )
        if spec.first_frame_from:
            reference_frames = generated.get(spec.first_frame_from)
            if reference_frames is None:
                raise ValueError(
                    f"{name} has unavailable first-frame source "
                    f"{spec.first_frame_from}"
                )
            frames[0] = reference_frames[0].copy()
        if len(frames) != spec.frames:
            raise ValueError(f"{name} produced the wrong frame count")
        generated[name] = frames
        _replace_row(atlas, spec.row, frames, cell_size)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".tmp.webp")
    _normalize_transparent_pixels(atlas).save(
        temporary,
        format="WEBP",
        lossless=True,
        method=6,
    )
    shutil.move(temporary, output_path)


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

    for index in range(8):
        atlas.paste(
            Image.new("RGBA", cell_size),
            (
                index * cell_size[0],
                int(states["walking-right"]["row"]) * cell_size[1],
            ),
        )
        atlas.paste(
            Image.new("RGBA", cell_size),
            (
                index * cell_size[0],
                int(states["walking-left"]["row"]) * cell_size[1],
            ),
        )
        atlas.paste(
            Image.new("RGBA", cell_size),
            (
                index * cell_size[0],
                int(states["sitting"]["row"]) * cell_size[1],
            ),
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

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = output_path.with_suffix(".tmp.webp")
    _normalize_transparent_pixels(atlas).save(
        temporary,
        format="WEBP",
        lossless=True,
        method=6,
    )
    shutil.move(temporary, output_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--animation", type=Path)
    parser.add_argument("--atlas", type=Path)
    parser.add_argument("--walking-strip", type=Path)
    parser.add_argument("--sitting-strip", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.manifest:
        build_assets_from_manifest(args.manifest.resolve(), args.output)
        return 0
    legacy = (
        args.animation,
        args.atlas,
        args.walking_strip,
        args.sitting_strip,
    )
    if any(value is None for value in legacy):
        parser.error(
            "--manifest or all legacy animation/atlas/strip arguments are required"
        )
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
