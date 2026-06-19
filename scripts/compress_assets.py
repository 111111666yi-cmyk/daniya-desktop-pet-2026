"""Compress PNG assets using Pillow lossless optimization + optional quantization.

Targets:
- Legacy action frames (1254x1254) → lossless optimize
- v1_actual_runtime frames (1024x1024) → lossless optimize
- normal1.png / normal2.png → lossless optimize

All operations are in-place. Run with --dry-run to preview savings.
Add --quantize to enable lossy 256-color quantization (much smaller, visually
indistinguishable at 80-160px display sizes).
"""
import argparse
import sys
from pathlib import Path
from PIL import Image

ASSETS_ROOT = Path(__file__).resolve().parent.parent / "characters" / "daniya" / "assets"

SKIP_DIRS = {"_raw_originals", "blink"}


def compress_png(path: Path, *, quantize: bool) -> tuple[int, int]:
    """Compress a single PNG. Returns (old_size, new_size)."""
    old_size = path.stat().st_size
    img = Image.open(path)

    if quantize and img.mode == "RGBA":
        img = img.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=0)
        img = img.convert("RGBA")

    img.save(path, format="PNG", optimize=True)
    new_size = path.stat().st_size
    return old_size, new_size


def find_pngs(root: Path) -> list[Path]:
    pngs = []
    for p in sorted(root.rglob("*.png")):
        if any(skip in p.parts for skip in SKIP_DIRS):
            continue
        pngs.append(p)
    return pngs


def main() -> None:
    parser = argparse.ArgumentParser(description="Compress Daniya PNG assets")
    parser.add_argument("--dry-run", action="store_true", help="Show sizes without modifying")
    parser.add_argument("--quantize", action="store_true", help="Enable 256-color quantization (lossy)")
    args = parser.parse_args()

    if not ASSETS_ROOT.is_dir():
        print(f"Assets root not found: {ASSETS_ROOT}", file=sys.stderr)
        sys.exit(1)

    pngs = find_pngs(ASSETS_ROOT)
    print(f"Found {len(pngs)} PNGs to process (quantize={'ON' if args.quantize else 'OFF'})\n")

    total_old = 0
    total_new = 0

    for p in pngs:
        rel = p.relative_to(ASSETS_ROOT)
        old_size = p.stat().st_size

        if args.dry_run:
            total_old += old_size
            total_new += old_size
            print(f"  [dry-run] {rel}  {old_size / 1024:.0f} KB")
            continue

        old_sz, new_sz = compress_png(p, quantize=args.quantize)
        saved = old_sz - new_sz
        pct = (saved / old_sz * 100) if old_sz else 0
        total_old += old_sz
        total_new += new_sz
        marker = "  " if pct < 5 else "* "
        print(f"  {marker}{rel}  {old_sz / 1024:.0f} → {new_sz / 1024:.0f} KB  ({pct:.0f}% saved)")

    saved_total = total_old - total_new
    pct_total = (saved_total / total_old * 100) if total_old else 0
    print(f"\nTotal: {total_old / 1048576:.1f} → {total_new / 1048576:.1f} MB  ({pct_total:.1f}% saved, {saved_total / 1048576:.1f} MB freed)")


if __name__ == "__main__":
    main()
