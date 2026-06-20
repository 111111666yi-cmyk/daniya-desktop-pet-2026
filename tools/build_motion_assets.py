from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.motion_asset_tools import (
    DEFAULT_CANVAS_SIZE,
    build_motion_assets,
    write_contact_sheet,
    write_manifest_fragment,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Slice, key, normalize, and package sprite frames.")
    parser.add_argument("source", type=Path, help="Directory of PNG frames or a sprite-sheet PNG")
    parser.add_argument("output", type=Path, help="Directory where normalized frames are written")
    parser.add_argument("--canvas", type=int, default=DEFAULT_CANVAS_SIZE, help="Square output canvas size")
    parser.add_argument("--grid-cols", type=int, default=None, help="Column count when source is a sheet image")
    parser.add_argument("--grid-rows", type=int, default=None, help="Row count when source is a sheet image")
    parser.add_argument("--frame-prefix", type=str, default="frame", help="Output name prefix for sliced sheet frames")
    parser.add_argument("--start-index", type=int, default=1, help="Start index for sliced sheet frames")
    parser.add_argument("--chroma-key", type=str, default=None, help="Optional hex color to remove, such as #00ff00")
    parser.add_argument("--transparent-threshold", type=int, default=16, help="Distance under this becomes fully transparent")
    parser.add_argument("--opaque-threshold", type=int, default=96, help="Distance above this remains fully opaque")
    parser.add_argument("--no-despill", action="store_true", help="Disable green-spill cleanup after keying")
    parser.add_argument("--contact-sheet", type=Path, default=None, help="Optional contact sheet output path")
    parser.add_argument("--manifest-fragment", type=Path, default=None, help="Optional JSON fragment output path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    normalized_paths, metadata = build_motion_assets(
        args.source,
        args.output,
        canvas_size=args.canvas,
        grid_cols=args.grid_cols,
        grid_rows=args.grid_rows,
        frame_prefix=args.frame_prefix,
        start_index=args.start_index,
        chroma_key=args.chroma_key,
        transparent_threshold=args.transparent_threshold,
        opaque_threshold=args.opaque_threshold,
        despill=not args.no_despill,
    )

    if args.contact_sheet is not None:
        write_contact_sheet(normalized_paths, args.contact_sheet)

    if args.manifest_fragment is not None:
        write_manifest_fragment(args.manifest_fragment, normalized_paths, metadata)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
