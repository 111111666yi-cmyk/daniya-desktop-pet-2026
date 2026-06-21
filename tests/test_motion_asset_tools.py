from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from src.motion_asset_tools import (
    FrameMetadata,
    anchor_stability_report,
    anchor_stability_report_from_metadata,
    build_catalog_fragment,
    build_motion_assets,
    cleanup_disconnected_alpha_islands,
    frame_delta_report,
    prepare_source_frame,
    resample_frames,
    slice_sheet,
)


def test_build_motion_assets_slices_sheet_and_removes_chroma_key(tmp_path: Path) -> None:
    sheet = Image.new("RGBA", (200, 100), (0, 255, 0, 255))
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((20, 20, 80, 90), fill=(255, 0, 0, 255))
    draw.rectangle((120, 10, 180, 80), fill=(0, 0, 255, 255))
    sheet_path = tmp_path / "walk_sheet.png"
    sheet.save(sheet_path)

    output_dir = tmp_path / "frames"
    paths, metadata = build_motion_assets(
        sheet_path,
        output_dir,
        canvas_size=256,
        grid_cols=2,
        grid_rows=1,
        frame_prefix="walk",
        chroma_key="#00ff00",
    )

    assert [path.name for path in paths] == ["walk_01.png", "walk_02.png"]
    assert len(metadata) == 2
    first = Image.open(paths[0]).convert("RGBA")
    assert first.getpixel((0, 0))[3] == 0
    assert first.getbbox() is not None


def test_slice_sheet_can_inset_cells_to_drop_boundary_bleed(tmp_path: Path) -> None:
    sheet = Image.new("RGBA", (200, 100), (0, 255, 0, 255))
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((120, 20, 180, 90), fill=(255, 0, 0, 255))
    draw.rectangle((100, 0, 140, 8), fill=(0, 0, 255, 255))
    sheet_path = tmp_path / "walk_sheet.png"
    sheet.save(sheet_path)

    frames = slice_sheet(
        sheet_path,
        grid_cols=2,
        grid_rows=1,
        frame_prefix="walk",
        cell_inset_percent=0.1,
    )

    second = frames[1][1]
    assert second.getpixel((20, 5))[:3] == (0, 255, 0)
    assert second.getpixel((40, 30))[:3] == (255, 0, 0)


def test_cleanup_disconnected_alpha_islands_removes_far_fragments_and_keeps_nearby_detail() -> None:
    image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((36, 24, 88, 108), fill=(255, 0, 0, 255))
    draw.rectangle((92, 52, 104, 72), fill=(255, 255, 0, 255))
    draw.rectangle((0, 0, 12, 12), fill=(0, 0, 255, 255))

    cleaned = cleanup_disconnected_alpha_islands(
        image,
        alpha_threshold=24,
        min_component_area=64,
        near_margin_px=12,
    )

    assert cleaned.getpixel((6, 6))[3] == 0
    assert cleaned.getpixel((48, 48))[3] == 255
    assert cleaned.getpixel((96, 60))[3] == 255


def test_cleanup_disconnected_alpha_islands_drops_border_bleed_without_cropping_main_body() -> None:
    image = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((28, 18, 92, 127), fill=(255, 0, 0, 255))
    draw.rectangle((50, 0, 82, 14), fill=(0, 0, 255, 255))
    draw.rectangle((94, 54, 108, 74), fill=(255, 255, 0, 255))

    cleaned = cleanup_disconnected_alpha_islands(
        image,
        alpha_threshold=24,
        min_component_area=64,
        near_margin_px=48,
    )

    assert cleaned.getpixel((64, 6))[3] == 0
    assert cleaned.getpixel((64, 96))[3] == 255
    assert cleaned.getpixel((100, 60))[3] == 255


def test_prepare_source_frame_can_zero_low_alpha_haze() -> None:
    image = Image.new("RGBA", (2, 1), (0, 255, 0, 255))
    image.putpixel((1, 0), (0, 235, 0, 255))

    prepared = prepare_source_frame(
        image,
        key_color=(0, 255, 0),
        transparent_threshold=16,
        opaque_threshold=96,
        alpha_floor=24,
    )

    assert prepared.getpixel((0, 0))[3] == 0
    assert prepared.getpixel((1, 0))[3] == 0


def test_anchor_stability_report_detects_baseline_shift(tmp_path: Path) -> None:
    first = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    second = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
    draw_first = ImageDraw.Draw(first)
    draw_second = ImageDraw.Draw(second)
    draw_first.rectangle((40, 30, 88, 120), fill=(255, 255, 255, 255))
    draw_second.rectangle((40, 20, 88, 110), fill=(255, 255, 255, 255))
    path_a = tmp_path / "a.png"
    path_b = tmp_path / "b.png"
    first.save(path_a)
    second.save(path_b)

    report = anchor_stability_report([path_a, path_b])

    assert report.frame_count == 2
    assert report.baseline_jitter_px > 0


def test_build_catalog_fragment_uses_relative_frames_and_mean_anchor_track() -> None:
    metadata = [
        FrameMetadata(
            frame="walk_01.png",
            alpha_bbox=(0, 0, 10, 10),
            anchor_track={
                "root": [0.5, 0.88],
                "foot_left": [0.4, 0.98],
                "foot_right": [0.6, 0.98],
            },
        ),
        FrameMetadata(
            frame="walk_02.png",
            alpha_bbox=(0, 0, 10, 10),
            anchor_track={
                "root": [0.52, 0.9],
                "foot_left": [0.42, 0.98],
                "foot_right": [0.62, 0.98],
            },
        ),
    ]

    fragment = build_catalog_fragment(
        "walk_loop_candidate",
        ["motion_rebuild/runtime/walk_loop_candidate/walk_01.png", "motion_rebuild/runtime/walk_loop_candidate/walk_02.png"],
        metadata,
        frame_duration_ms=60,
        loop=True,
        state_id="walking",
        state_priority=30,
        cycle_distance_px=64,
    )

    clip = fragment["clips"]["walk_loop_candidate"]
    assert clip["frames"] == [
        "motion_rebuild/runtime/walk_loop_candidate/walk_01.png",
        "motion_rebuild/runtime/walk_loop_candidate/walk_02.png",
    ]
    assert clip["anchor_track"]["root"] == [0.51, 0.89]
    assert clip["locomotion_profile"]["cycle_distance_px"] == 64.0
    assert fragment["states"]["walking"]["clip"] == "walk_loop_candidate"


def test_source_space_report_preserves_sheet_baseline_shift(tmp_path: Path) -> None:
    sheet = Image.new("RGBA", (200, 100), (0, 255, 0, 255))
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((20, 20, 80, 90), fill=(255, 0, 0, 255))
    draw.rectangle((120, 10, 180, 80), fill=(0, 0, 255, 255))
    sheet_path = tmp_path / "walk_sheet.png"
    sheet.save(sheet_path)

    output_dir = tmp_path / "frames"
    paths, metadata = build_motion_assets(
        sheet_path,
        output_dir,
        canvas_size=256,
        grid_cols=2,
        grid_rows=1,
        frame_prefix="walk",
        chroma_key="#00ff00",
    )

    source_report = anchor_stability_report_from_metadata(metadata, source_space=True)
    runtime_report = anchor_stability_report(paths)

    assert source_report.baseline_jitter_px > 0
    assert runtime_report.baseline_jitter_px == 0


def test_resample_frames_generates_blended_runtime_sequence() -> None:
    first = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    second = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw_first = ImageDraw.Draw(first)
    draw_second = ImageDraw.Draw(second)
    draw_first.rectangle((8, 8, 24, 24), fill=(255, 0, 0, 255))
    draw_second.rectangle((8, 8, 24, 24), fill=(0, 0, 255, 255))

    frames = resample_frames(
        [("a.png", first), ("b.png", second)],
        target_frame_count=4,
        frame_prefix="walk",
        loop=True,
        mode="blend",
    )

    assert [name for name, _ in frames] == [
        "walk_01.png",
        "walk_02.png",
        "walk_03.png",
        "walk_04.png",
    ]
    mid_pixel = frames[1][1].getpixel((16, 16))
    assert mid_pixel[0] > 0
    assert mid_pixel[2] > 0


def test_build_motion_assets_can_expand_non_loop_sequence(tmp_path: Path) -> None:
    frame_dir = tmp_path / "source_frames"
    frame_dir.mkdir()

    first = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    second = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw_first = ImageDraw.Draw(first)
    draw_second = ImageDraw.Draw(second)
    draw_first.rectangle((12, 12, 52, 52), fill=(255, 0, 0, 255))
    draw_second.rectangle((12, 12, 52, 52), fill=(0, 0, 255, 255))
    first.save(frame_dir / "pose_a.png")
    second.save(frame_dir / "pose_b.png")

    output_dir = tmp_path / "runtime_frames"
    paths, metadata = build_motion_assets(
        frame_dir,
        output_dir,
        canvas_size=128,
        frame_prefix="drag",
        target_frame_count=3,
        resample_mode="blend",
        loop_for_resample=False,
    )

    assert [path.name for path in paths] == ["drag_01.png", "drag_02.png", "drag_03.png"]
    assert len(metadata) == 3
    middle = Image.open(paths[1]).convert("RGBA")
    middle_pixel = middle.getpixel((64, 64))
    assert middle_pixel[0] > 0
    assert middle_pixel[2] > 0


def test_frame_delta_report_detects_pose_change(tmp_path: Path) -> None:
    first = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    second = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw_first = ImageDraw.Draw(first)
    draw_second = ImageDraw.Draw(second)
    draw_first.rectangle((8, 20, 28, 52), fill=(255, 255, 255, 255))
    draw_second.rectangle((20, 20, 40, 52), fill=(255, 255, 255, 255))
    path_a = tmp_path / "pose_a.png"
    path_b = tmp_path / "pose_b.png"
    first.save(path_a)
    second.save(path_b)

    report = frame_delta_report([path_a, path_b], loop=False)

    assert report.pair_count == 1
    assert report.mean_alpha_delta_ratio > 0
    assert report.mean_rgba_delta_ratio > 0
