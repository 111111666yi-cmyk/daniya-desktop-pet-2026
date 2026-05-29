import sys
import json
from pathlib import Path
from PIL import Image

def validate_assets(base_dir_str: str) -> None:
    base_dir = Path(base_dir_str)
    if not base_dir.exists():
        print(f"Directory {base_dir} does not exist.")
        return

    manifest_path = base_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"Manifest not found at {manifest_path}")
        return

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        print(f"Failed to load manifest: {e}")
        return

    actions = manifest.get("actions", {})
    if not actions:
        print("No actions defined in manifest.")
        return

    print(f"Validating manifest at {manifest_path}...")
    print("-" * 50)

    total_warnings = 0
    total_errors = 0

    for action_name, config in actions.items():
        frames = config.get("frames", [])
        fallback = config.get("fallback", [])
        
        print(f"Action: {action_name} (Frames: {len(frames)})")
        
        missing_frames = []
        sizes = set()
        has_alpha_all = True
        
        for frame in frames:
            frame_path = base_dir / frame
            if not frame_path.exists():
                missing_frames.append(frame)
                continue
                
            try:
                with Image.open(frame_path) as img:
                    sizes.add(img.size)
                    if img.mode not in ('RGBA', 'LA') and (img.mode == 'P' and 'transparency' not in img.info):
                        has_alpha_all = False
            except Exception as e:
                print(f"  [ERROR] Cannot open {frame}: {e}")
                total_errors += 1
                
        if missing_frames:
            print(f"  [ERROR] Missing frames: {missing_frames}")
            total_errors += 1
            
        if len(sizes) > 1:
            print(f"  [WARNING] Inconsistent sizes: {sizes}")
            total_warnings += 1
        elif len(sizes) == 1:
            print(f"  Size: {list(sizes)[0]}")
            
        if frames and not missing_frames:
            print(f"  Alpha Channel: {'Yes' if has_alpha_all else 'No (WARNING)'}")
            if not has_alpha_all:
                total_warnings += 1
                
        # Check fallbacks
        missing_fallbacks = []
        for fb in fallback:
            if not (base_dir / fb).exists():
                missing_fallbacks.append(fb)
                
        if missing_fallbacks:
            print(f"  [ERROR] Missing fallback frames: {missing_fallbacks}")
            total_errors += 1
        else:
            print(f"  Fallback: OK")
            
        print("-" * 50)

    print(f"Validation complete: {total_errors} errors, {total_warnings} warnings.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validate_assets.py <path_to_assets_dir>")
        sys.exit(1)
    validate_assets(sys.argv[1])
