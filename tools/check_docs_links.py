from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote

LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def is_external(target: str) -> bool:
    lowered = target.lower()
    return lowered.startswith(("http://", "https://", "mailto:", "file://", "#"))


def iter_markdown_files(root: Path) -> list[Path]:
    return [root / "README.md", *sorted((root / "docs").glob("*.md"))]


def main() -> int:
    root = project_root()
    missing: list[str] = []

    for file_path in iter_markdown_files(root):
        if not file_path.exists():
            continue
        text = file_path.read_text(encoding="utf-8", errors="ignore")
        for match in LINK_RE.finditer(text):
            target = match.group(1).strip()
            if is_external(target):
                continue
            target = unquote(target.split("#", 1)[0].strip())
            if not target:
                continue
            candidate = (file_path.parent / target).resolve()
            if not candidate.exists():
                missing.append(f"{file_path.relative_to(root).as_posix()} -> {target}")

    if missing:
        print("Missing local markdown links:", file=sys.stderr)
        for item in missing:
            print(f"- {item}", file=sys.stderr)
        return 1

    print("Docs local link check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
