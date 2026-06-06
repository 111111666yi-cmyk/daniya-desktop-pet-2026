from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROTECTED_PATHS = [
    ".env",
    "data",
    "backups",
    "assets/private",
    "assets/voices",
    "assets/voice_clips",
    "cache/tts",
    "models",
    "runtime",
    "release",
    "dist",
    "build",
    "config/api_config.json",
    "config/multimodal_config.json",
    "characters/test_dummy",
]


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = project_root()
    cmd = ["git", "ls-files", *PROTECTED_PATHS]
    result = subprocess.run(cmd, cwd=root, text=True, capture_output=True)
    if result.returncode != 0:
        print(result.stderr.strip() or "git ls-files failed", file=sys.stderr)
        return result.returncode or 1

    tracked = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if tracked:
        print("Sensitive or generated paths are tracked by Git:", file=sys.stderr)
        for path in tracked:
            print(f"- {path}", file=sys.stderr)
        return 1

    print("Sensitive tracked-path check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
