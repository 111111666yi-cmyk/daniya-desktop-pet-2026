from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from PIL import Image, ImageColor, ImageDraw

from src.motion_asset_tools import anchor_stability_report, estimate_anchor, render_preview_gif, write_contact_sheet
from src.motion_catalog import build_motion_catalog


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render QA artifacts for a motion clip.")
    parser.add_argument("clip", type=str, help="Motion clip id, such as walk_loop or drag_pickup")
    parser.add_argument("--character-id", type=str, default="daniya", help="Character id under characters/")
    parser.add_argument("--manifest", type=Path, default=None, help="Override manifest path")
    parser.add_argument("--output-dir", type=Path, default=Path("_analysis") / "motion_preview", help="Directory for QA artifacts")
    parser.add_argument("--gif-duration-ms", type=int, default=90, help="Per-frame duration for the preview GIF")
    parser.add_argument("--gif-size", type=int, default=256, help="Square preview size for the GIF")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = args.manifest or Path("characters") / args.character_id / "assets" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    asset_dir = manifest_path.parent
    catalog = build_motion_catalog(asset_dir, manifest)
    clip = catalog.clip_spec(args.clip)
    if clip is None:
        raise SystemExit(f"unknown clip: {args.clip}")

    frame_paths = [asset_dir / frame for frame in clip.frames]
    missing = [str(path) for path in frame_paths if not path.exists()]
    if missing:
        raise SystemExit("missing frames:\n" + "\n".join(missing))

    clip_dir = args.output_dir / args.character_id / args.clip
    clip_dir.mkdir(parents=True, exist_ok=True)
    contact_sheet = clip_dir / f"{args.clip}_sheet.png"
    annotated_sheet = clip_dir / f"{args.clip}_anchors.png"
    preview_gif = clip_dir / f"{args.clip}.gif"
    report_path = clip_dir / f"{args.clip}_report.json"

    write_contact_sheet(frame_paths, contact_sheet)
    render_preview_gif(frame_paths, preview_gif, duration_ms=args.gif_duration_ms, scale_to=args.gif_size)
    render_anchor_sheet(frame_paths, annotated_sheet)
    report = anchor_stability_report(frame_paths)
    report_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(clip_dir)
    return 0


def render_anchor_sheet(frame_paths: list[Path], output_path: Path) -> None:
    images = [Image.open(path).convert("RGBA") for path in frame_paths]
    cols = min(4, max(1, len(images)))
    rows = (len(images) + cols - 1) // cols
    cell = 256
    sheet = Image.new("RGBA", (cols * cell, rows * cell), (244, 245, 248, 255))
    red = ImageColor.getrgb("#ff5c5c")
    blue = ImageColor.getrgb("#4b7cff")
    gold = ImageColor.getrgb("#ffb300")
    for index, image in enumerate(images):
        preview = image.copy()
        preview.thumbnail((cell - 16, cell - 32), Image.Resampling.LANCZOS)
        x = (index % cols) * cell + (cell - preview.width) // 2
        y = (index // cols) * cell + 8
        sheet.alpha_composite(preview, (x, y))
        draw = ImageDraw.Draw(sheet)
        anchors = estimate_anchor(preview)
        baseline = y + int(max(anchor[1] for key, anchor in anchors.items() if key.startswith("foot_")) * preview.height)
        draw.line((index % cols * cell + 8, baseline, (index % cols + 1) * cell - 8, baseline), fill=gold, width=2)
        for name, (ax, ay) in anchors.items():
            px = x + int(ax * preview.width)
            py = y + int(ay * preview.height)
            color = red if name == "root" else blue
            draw.ellipse((px - 4, py - 4, px + 4, py + 4), fill=color)
        draw.text((index % cols * cell + 8, (index // cols) * cell + cell - 20), frame_paths[index].stem, fill=(18, 18, 18, 255))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output_path)


if __name__ == "__main__":
    raise SystemExit(main())
