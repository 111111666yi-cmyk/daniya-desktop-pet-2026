from __future__ import annotations

import argparse
import json
import re
import sys
import time
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
    "DaniyaSummerPet.exe",
    "README.md",
    "LICENSE",
    ".env.example",
    "config/app_config.json",
    "config/app_config.example.json",
    "config/api_config.example.json",
    "config/model_profiles.json",
    "characters/daniya/actions.yaml",
    "characters/daniya/character.yaml",
    "characters/daniya/events.yaml",
    "characters/daniya/lore.md",
    "characters/daniya/lore_index.yaml",
    "characters/daniya/prompt_pack.md",
    "characters/daniya/relationship.yaml",
    "characters/daniya/speech.yaml",
    "characters/daniya/story.yaml",
    "characters/daniya/items.json",
    "characters/daniya/outfits.json",
    "characters/daniya/ambient_events.json",
    "characters/template/story.yaml",
    "characters/template/items.json",
    "characters/template/outfits.json",
    "characters/template/ambient_events.json",
    "assets/icons/weather_umbrella.png",
    "docs/natural_reminders.md",
    "docs/file_organizer.md",
    "docs/system_status.md",
    "docs/clipboard_privacy.md",
    "docs/focus_mode.md",
    "docs/V0.80_INTEGRATION_ACCEPTANCE.md",
    "docs/V0.80_MANUAL_QA_CHECKLIST.md",
    "docs/memory_and_diary.md",
    "docs/V0.83_INTEGRATION_ACCEPTANCE.md",
    "docs/V0.83_MANUAL_QA_CHECKLIST.md",
    "docs/V0.81_V0.83_RELEASE_REPORT.md",
)
TEXT_SUFFIXES = {".txt", ".md", ".json", ".yaml", ".yml", ".py", ".bat", ".env", ".ini", ".cfg", ".example"}
MAX_TEXT_SCAN_BYTES = 1_000_000


def _source_app_version() -> str:
    version_path = Path(__file__).resolve().parents[1] / "src" / "version.py"
    match = re.search(
        r"APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]",
        version_path.read_text(encoding="utf-8"),
    )
    if match is None:
        raise RuntimeError("src/version.py missing APP_VERSION")
    return match.group(1)


APP_VERSION = _source_app_version()


def scan_zip(zip_path: Path) -> dict[str, object]:
    with _open_validated_zip(zip_path) as archive:
        names = [info.filename.replace("\\", "/") for info in archive.infolist()]
        expected_root = f"DaniyaSummerPet-{APP_VERSION}-win-x64/"
        package_root_matches = any(name.startswith(expected_root) for name in names)
        forbidden = [name for name in names if FORBIDDEN_PATH_RE.search(name)]
        missing_required = [
            suffix for suffix in REQUIRED_ENTRY_SUFFIXES if not any(name.endswith(suffix) for name in names)
        ]
        secret_hits: list[str] = []
        local_path_hits: list[str] = []
        config_errors: list[str] = []
        app_config_info = next(
            (info for info in archive.infolist() if info.filename.replace("\\", "/").endswith("config/app_config.json")),
            None,
        )
        if app_config_info is not None:
            try:
                app_config = json.loads(archive.read(app_config_info).decode("utf-8"))
                packaged_version = str(app_config.get("version", "")) if isinstance(app_config, dict) else ""
                if packaged_version != APP_VERSION:
                    config_errors.append(
                        f"config/app_config.json version {packaged_version!r} != {APP_VERSION!r}"
                    )
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                config_errors.append(f"config/app_config.json unreadable: {exc}")
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
            "zip_error": None,
            "expected_package_root": expected_root,
            "package_root_matches": package_root_matches,
            "forbidden_entries": forbidden,
            "missing_required_entries": missing_required,
            "config_errors": config_errors,
            "secret_hits": secret_hits,
            "local_path_hits": local_path_hits,
        }


def _open_validated_zip(zip_path: Path) -> zipfile.ZipFile:
    last_error: Exception | None = None
    for attempt in range(5):
        try:
            archive = zipfile.ZipFile(zip_path)
            bad_member = archive.testzip()
            if bad_member:
                archive.close()
                raise zipfile.BadZipFile(f"corrupt member: {bad_member}")
            return archive
        except (OSError, zipfile.BadZipFile) as exc:
            last_error = exc
            if attempt < 4:
                time.sleep(0.5)
                continue
            raise
    raise zipfile.BadZipFile(str(last_error or "unknown zip validation error"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Scan a release zip for forbidden files and obvious secrets.")
    parser.add_argument("zip_path", type=Path)
    args = parser.parse_args()

    zip_path = args.zip_path.resolve()
    if not zip_path.exists():
        print(f"Zip not found: {zip_path}", file=sys.stderr)
        return 1

    try:
        result = scan_zip(zip_path)
    except (OSError, zipfile.BadZipFile) as exc:
        result = {
            "zip": str(zip_path),
            "entry_count": 0,
            "zip_error": str(exc),
            "expected_package_root": f"DaniyaSummerPet-{APP_VERSION}-win-x64/",
            "package_root_matches": False,
            "forbidden_entries": [],
            "missing_required_entries": list(REQUIRED_ENTRY_SUFFIXES),
            "config_errors": [],
            "secret_hits": [],
            "local_path_hits": [],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if (
        result["zip_error"]
        or not result["package_root_matches"]
        or result["forbidden_entries"]
        or result["missing_required_entries"]
        or result["config_errors"]
        or result["secret_hits"]
        or result["local_path_hits"]
    ):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
