from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image


DEFAULT_RULE = {"height": 900, "width": 980, "bottom": 960}
GROUP_RULES = {
    "A_sit_base": DEFAULT_RULE,
    "B_stand_base_pack": DEFAULT_RULE,
    "C_sleep_base_pack": DEFAULT_RULE,
    "D_special_motion_pack": DEFAULT_RULE,
    "E_QQ_pet_drag_system": DEFAULT_RULE,
    "base_templates": DEFAULT_RULE,
}


def group_for(path: Path, source: Path) -> str:
    try:
        return path.relative_to(source).parts[0]
    except (ValueError, IndexError):
        return ""


def normalize_image(source_path: Path, destination_path: Path, source_root: Path) -> bool:
    image = Image.open(source_path).convert("RGBA")
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return False

    crop = image.crop(bbox)
    group = group_for(source_path, source_root)
    rule = GROUP_RULES.get(group, DEFAULT_RULE)
    target_height = int(rule["height"])
    target_width = int(rule["width"])
    target_bottom = int(rule["bottom"])

    scale = min(target_height / crop.height, target_width / crop.width)
    new_width = max(1, int(round(crop.width * scale)))
    new_height = max(1, int(round(crop.height * scale)))
    resized = crop.resize((new_width, new_height), Image.Resampling.LANCZOS)

    canvas = Image.new("RGBA", image.size, (255, 255, 255, 0))
    left = max(0, min(image.width - new_width, (image.width - new_width) // 2))
    top = max(0, min(image.height - new_height, target_bottom - new_height))
    canvas.alpha_composite(resized, (left, top))

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(destination_path)
    return True


def normalize_tree(source: Path, destination: Path) -> int:
    count = 0
    for path in sorted(source.rglob("*.png")):
        relative = path.relative_to(source)
        if any(part.startswith("_") for part in relative.parts):
            continue
        if normalize_image(path, destination / relative, source):
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize pet PNG alpha bounds for runtime display.")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()

    count = normalize_tree(args.source, args.destination)
    print(f"normalized={count} destination={args.destination}")


if __name__ == "__main__":
    main()
