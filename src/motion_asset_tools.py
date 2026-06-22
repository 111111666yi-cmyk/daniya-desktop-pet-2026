from __future__ import annotations

from array import array
from collections import deque
import importlib
import io
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageChops, ImageColor, ImageDraw, ImageOps


DEFAULT_CANVAS_SIZE = 1024
DEFAULT_KEY_COLOR = "#00ff00"


@dataclass(frozen=True)
class FrameMetadata:
    frame: str
    alpha_bbox: tuple[int, int, int, int]
    anchor_track: dict[str, list[float]]
    source_size: tuple[int, int] | None = None
    source_alpha_bbox: tuple[int, int, int, int] | None = None
    source_anchor_track: dict[str, list[float]] | None = None


@dataclass(frozen=True)
class AnchorStabilityReport:
    frame_count: int
    root_jitter_px: float
    foot_left_jitter_px: float
    foot_right_jitter_px: float
    baseline_jitter_px: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            "frame_count": self.frame_count,
            "root_jitter_px": round(self.root_jitter_px, 3),
            "foot_left_jitter_px": round(self.foot_left_jitter_px, 3),
            "foot_right_jitter_px": round(self.foot_right_jitter_px, 3),
            "baseline_jitter_px": round(self.baseline_jitter_px, 3),
        }


@dataclass(frozen=True)
class FrameDeltaReport:
    pair_count: int
    mean_alpha_delta_ratio: float
    min_alpha_delta_ratio: float
    max_alpha_delta_ratio: float
    mean_rgba_delta_ratio: float

    def to_dict(self) -> dict[str, float | int]:
        return {
            "pair_count": self.pair_count,
            "mean_alpha_delta_ratio": round(self.mean_alpha_delta_ratio, 6),
            "min_alpha_delta_ratio": round(self.min_alpha_delta_ratio, 6),
            "max_alpha_delta_ratio": round(self.max_alpha_delta_ratio, 6),
            "mean_rgba_delta_ratio": round(self.mean_rgba_delta_ratio, 6),
        }


@dataclass(frozen=True)
class AlphaComponent:
    area: int
    bbox: tuple[int, int, int, int]
    touches: dict[str, bool]


def aggregate_anchor_track(metadata: Iterable[FrameMetadata]) -> dict[str, list[float]]:
    totals: dict[str, list[float]] = {}
    counts: dict[str, int] = {}
    for item in metadata:
        for name, coords in item.anchor_track.items():
            if name not in totals:
                totals[name] = [0.0, 0.0]
                counts[name] = 0
            totals[name][0] += float(coords[0])
            totals[name][1] += float(coords[1])
            counts[name] += 1
    return {
        name: [
            round(values[0] / max(1, counts[name]), 4),
            round(values[1] / max(1, counts[name]), 4),
        ]
        for name, values in totals.items()
    }


def parse_hex_color(value: str) -> tuple[int, int, int]:
    red, green, blue = ImageColor.getrgb(value)
    return int(red), int(green), int(blue)


def slice_sheet(
    sheet_path: Path,
    *,
    grid_cols: int,
    grid_rows: int,
    frame_prefix: str,
    start_index: int = 1,
    cell_inset_percent: float = 0.0,
) -> list[tuple[str, Image.Image]]:
    image = Image.open(sheet_path).convert("RGBA")
    cell_width = image.width // max(1, grid_cols)
    cell_height = image.height // max(1, grid_rows)
    inset_x = max(0, int(round(cell_width * max(0.0, cell_inset_percent))))
    inset_y = max(0, int(round(cell_height * max(0.0, cell_inset_percent))))
    if inset_x * 2 >= cell_width or inset_y * 2 >= cell_height:
        raise ValueError("cell inset is too large for the selected grid")
    frames: list[tuple[str, Image.Image]] = []
    index = start_index
    for row in range(grid_rows):
        for col in range(grid_cols):
            left = col * cell_width
            top = row * cell_height
            cell = image.crop(
                (
                    left + inset_x,
                    top + inset_y,
                    left + cell_width - inset_x,
                    top + cell_height - inset_y,
                )
            )
            frames.append((f"{frame_prefix}_{index:02d}.png", cell))
            index += 1
    return frames


def collect_source_frames(
    source: Path,
    *,
    grid_cols: int | None = None,
    grid_rows: int | None = None,
    frame_prefix: str = "frame",
    start_index: int = 1,
    cell_inset_percent: float = 0.0,
) -> list[tuple[str, Image.Image]]:
    if source.is_dir():
        return [(path.name, Image.open(path).convert("RGBA")) for path in sorted(source.iterdir()) if path.suffix.lower() == ".png"]
    if source.is_file():
        if not grid_cols or not grid_rows:
            raise ValueError("sheet input requires --grid-cols and --grid-rows")
        return slice_sheet(
            source,
            grid_cols=grid_cols,
            grid_rows=grid_rows,
            frame_prefix=frame_prefix,
            start_index=start_index,
            cell_inset_percent=cell_inset_percent,
        )
    raise FileNotFoundError(source)


def prepare_source_frame(
    image: Image.Image,
    *,
    matting_backend: str = "chroma",
    key_color: tuple[int, int, int] | None = None,
    transparent_threshold: int = 16,
    opaque_threshold: int = 96,
    despill: bool = True,
    alpha_floor: int = 0,
) -> Image.Image:
    if matting_backend == "none":
        prepared = image.convert("RGBA")
    elif matting_backend == "chroma":
        if key_color is None:
            prepared = image.convert("RGBA")
        else:
            prepared = remove_chroma_key(
                image,
                key_color=key_color,
                transparent_threshold=transparent_threshold,
                opaque_threshold=opaque_threshold,
                despill=despill,
                alpha_floor=0,
            )
    elif matting_backend == "rembg":
        prepared = remove_background_with_rembg(image)
    else:
        raise ValueError(f"unsupported matting backend: {matting_backend}")
    return apply_alpha_floor(prepared, alpha_floor=alpha_floor)


def remove_background_with_rembg(image: Image.Image) -> Image.Image:
    try:
        rembg = importlib.import_module("rembg")
    except ImportError as exc:
        raise RuntimeError(
            "rembg backend requested but the 'rembg' package is not installed in this environment"
        ) from exc

    result = rembg.remove(image.convert("RGBA"))
    if isinstance(result, Image.Image):
        return result.convert("RGBA")
    if isinstance(result, (bytes, bytearray)):
        return Image.open(io.BytesIO(result)).convert("RGBA")
    raise TypeError(f"unsupported rembg result type: {type(result)!r}")


def apply_alpha_floor(image: Image.Image, *, alpha_floor: int = 0) -> Image.Image:
    rgba = image.convert("RGBA")
    if alpha_floor <= 0:
        return rgba
    pixels = rgba.load()
    for y in range(rgba.height):
        for x in range(rgba.width):
            red, green, blue, alpha = pixels[x, y]
            if alpha < alpha_floor:
                pixels[x, y] = (red, green, blue, 0)
    return rgba


def remove_chroma_key(
    image: Image.Image,
    *,
    key_color: tuple[int, int, int],
    transparent_threshold: int = 16,
    opaque_threshold: int = 96,
    despill: bool = True,
    alpha_floor: int = 0,
) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    key_r, key_g, key_b = key_color
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            distance = math.sqrt((red - key_r) ** 2 + (green - key_g) ** 2 + (blue - key_b) ** 2)
            if distance <= transparent_threshold:
                pixels[x, y] = (red, green, blue, 0)
                continue
            if distance < opaque_threshold:
                blend = (distance - transparent_threshold) / max(1.0, opaque_threshold - transparent_threshold)
                alpha = int(alpha * blend)
            if alpha_floor > 0 and alpha < alpha_floor:
                alpha = 0
            if despill and alpha < 255 and green > max(red, blue):
                green = int((green + max(red, blue)) / 2)
            pixels[x, y] = (red, green, blue, alpha)
    return rgba


def cleanup_disconnected_alpha_islands(
    image: Image.Image,
    *,
    alpha_threshold: int = 24,
    min_component_area: int = 96,
    near_margin_px: int = 64,
) -> Image.Image:
    rgba = image.convert("RGBA")
    width, height = rgba.size
    if width <= 0 or height <= 0:
        return rgba

    alpha = rgba.getchannel("A")
    alpha_data = alpha.load()
    labels = array("I", [0]) * (width * height)
    components: dict[int, AlphaComponent] = {}
    label = 0
    main_label = 0
    main_area = 0

    for y in range(height):
        row_offset = y * width
        for x in range(width):
            idx = row_offset + x
            if labels[idx] != 0 or alpha_data[x, y] < alpha_threshold:
                continue

            label += 1
            queue: deque[tuple[int, int]] = deque([(x, y)])
            labels[idx] = label
            area = 0
            min_x = max_x = x
            min_y = max_y = y

            while queue:
                cx, cy = queue.popleft()
                area += 1
                if cx < min_x:
                    min_x = cx
                if cx > max_x:
                    max_x = cx
                if cy < min_y:
                    min_y = cy
                if cy > max_y:
                    max_y = cy

                for nx in range(max(0, cx - 1), min(width - 1, cx + 1) + 1):
                    for ny in range(max(0, cy - 1), min(height - 1, cy + 1) + 1):
                        nidx = ny * width + nx
                        if labels[nidx] != 0 or alpha_data[nx, ny] < alpha_threshold:
                            continue
                        labels[nidx] = label
                        queue.append((nx, ny))

            bbox = (min_x, min_y, max_x, max_y)
            components[label] = AlphaComponent(
                area=area,
                bbox=bbox,
                touches={
                    "left": min_x == 0,
                    "right": max_x == width - 1,
                    "top": min_y == 0,
                    "bottom": max_y == height - 1,
                },
            )
            if area > main_area:
                main_label = label
                main_area = area

    if main_label == 0:
        return rgba

    main_component = components[main_label]
    keep_box = _expand_bbox(main_component.bbox, margin=near_margin_px, width=width, height=height)
    keep_labels = {main_label}
    for component_label, component in components.items():
        if component_label == main_label:
            continue
        if _touches_unshared_edge(component.touches, main_component.touches):
            continue
        if component.area >= min_component_area and _bboxes_intersect(keep_box, component.bbox):
            keep_labels.add(component_label)

    pixels = rgba.load()
    for y in range(height):
        row_offset = y * width
        for x in range(width):
            component_label = labels[row_offset + x]
            if component_label != 0 and component_label not in keep_labels:
                red, green, blue, _alpha = pixels[x, y]
                pixels[x, y] = (red, green, blue, 0)
    return rgba


def _expand_bbox(
    bbox: tuple[int, int, int, int],
    *,
    margin: int,
    width: int,
    height: int,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = bbox
    return (
        max(0, left - margin),
        max(0, top - margin),
        min(width - 1, right + margin),
        min(height - 1, bottom + margin),
    )


def _bboxes_intersect(
    left: tuple[int, int, int, int],
    right: tuple[int, int, int, int],
) -> bool:
    return not (
        left[2] < right[0]
        or right[2] < left[0]
        or left[3] < right[1]
        or right[3] < left[1]
    )


def _touches_unshared_edge(
    component_touches: dict[str, bool],
    main_touches: dict[str, bool],
) -> bool:
    return any(component_touches[edge] and not main_touches[edge] for edge in component_touches)


def pad_frame_to_size(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    if image.size == size:
        return image.copy()
    canvas = Image.new("RGBA", size, (0, 0, 0, 0))
    x = (size[0] - image.width) // 2
    y = (size[1] - image.height) // 2
    canvas.alpha_composite(image.convert("RGBA"), (x, y))
    return canvas


def resample_frames(
    frames: Iterable[tuple[str, Image.Image]],
    *,
    target_frame_count: int,
    frame_prefix: str = "frame",
    start_index: int = 1,
    loop: bool = True,
    mode: str = "blend",
) -> list[tuple[str, Image.Image]]:
    source_frames = [(name, image.convert("RGBA")) for name, image in frames]
    if not source_frames:
        raise ValueError("cannot resample an empty frame sequence")
    if target_frame_count <= 0:
        raise ValueError("target_frame_count must be positive")
    if mode not in {"blend", "hold"}:
        raise ValueError(f"unsupported resample mode: {mode}")

    size = (
        max(image.width for _, image in source_frames),
        max(image.height for _, image in source_frames),
    )
    padded_frames = [(name, pad_frame_to_size(image, size)) for name, image in source_frames]
    source_count = len(padded_frames)
    if target_frame_count == source_count:
        return [
            (f"{frame_prefix}_{index:02d}.png", image.copy())
            for index, (_, image) in enumerate(padded_frames, start=start_index)
        ]

    positions: list[float] = []
    if loop:
        step = source_count / target_frame_count
        positions = [index * step for index in range(target_frame_count)]
    elif target_frame_count == 1:
        positions = [0.0]
    else:
        last_index = max(0, source_count - 1)
        step = last_index / max(1, target_frame_count - 1)
        positions = [index * step for index in range(target_frame_count)]

    resampled: list[tuple[str, Image.Image]] = []
    for output_index, position in enumerate(positions, start=start_index):
        left_index = int(math.floor(position))
        fraction = position - left_index
        if loop:
            left_index %= source_count
            right_index = (left_index + 1) % source_count
        else:
            left_index = max(0, min(left_index, source_count - 1))
            right_index = min(left_index + 1, source_count - 1)
        left_image = padded_frames[left_index][1]
        if mode == "hold" or fraction <= 1e-6 or left_index == right_index:
            frame_image = left_image.copy()
        else:
            right_image = padded_frames[right_index][1]
            frame_image = Image.blend(left_image, right_image, fraction)
        resampled.append((f"{frame_prefix}_{output_index:02d}.png", frame_image))
    return resampled


def estimate_anchor(image: Image.Image) -> dict[str, list[float]]:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        return {
            "root": [0.5, 0.88],
            "foot_left": [0.42, 0.98],
            "foot_right": [0.58, 0.98],
            "hips": [0.5, 0.66],
            "drag_handle": [0.5, 0.18],
        }
    left, top, right, bottom = bbox
    width = max(1, image.width)
    height = max(1, image.height)
    mid_x = (left + right) / 2 / width
    return {
        "root": [round(mid_x, 4), round(max(0.0, min(1.0, bottom / height - 0.1)), 4)],
        "foot_left": [round(max(0.0, left / width), 4), round(bottom / height, 4)],
        "foot_right": [round(min(1.0, right / width), 4), round(bottom / height, 4)],
        "hips": [round(mid_x, 4), round(max(0.0, min(1.0, (top + bottom * 0.58) / height)), 4)],
        "drag_handle": [round(mid_x, 4), round(max(0.0, top / height), 4)],
    }


def normalize_frame_image(image: Image.Image, *, canvas_size: int = DEFAULT_CANVAS_SIZE) -> tuple[Image.Image, tuple[int, int, int, int], dict[str, list[float]]]:
    alpha = image.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        bbox = (0, 0, image.width, image.height)
    cropped = image.crop(bbox)
    contained = ImageOps.contain(cropped, (canvas_size, canvas_size), method=Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    x = (canvas_size - contained.width) // 2
    y = canvas_size - contained.height
    canvas.alpha_composite(contained, (x, y))
    return canvas, tuple(int(v) for v in bbox), estimate_anchor(canvas)


def build_motion_assets(
    source: Path,
    output_dir: Path,
    *,
    canvas_size: int = DEFAULT_CANVAS_SIZE,
    grid_cols: int | None = None,
    grid_rows: int | None = None,
    frame_prefix: str = "frame",
    start_index: int = 1,
    cell_inset_percent: float = 0.0,
    matting_backend: str = "chroma",
    chroma_key: str | None = None,
    transparent_threshold: int = 16,
    opaque_threshold: int = 96,
    despill: bool = True,
    alpha_floor: int = 0,
    cleanup_islands: bool = False,
    cleanup_alpha_threshold: int = 24,
    cleanup_min_component_area: int = 96,
    cleanup_near_margin_px: int = 64,
    target_frame_count: int | None = None,
    resample_mode: str = "blend",
    loop_for_resample: bool = True,
) -> tuple[list[Path], list[FrameMetadata]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    key_color = parse_hex_color(chroma_key or DEFAULT_KEY_COLOR) if chroma_key else None
    def _prepare(image: Image.Image) -> Image.Image:
        return prepare_source_frame(
            image,
            matting_backend=matting_backend,
            key_color=key_color,
            transparent_threshold=transparent_threshold,
            opaque_threshold=opaque_threshold,
            despill=despill,
            alpha_floor=alpha_floor,
        )
    prepared_frames = [
        (
            frame_name,
            (
                cleanup_disconnected_alpha_islands(
                    _prepare(image),
                    alpha_threshold=cleanup_alpha_threshold,
                    min_component_area=cleanup_min_component_area,
                    near_margin_px=cleanup_near_margin_px,
                )
                if cleanup_islands
                else _prepare(image)
            ),
        )
        for frame_name, image in collect_source_frames(
            source,
            grid_cols=grid_cols,
            grid_rows=grid_rows,
            frame_prefix=frame_prefix,
            start_index=start_index,
            cell_inset_percent=cell_inset_percent,
        )
    ]
    if target_frame_count is not None:
        prepared_frames = resample_frames(
            prepared_frames,
            target_frame_count=target_frame_count,
            frame_prefix=frame_prefix,
            start_index=start_index,
            loop=loop_for_resample,
            mode=resample_mode,
        )
    normalized_paths: list[Path] = []
    metadata: list[FrameMetadata] = []
    for frame_name, prepared in prepared_frames:
        source_alpha = prepared.getchannel("A").getbbox()
        source_bbox = tuple(int(v) for v in (source_alpha or (0, 0, prepared.width, prepared.height)))
        source_anchors = estimate_anchor(prepared)
        normalized, bbox, anchors = normalize_frame_image(prepared, canvas_size=canvas_size)
        output_path = output_dir / frame_name
        normalized.save(output_path)
        normalized_paths.append(output_path)
        metadata.append(
            FrameMetadata(
                frame=frame_name,
                alpha_bbox=bbox,
                anchor_track=anchors,
                source_size=(prepared.width, prepared.height),
                source_alpha_bbox=source_bbox,
                source_anchor_track=source_anchors,
            )
        )
    return normalized_paths, metadata


def write_contact_sheet(frame_paths: Iterable[Path], output_path: Path, *, cell_size: int = 256) -> None:
    images = [Image.open(path).convert("RGBA") for path in frame_paths]
    cols = min(4, max(1, len(images)))
    rows = (len(images) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell_size, rows * cell_size), (236, 236, 236, 255))
    draw = ImageDraw.Draw(sheet)
    for index, (path, image) in enumerate(zip(frame_paths, images)):
        preview = ImageOps.contain(image, (cell_size - 16, cell_size - 32), method=Image.Resampling.LANCZOS)
        x = (index % cols) * cell_size + (cell_size - preview.width) // 2
        y = (index // cols) * cell_size + 8
        sheet.alpha_composite(preview, (x, y))
        draw.text(
            ((index % cols) * cell_size + 8, (index // cols) * cell_size + cell_size - 20),
            Path(path).stem,
            fill=(18, 18, 18, 255),
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


def render_preview_gif(frame_paths: Iterable[Path], output_path: Path, *, duration_ms: int = 90, scale_to: int = 256) -> None:
    frames = []
    for path in frame_paths:
        image = Image.open(path).convert("RGBA")
        preview = ImageOps.contain(image, (scale_to, scale_to), method=Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (scale_to, scale_to), (0, 0, 0, 0))
        x = (scale_to - preview.width) // 2
        y = scale_to - preview.height
        canvas.alpha_composite(preview, (x, y))
        frames.append(canvas)
    if not frames:
        raise ValueError("no frames for preview gif")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
        transparency=0,
    )


def anchor_stability_report(frame_paths: Iterable[Path]) -> AnchorStabilityReport:
    roots: list[float] = []
    feet_left: list[float] = []
    feet_right: list[float] = []
    baselines: list[int] = []
    frame_count = 0
    for path in frame_paths:
        image = Image.open(path).convert("RGBA")
        anchors = estimate_anchor(image)
        roots.append(anchors["root"][1] * image.height)
        feet_left.append(anchors["foot_left"][1] * image.height)
        feet_right.append(anchors["foot_right"][1] * image.height)
        alpha = image.getchannel("A")
        bbox = alpha.getbbox()
        baselines.append((bbox[3] if bbox else image.height))
        frame_count += 1

    def _spread(values: list[float | int]) -> float:
        if not values:
            return 0.0
        return float(max(values) - min(values))

    return AnchorStabilityReport(
        frame_count=frame_count,
        root_jitter_px=_spread(roots),
        foot_left_jitter_px=_spread(feet_left),
        foot_right_jitter_px=_spread(feet_right),
        baseline_jitter_px=_spread(baselines),
    )


def frame_delta_report(
    frame_paths: Iterable[Path],
    *,
    loop: bool = True,
    alpha_threshold: int = 12,
    rgba_threshold: int = 20,
) -> FrameDeltaReport:
    images = [Image.open(path).convert("RGBA") for path in frame_paths]
    if len(images) < 2:
        return FrameDeltaReport(
            pair_count=0,
            mean_alpha_delta_ratio=0.0,
            min_alpha_delta_ratio=0.0,
            max_alpha_delta_ratio=0.0,
            mean_rgba_delta_ratio=0.0,
        )

    pairs = list(zip(images, images[1:]))
    if loop:
        pairs.append((images[-1], images[0]))

    alpha_ratios: list[float] = []
    rgba_ratios: list[float] = []
    for left, right in pairs:
        total_pixels = max(1, left.width * left.height)

        alpha_diff = ImageChops.difference(left.getchannel("A"), right.getchannel("A"))
        alpha_hist = alpha_diff.histogram()
        alpha_changed = sum(alpha_hist[alpha_threshold:])

        rgba_diff = ImageChops.difference(left, right).convert("RGB")
        red, green, blue = rgba_diff.split()
        rgb_max = ImageChops.lighter(ImageChops.lighter(red, green), blue)
        rgba_hist = rgb_max.histogram()
        rgba_changed = sum(rgba_hist[rgba_threshold:])

        alpha_ratios.append(alpha_changed / total_pixels)
        rgba_ratios.append(rgba_changed / total_pixels)

    return FrameDeltaReport(
        pair_count=len(pairs),
        mean_alpha_delta_ratio=sum(alpha_ratios) / len(alpha_ratios),
        min_alpha_delta_ratio=min(alpha_ratios),
        max_alpha_delta_ratio=max(alpha_ratios),
        mean_rgba_delta_ratio=sum(rgba_ratios) / len(rgba_ratios),
    )


def anchor_stability_report_from_metadata(
    metadata: Iterable[FrameMetadata],
    *,
    source_space: bool = False,
) -> AnchorStabilityReport:
    roots: list[float] = []
    feet_left: list[float] = []
    feet_right: list[float] = []
    baselines: list[int] = []
    frame_count = 0
    for item in metadata:
        if source_space and item.source_anchor_track and item.source_size and item.source_alpha_bbox:
            anchors = item.source_anchor_track
            height = item.source_size[1]
            baseline = item.source_alpha_bbox[3]
        else:
            anchors = item.anchor_track
            height = DEFAULT_CANVAS_SIZE
            baseline = item.alpha_bbox[3]
        roots.append(float(anchors["root"][1]) * height)
        feet_left.append(float(anchors["foot_left"][1]) * height)
        feet_right.append(float(anchors["foot_right"][1]) * height)
        baselines.append(int(baseline))
        frame_count += 1

    def _spread(values: list[float | int]) -> float:
        if not values:
            return 0.0
        return float(max(values) - min(values))

    return AnchorStabilityReport(
        frame_count=frame_count,
        root_jitter_px=_spread(roots),
        foot_left_jitter_px=_spread(feet_left),
        foot_right_jitter_px=_spread(feet_right),
        baseline_jitter_px=_spread(baselines),
    )


def write_manifest_fragment(
    output_path: Path,
    frame_paths: Iterable[Path],
    metadata: Iterable[FrameMetadata],
) -> None:
    fragment = {
        "frames": [Path(path).name for path in frame_paths],
        "anchors": [
            {
                "frame": item.frame,
                "alpha_bbox": list(item.alpha_bbox),
                "anchor_track": item.anchor_track,
                "source_size": list(item.source_size) if item.source_size else None,
                "source_alpha_bbox": list(item.source_alpha_bbox) if item.source_alpha_bbox else None,
                "source_anchor_track": item.source_anchor_track,
            }
            for item in metadata
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(fragment, ensure_ascii=False, indent=2), encoding="utf-8")


def build_catalog_fragment(
    clip_id: str,
    frame_paths: Iterable[str | Path],
    metadata: Iterable[FrameMetadata],
    *,
    kind: str = "sprite_sequence",
    frame_duration_ms: int = 90,
    loop: bool = True,
    state_id: str | None = None,
    state_priority: int = 30,
    state_min_hold_ms: int = 0,
    fallback_state: str | None = None,
    transition_in: str | None = None,
    transition_out: str | None = None,
    cycle_distance_px: float | None = None,
    min_speed_px_s: float | None = None,
    max_speed_px_s: float | None = None,
    renderer_binding: dict[str, str] | None = None,
) -> dict[str, dict[str, dict[str, object]]]:
    normalized_paths = [Path(path).as_posix() for path in frame_paths]
    clip: dict[str, object] = {
        "kind": kind,
        "frames": normalized_paths,
        "frame_duration_ms": int(frame_duration_ms),
        "loop": bool(loop),
        "anchor_track": aggregate_anchor_track(metadata),
    }
    if transition_in:
        clip["transition_in"] = transition_in
    if transition_out:
        clip["transition_out"] = transition_out
    if cycle_distance_px is not None:
        clip["locomotion_profile"] = {
            "cycle_distance_px": float(cycle_distance_px),
            "min_speed_px_s": float(min_speed_px_s if min_speed_px_s is not None else 48.0),
            "max_speed_px_s": float(max_speed_px_s if max_speed_px_s is not None else 96.0),
        }

    fragment: dict[str, dict[str, dict[str, object]]] = {
        "clips": {
            clip_id: clip,
        }
    }

    if state_id:
        state: dict[str, object] = {
            "clip": clip_id,
            "loop": bool(loop),
            "min_hold_ms": int(state_min_hold_ms),
            "priority": int(state_priority),
        }
        if fallback_state:
            state["fallback_state"] = fallback_state
        if renderer_binding:
            state["renderer_binding"] = dict(renderer_binding)
        fragment["states"] = {
            state_id: state,
        }

    return fragment


def write_catalog_fragment(
    output_path: Path,
    clip_id: str,
    frame_paths: Iterable[str | Path],
    metadata: Iterable[FrameMetadata],
    *,
    kind: str = "sprite_sequence",
    frame_duration_ms: int = 90,
    loop: bool = True,
    state_id: str | None = None,
    state_priority: int = 30,
    state_min_hold_ms: int = 0,
    fallback_state: str | None = None,
    transition_in: str | None = None,
    transition_out: str | None = None,
    cycle_distance_px: float | None = None,
    min_speed_px_s: float | None = None,
    max_speed_px_s: float | None = None,
    renderer_binding: dict[str, str] | None = None,
) -> dict[str, dict[str, dict[str, object]]]:
    fragment = build_catalog_fragment(
        clip_id,
        frame_paths,
        metadata,
        kind=kind,
        frame_duration_ms=frame_duration_ms,
        loop=loop,
        state_id=state_id,
        state_priority=state_priority,
        state_min_hold_ms=state_min_hold_ms,
        fallback_state=fallback_state,
        transition_in=transition_in,
        transition_out=transition_out,
        cycle_distance_px=cycle_distance_px,
        min_speed_px_s=min_speed_px_s,
        max_speed_px_s=max_speed_px_s,
        renderer_binding=renderer_binding,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(fragment, ensure_ascii=False, indent=2), encoding="utf-8")
    return fragment
