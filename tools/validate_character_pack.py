from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.character_loader import validate_character_pack


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a v0.415 character pack.")
    parser.add_argument("character_id", nargs="?", default="daniya")
    parser.add_argument("--root", type=Path, default=PROJECT_ROOT / "characters", help="Directory containing character packs.")
    args = parser.parse_args(argv)

    character_id = args.character_id
    root = args.root
    candidate = Path(character_id)
    if candidate.exists() and candidate.is_dir():
        root = candidate.parent
        character_id = candidate.name

    result = validate_character_pack(character_id, root=root)
    if result.ok:
        print(f"Character pack OK: {result.character_id}")
        return 0

    print(f"Character pack invalid: {result.character_id}")
    for issue in result.issues:
        print(issue.format())
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
