from __future__ import annotations

from pathlib import Path
import math

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "assets" / "private" / "daniya_summer" / "v1_actual_runtime" / "B_stand_base_pack"
DEST_DIR = ROOT / "assets" / "private" / "daniya_summer" / "v1_actual_runtime" / "B_walk_generated"


def paste_centered(canvas: Image.Image, sprite: Image.Image, x: int, y: int) -> None:
    canvas.alpha_composite(sprite, (x, y))


def make_frame(source: Image.Image, tilt: float, x_offset: int, y_offset: int, squash: float) -> Image.Image:
    bbox = source.getchannel("A").getbbox()
    if bbox is None:
        return source.copy()

    crop = source.crop(bbox)
    new_height = max(1, int(round(crop.height * squash)))
    sprite = crop.resize((crop.width, new_height), Image.Resampling.LANCZOS)
    sprite = sprite.rotate(tilt, resample=Image.Resampling.BICUBIC, expand=True)

    canvas = Image.new("RGBA", source.size, (255, 255, 255, 0))
    x = (source.width - sprite.width) // 2 + x_offset
    y = bbox[3] - sprite.height + y_offset
    paste_centered(canvas, sprite, x, y)
    return canvas


def main() -> None:
    source = Image.open(SOURCE_DIR / "stand_normal_01.png").convert("RGBA")
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    frame_count = 12
    for index in range(frame_count):
        phase = index / frame_count * math.tau
        tilt = math.sin(phase) * 1.1
        x_offset = int(round(math.sin(phase) * 5))
        y_offset = int(round(-3 + math.cos(phase * 2) * 2))
        squash = 1.0 + math.cos(phase * 2) * 0.003
        make_frame(source, tilt, x_offset, y_offset, squash).save(DEST_DIR / f"walk_{index + 1:02d}.png")
    print(f"generated={frame_count} destination={DEST_DIR}")


if __name__ == "__main__":
    main()
