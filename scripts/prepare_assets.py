from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIR = ROOT / "assets" / "private" / "daniya_summer"


def remove_white_background(source: Path, destination: Path, threshold: int = 245) -> None:
    image = Image.open(source).convert("RGBA")
    pixels = image.load()

    for y in range(image.height):
        for x in range(image.width):
            red, green, blue, alpha = pixels[x, y]
            if red >= threshold and green >= threshold and blue >= threshold:
                pixels[x, y] = (red, green, blue, 0)

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination)


def create_icon(source_png: Path, destination_ico: Path) -> None:
    image = Image.open(source_png).convert("RGBA")
    destination_ico.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination_ico, sizes=[(256, 256), (128, 128), (64, 64), (32, 32), (16, 16)])


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare private desktop pet assets.")
    parser.add_argument("--normal1", required=True, help="Path to idle/closed-mouth image.")
    parser.add_argument("--normal2", required=True, help="Path to speaking/open-mouth image.")
    parser.add_argument("--threshold", type=int, default=245, help="White threshold for transparency.")
    args = parser.parse_args()

    normal1_source = Path(args.normal1).expanduser().resolve()
    normal2_source = Path(args.normal2).expanduser().resolve()

    if not normal1_source.exists():
        raise FileNotFoundError(f"normal1 source does not exist: {normal1_source}")
    if not normal2_source.exists():
        raise FileNotFoundError(f"normal2 source does not exist: {normal2_source}")

    normal1_target = PRIVATE_DIR / "normal1.png"
    normal2_target = PRIVATE_DIR / "normal2.png"
    icon_target = PRIVATE_DIR / "app.ico"
    manifest_target = PRIVATE_DIR / "manifest.json"

    remove_white_background(normal1_source, normal1_target, args.threshold)
    remove_white_background(normal2_source, normal2_target, args.threshold)
    create_icon(normal1_target, icon_target)
    if not manifest_target.exists():
        manifest_target.write_text(
            """{
  "name": "daniya_summer",
  "display_name": "达妮娅·夏日形态",
  "default_height": 96,
  "animations": {
    "idle": ["normal1.png"],
    "talking": ["normal1.png", "normal2.png"],
    "hover": ["normal1.png"],
    "clicked": ["normal2.png"],
    "dragging": ["normal2.png"],
    "sleeping": ["normal1.png"],
    "happy": ["normal2.png"],
    "remind": ["normal2.png"]
  }
}
""",
            encoding="utf-8",
        )

    print(f"Wrote {normal1_target}")
    print(f"Wrote {normal2_target}")
    print(f"Wrote {icon_target}")
    print(f"Wrote {manifest_target}")


if __name__ == "__main__":
    main()
