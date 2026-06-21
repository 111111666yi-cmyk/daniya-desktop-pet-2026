from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.motion_asset_tools import (
    DEFAULT_CANVAS_SIZE,
    anchor_stability_report,
    anchor_stability_report_from_metadata,
    build_motion_assets,
    frame_delta_report,
    render_preview_gif,
    write_catalog_fragment,
    write_contact_sheet,
    write_manifest_fragment,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import a candidate motion sheet into the Daniya motion rebuild workspace."
    )
    parser.add_argument("clip_id", type=str, help="Target clip id, such as walk_loop or drag_pickup")
    parser.add_argument("source", type=Path, help="Sheet PNG or directory of source PNG frames")
    parser.add_argument("--character-id", type=str, default="daniya", help="Character id under characters/")
    parser.add_argument("--canvas", type=int, default=DEFAULT_CANVAS_SIZE, help="Square output canvas size")
    parser.add_argument("--grid-cols", type=int, default=None, help="Column count when source is a sheet image")
    parser.add_argument("--grid-rows", type=int, default=None, help="Row count when source is a sheet image")
    parser.add_argument("--frame-prefix", type=str, default=None, help="Output frame prefix; defaults to clip id")
    parser.add_argument("--start-index", type=int, default=1, help="Start index for sliced sheet frames")
    parser.add_argument("--cell-inset-percent", type=float, default=0.0, help="Optional safe-area inset ratio applied to every sliced sheet cell")
    parser.add_argument("--chroma-key", type=str, default="#00ff00", help="Hex chroma key to remove; use empty string to disable")
    parser.add_argument("--transparent-threshold", type=int, default=16, help="Distance under this becomes fully transparent")
    parser.add_argument("--opaque-threshold", type=int, default=96, help="Distance above this remains fully opaque")
    parser.add_argument("--alpha-floor", type=int, default=0, help="Force pixels below this alpha to fully transparent after chroma keying")
    parser.add_argument("--no-despill", action="store_true", help="Disable spill cleanup after keying")
    parser.add_argument("--cleanup-islands", action="store_true", help="Remove disconnected alpha islands after keying")
    parser.add_argument("--cleanup-alpha-threshold", type=int, default=24, help="Alpha threshold used by island cleanup")
    parser.add_argument("--cleanup-min-component-area", type=int, default=96, help="Minimum area for detached components to survive cleanup when they are near the main silhouette")
    parser.add_argument("--cleanup-near-margin-px", type=int, default=64, help="Margin around the main silhouette used to preserve nearby detached components during cleanup")
    parser.add_argument("--target-frame-count", type=int, default=None, help="Optional runtime frame count after resampling the source")
    parser.add_argument("--resample-mode", type=str, default="blend", choices=["blend", "hold"], help="Resampling mode when --target-frame-count is set")
    parser.add_argument("--runtime-dir", type=Path, default=None, help="Override runtime output directory")
    parser.add_argument("--report-dir", type=Path, default=None, help="Override report output directory")
    parser.add_argument("--kind", type=str, default="sprite_sequence", choices=["sprite_sequence", "live2d_preview", "live2d_runtime"], help="Motion clip kind for the catalog fragment")
    parser.add_argument("--frame-duration-ms", type=int, default=90, help="Per-frame duration for the generated catalog fragment")
    parser.add_argument("--gif-duration-ms", type=int, default=90, help="Per-frame duration for the preview GIF")
    parser.add_argument("--gif-size", type=int, default=256, help="Square preview size for the GIF")
    parser.add_argument("--state-id", type=str, default=None, help="State id to generate alongside the clip; defaults to clip id")
    parser.add_argument("--state-priority", type=int, default=30, help="Priority for the generated state fragment")
    parser.add_argument("--state-min-hold-ms", type=int, default=0, help="Min hold time for the generated state fragment")
    parser.add_argument("--fallback-state", type=str, default=None, help="Fallback state for the generated state fragment")
    parser.add_argument("--transition-in", type=str, default=None, help="Optional transition_in clip name")
    parser.add_argument("--transition-out", type=str, default=None, help="Optional transition_out clip name")
    parser.add_argument("--cycle-distance-px", type=float, default=None, help="If set, include a locomotion_profile with this cycle distance")
    parser.add_argument("--min-speed-px-s", type=float, default=None, help="Optional locomotion minimum speed")
    parser.add_argument("--max-speed-px-s", type=float, default=None, help="Optional locomotion maximum speed")
    parser.add_argument("--renderer-binding-json", type=str, default=None, help="Inline JSON object or path to a JSON file for renderer_binding")
    parser.add_argument("--baseline-threshold-px", type=float, default=None, help="Fail import when baseline jitter exceeds this threshold")
    parser.add_argument("--root-threshold-px", type=float, default=None, help="Fail import when root jitter exceeds this threshold")
    parser.add_argument("--foot-threshold-px", type=float, default=None, help="Fail import when either foot jitter exceeds this threshold")
    parser.add_argument("--alpha-delta-threshold", type=float, default=None, help="Fail import when mean alpha delta ratio is lower than this threshold")
    parser.add_argument("--rgba-delta-threshold", type=float, default=None, help="Fail import when mean rgba delta ratio is lower than this threshold")
    loop_group = parser.add_mutually_exclusive_group()
    loop_group.add_argument("--loop", dest="loop", action="store_true", help="Mark the clip and state as looping")
    loop_group.add_argument("--no-loop", dest="loop", action="store_false", help="Mark the clip and state as non-looping")
    parser.set_defaults(loop=True)
    parser.add_argument("--no-state-fragment", action="store_true", help="Generate only the clip fragment without a state entry")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    asset_dir = Path("characters") / args.character_id / "assets"
    runtime_dir = args.runtime_dir or asset_dir / "motion_rebuild" / "runtime" / args.clip_id
    report_dir = args.report_dir or asset_dir / "motion_rebuild" / "reports" / args.clip_id
    frame_prefix = args.frame_prefix or args.clip_id
    state_id = None if args.no_state_fragment else (args.state_id or args.clip_id)

    runtime_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    frame_paths, metadata = build_motion_assets(
        args.source,
        runtime_dir,
        canvas_size=args.canvas,
        grid_cols=args.grid_cols,
        grid_rows=args.grid_rows,
        frame_prefix=frame_prefix,
        start_index=args.start_index,
        cell_inset_percent=args.cell_inset_percent,
        chroma_key=args.chroma_key or None,
        transparent_threshold=args.transparent_threshold,
        opaque_threshold=args.opaque_threshold,
        despill=not args.no_despill,
        alpha_floor=args.alpha_floor,
        cleanup_islands=args.cleanup_islands,
        cleanup_alpha_threshold=args.cleanup_alpha_threshold,
        cleanup_min_component_area=args.cleanup_min_component_area,
        cleanup_near_margin_px=args.cleanup_near_margin_px,
        target_frame_count=args.target_frame_count,
        resample_mode=args.resample_mode,
        loop_for_resample=args.loop,
    )

    contact_sheet_path = report_dir / f"{args.clip_id}_sheet.png"
    preview_gif_path = report_dir / f"{args.clip_id}.gif"
    qa_report_path = report_dir / f"{args.clip_id}_report.json"
    frame_manifest_path = report_dir / f"{args.clip_id}_frames.json"
    catalog_fragment_path = report_dir / f"{args.clip_id}_catalog_fragment.json"

    write_contact_sheet(frame_paths, contact_sheet_path)
    render_preview_gif(frame_paths, preview_gif_path, duration_ms=args.gif_duration_ms, scale_to=args.gif_size)
    source_report = anchor_stability_report_from_metadata(metadata, source_space=True)
    runtime_report = anchor_stability_report(frame_paths)
    delta_report = frame_delta_report(frame_paths, loop=args.loop)
    qa_report_path.write_text(
        json.dumps(
            {
                "source_space": source_report.to_dict(),
                "runtime_space": runtime_report.to_dict(),
                "frame_delta": delta_report.to_dict(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    write_manifest_fragment(frame_manifest_path, frame_paths, metadata)

    frame_refs = [relative_to_asset_dir(path, asset_dir) for path in frame_paths]
    write_catalog_fragment(
        catalog_fragment_path,
        args.clip_id,
        frame_refs,
        metadata,
        kind=args.kind,
        frame_duration_ms=args.frame_duration_ms,
        loop=args.loop,
        state_id=state_id,
        state_priority=args.state_priority,
        state_min_hold_ms=args.state_min_hold_ms,
        fallback_state=args.fallback_state,
        transition_in=args.transition_in,
        transition_out=args.transition_out,
        cycle_distance_px=args.cycle_distance_px,
        min_speed_px_s=args.min_speed_px_s,
        max_speed_px_s=args.max_speed_px_s,
        renderer_binding=load_renderer_binding(args.renderer_binding_json),
    )

    failures = validate_report(source_report, delta_report, args)
    summary = {
        "clip_id": args.clip_id,
        "source": str(args.source),
        "runtime_dir": str(runtime_dir),
        "report_dir": str(report_dir),
        "frame_count": len(frame_paths),
        "target_frame_count": args.target_frame_count,
        "frames": frame_refs,
        "artifacts": {
            "contact_sheet": str(contact_sheet_path),
            "preview_gif": str(preview_gif_path),
            "qa_report": str(qa_report_path),
            "frame_manifest": str(frame_manifest_path),
            "catalog_fragment": str(catalog_fragment_path),
        },
        "qa": {
            "source_space": source_report.to_dict(),
            "runtime_space": runtime_report.to_dict(),
            "frame_delta": delta_report.to_dict(),
        },
        "gate_failures": failures,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 2 if failures else 0


def relative_to_asset_dir(path: Path, asset_dir: Path) -> str:
    try:
        return path.resolve().relative_to(asset_dir.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def load_renderer_binding(value: str | None) -> dict[str, str] | None:
    if not value:
        return None
    maybe_path = Path(value)
    if maybe_path.exists():
        payload = json.loads(maybe_path.read_text(encoding="utf-8"))
    else:
        payload = json.loads(value)
    if not isinstance(payload, dict):
        raise ValueError("renderer binding must decode to a JSON object")
    return {str(key): str(item) for key, item in payload.items()}


def validate_report(report: Any, delta_report: Any, args: argparse.Namespace) -> list[str]:
    failures: list[str] = []
    if args.root_threshold_px is not None and report.root_jitter_px > args.root_threshold_px:
        failures.append(f"root_jitter_px={report.root_jitter_px:.3f} exceeds {args.root_threshold_px:.3f}")
    if args.foot_threshold_px is not None:
        if report.foot_left_jitter_px > args.foot_threshold_px:
            failures.append(f"foot_left_jitter_px={report.foot_left_jitter_px:.3f} exceeds {args.foot_threshold_px:.3f}")
        if report.foot_right_jitter_px > args.foot_threshold_px:
            failures.append(f"foot_right_jitter_px={report.foot_right_jitter_px:.3f} exceeds {args.foot_threshold_px:.3f}")
    if args.baseline_threshold_px is not None and report.baseline_jitter_px > args.baseline_threshold_px:
        failures.append(f"baseline_jitter_px={report.baseline_jitter_px:.3f} exceeds {args.baseline_threshold_px:.3f}")
    if args.alpha_delta_threshold is not None and delta_report.mean_alpha_delta_ratio < args.alpha_delta_threshold:
        failures.append(
            f"mean_alpha_delta_ratio={delta_report.mean_alpha_delta_ratio:.6f} is below {args.alpha_delta_threshold:.6f}"
        )
    if args.rgba_delta_threshold is not None and delta_report.mean_rgba_delta_ratio < args.rgba_delta_threshold:
        failures.append(
            f"mean_rgba_delta_ratio={delta_report.mean_rgba_delta_ratio:.6f} is below {args.rgba_delta_threshold:.6f}"
        )
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
