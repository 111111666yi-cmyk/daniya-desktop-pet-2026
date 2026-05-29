from __future__ import annotations

import argparse
from collections import deque
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_DIR = ROOT / "assets" / "private" / "daniya_summer"


def remove_white_background(source: Path, destination: Path, threshold: int = 245) -> None:
    image = Image.open(source).convert("RGBA")
    pixels = image.load()
    queue: deque[tuple[int, int]] = deque()
    visited: set[tuple[int, int]] = set()

    def is_background(x: int, y: int) -> bool:
        red, green, blue, alpha = pixels[x, y]
        return alpha > 0 and red >= threshold and green >= threshold and blue >= threshold

    def enqueue(x: int, y: int) -> None:
        point = (x, y)
        if point not in visited and is_background(x, y):
            visited.add(point)
            queue.append(point)

    for x in range(image.width):
        enqueue(x, 0)
        enqueue(x, image.height - 1)
    for y in range(image.height):
        enqueue(0, y)
        enqueue(image.width - 1, y)

    while queue:
        x, y = queue.popleft()
        red, green, blue, alpha = pixels[x, y]
        pixels[x, y] = (red, green, blue, 0)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < image.width and 0 <= ny < image.height:
                enqueue(nx, ny)

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
  "actions_version": "0.4",
  "animations": {
    "idle": ["normal1.png"],
    "talk": ["normal1.png", "normal2.png"],
    "talking": ["normal1.png", "normal2.png"],
    "hover": ["normal1.png"],
    "clicked": ["normal2.png"],
    "drag": ["normal2.png"],
    "dragging": ["normal2.png"],
    "sleep": ["normal1.png"],
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
