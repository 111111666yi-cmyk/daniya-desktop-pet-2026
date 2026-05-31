from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REQUIRED_FILES = [
    "config/app_config.example.json",
    "config/app_config.json",
    "config/api_config.example.json",
    ".env.example",
]
SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{20,}|api[_-]?key\s*[:=]\s*['\"][^'\"]{12,}['\"])",
    re.IGNORECASE,
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = project_root()
    failures: list[str] = []

    for relative in REQUIRED_FILES:
        path = root / relative
        if not path.exists():
            failures.append(f"Missing required config/template file: {relative}")
            continue
        text = path.read_text(encoding="utf-8")
        if SECRET_RE.search(text):
            failures.append(f"Possible secret in public config/template: {relative}")
        if path.suffix == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                failures.append(f"Invalid JSON in {relative}: {exc}")

    app_config_text = (root / "config" / "app_config.json").read_text(encoding="utf-8")
    home = str(Path.home()).replace("\\", "/")
    normalized_app_config = app_config_text.replace("\\", "/")
    if home and home in normalized_app_config:
        failures.append("config/app_config.json contains this user's home path")
    if "C:/Users/" in normalized_app_config:
        failures.append("config/app_config.json contains an absolute Windows user path")

    result = subprocess.run(
        ["git", "ls-files", "config/api_config.json", "config/multimodal_config.json"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        failures.append(result.stderr.strip() or "git ls-files failed")
    tracked = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    if tracked:
        failures.append("Ignored user config is tracked: " + ", ".join(tracked))

    if failures:
        print("Config template check failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Config template check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
