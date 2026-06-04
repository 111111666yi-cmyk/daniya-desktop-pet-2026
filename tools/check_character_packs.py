from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REQUIRED_PACKS = [
    Path("characters/daniya"),
    Path("characters/template"),
]


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = project_root()
    validator = root / "tools" / "validate_character_pack.py"
    failures: list[str] = []

    for pack in REQUIRED_PACKS:
        pack_path = root / pack
        if not pack_path.exists():
            failures.append(f"Missing character pack: {pack.as_posix()}")
            continue
        result = subprocess.run([sys.executable, str(validator), str(pack)], cwd=root, text=True, capture_output=True)
        if result.returncode != 0:
            failures.append(result.stdout.strip() or result.stderr.strip() or f"Validation failed: {pack}")
        else:
            print(result.stdout.strip())

    if failures:
        print("Character pack check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Character pack check passed; test_dummy is not required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
