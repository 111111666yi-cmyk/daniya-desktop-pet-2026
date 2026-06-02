from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from pathlib import Path

FORBIDDEN_PATH_RE = re.compile(
    r"(^|/)(\.env|data|assets/private|models|backups|dist|build|release)(/|$)"
    r"|(^|/)config/(api_config|multimodal_config)\.json$"
    r"|(^|/)characters/daniya/assets(/|$)"
    r"|(^|/)characters/test_dummy(/|$)"
    r"|(^|/)docs/v0\.51_patch_audit(/|$)"
    r"|(^|/)__pycache__(/|$)"
    r"|\.(pyc|log|tmp)$",
    re.IGNORECASE,
)
SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{20,}|api[_-]?key\s*[:=]\s*['\"][^'\"]{12,}['\"])",
    re.IGNORECASE,
)
LOCAL_PATH_RE = re.compile(
    r"(C:\\Users\\[^\\\s`'\"]+|C:/Users/[^/\s`'\"]+|file:///C:/Users/[^/\s`'\"]+)",
    re.IGNORECASE,
)
REQUIRED_ENTRY_SUFFIXES = (
    "characters/daniya/story.yaml",
    "characters/template/story.yaml",
)
TEXT_SUFFIXES = {".txt", ".md", ".json", ".yaml", ".yml", ".py", ".bat", ".env", ".ini", ".cfg", ".example"}
MAX_TEXT_SCAN_BYTES = 1_000_000


def scan_zip(zip_path: Path) -> dict[str, object]:
    with zipfile.ZipFile(zip_path) as archive:
        names = [info.filename.replace("\\", "/") for info in archive.infolist()]
        forbidden = [name for name in names if FORBIDDEN_PATH_RE.search(name)]
        missing_required = [
            suffix for suffix in REQUIRED_ENTRY_SUFFIXES if not any(name.endswith(suffix) for name in names)
        ]
        secret_hits: list[str] = []
        local_path_hits: list[str] = []
        for info in archive.infolist():
            suffix = Path(info.filename).suffix.lower()
            if suffix not in TEXT_SUFFIXES or info.file_size > MAX_TEXT_SCAN_BYTES:
                continue
            try:
                text = archive.read(info).decode("utf-8", errors="ignore")
            except Exception:
                continue
            if SECRET_RE.search(text):
                secret_hits.append(info.filename)
            if LOCAL_PATH_RE.search(text):
                local_path_hits.append(info.filename)
        return {
            "zip": str(zip_path),
            "entry_count": len(names),
            "forbidden_entries": forbidden,
            "missing_required_entries": missing_required,
            "secret_hits": secret_hits,
            "local_path_hits": local_path_hits,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan a release zip for forbidden files and obvious secrets.")
    parser.add_argument("zip_path", type=Path)
    args = parser.parse_args()

    zip_path = args.zip_path.resolve()
    if not zip_path.exists():
        print(f"Zip not found: {zip_path}", file=sys.stderr)
        return 1

    result = scan_zip(zip_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result["forbidden_entries"] or result["missing_required_entries"] or result["secret_hits"] or result["local_path_hits"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
