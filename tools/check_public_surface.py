from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]

PUBLIC_TEXT_EXTENSIONS = {".md", ".txt", ".yaml", ".yml", ".json"}
PUBLIC_SURFACE_PREFIXES = (
    "README.md",
    "CHANGELOG.md",
    "VERSION_LOG.md",
    "AGENTS.md",
    "CONTRIBUTING.md",
    "docs/",
    "characters/daniya/",
    "characters/template/",
    "config/",
    ".github/",
)

LOCAL_PATH_MARKERS = (
    "<your-username>",
    "C:/Users/23775",
    "C:\\Users\\23775",
    "file:///C:/Users/23775",
    "daniya2026523",
)

CHARACTER_FORBIDDEN_TERMS = (
    "Codex 对接",
    "御主",
    "上帝视角",
    "剧情模式",
    "普通恋爱攻略对象",
    "高阶 lore",
    "工程化 lore",
    "工程项目",
    "工程意义",
    "工程实现",
    "人格图腾",
    "桌宠工程",
    "桌宠项目",
    "桌宠里的",
    "桌宠里属于",
    "桌宠人格",
    "桌宠达妮娅",
    "同人桌宠项目",
    "AI 桌宠",
    "Prompt Pack",
    "System Prompt Fragment",
    "Character Fragment",
    "Reply Rules",
)

STALE_DEFAULT_MARKERS = (
    "默认 90s",
    "默认 10 分钟无互动后，达妮娅会主动冒一句本地气泡",
    '"idle_behavior_seconds": 90',
    '"idle_behavior_enabled": true,     // 是否开启空闲阶段小动作',
)


def main() -> int:
    errors: list[str] = []
    tracked = _tracked_files()

    errors.extend(_check_public_paths(tracked))
    errors.extend(_check_character_copy(tracked))
    errors.extend(_check_stale_default_docs(tracked))
    errors.extend(_check_quiet_defaults())
    errors.extend(_check_memory_controls())

    if errors:
        print("Public surface check failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Public surface check passed.")
    return 0


def _tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return [ROOT / line.strip() for line in result.stdout.splitlines() if line.strip()]


def _check_public_paths(files: Iterable[Path]) -> list[str]:
    errors: list[str] = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if not _is_public_surface_file(rel, path):
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_no, line in enumerate(text.splitlines(), 1):
            for marker in LOCAL_PATH_MARKERS:
                if marker in line:
                    errors.append(f"{rel}:{line_no} contains public-path marker {marker!r}")
    return errors


def _check_character_copy(files: Iterable[Path]) -> list[str]:
    errors: list[str] = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if not (
            rel.startswith("characters/daniya/")
            or rel.startswith("characters/template/")
            or rel == "README.md"
            or rel.startswith("docs/")
        ):
            continue
        if path.suffix.lower() not in PUBLIC_TEXT_EXTENSIONS:
            continue
        text = _story_body_text(path) if path.name == "story.yaml" else path.read_text(encoding="utf-8", errors="ignore")
        for line_no, line in enumerate(text.splitlines(), 1):
            for term in CHARACTER_FORBIDDEN_TERMS:
                if term in line:
                    errors.append(f"{rel}:{line_no} contains review-forbidden wording {term!r}")
    return errors


def _check_stale_default_docs(files: Iterable[Path]) -> list[str]:
    errors: list[str] = []
    for path in files:
        rel = path.relative_to(ROOT).as_posix()
        if not (rel == "README.md" or rel.startswith("docs/")):
            continue
        if path.suffix.lower() not in PUBLIC_TEXT_EXTENSIONS:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for line_no, line in enumerate(text.splitlines(), 1):
            for marker in STALE_DEFAULT_MARKERS:
                if marker in line:
                    errors.append(f"{rel}:{line_no} contains stale default wording {marker!r}")
    return errors


def _story_body_text(path: Path) -> str:
    lines = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("      ") and not line.lstrip().startswith("prompt:"):
            lines.append(line)
    return "\n".join(lines)


def _check_quiet_defaults() -> list[str]:
    errors: list[str] = []
    for rel in ("config/app_config.json", "config/app_config.example.json"):
        data = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        pet = data.get("pet") if isinstance(data.get("pet"), dict) else {}
        expected_false = {
            "idle_chat_enabled": data.get("idle_chat_enabled"),
            "hourly_chime_enabled": data.get("hourly_chime_enabled"),
            "idle_behavior_enabled": data.get("idle_behavior_enabled"),
            "pet.edge_peek_enabled": pet.get("edge_peek_enabled"),
        }
        for key, value in expected_false.items():
            if value is not False:
                errors.append(f"{rel} expected {key}=false, got {value!r}")
        try:
            idle_seconds = int(data.get("idle_behavior_seconds", 0))
        except (TypeError, ValueError):
            idle_seconds = 0
        if idle_seconds < 600:
            errors.append(f"{rel} expected idle_behavior_seconds >= 600, got {idle_seconds!r}")
    return errors


def _check_memory_controls() -> list[str]:
    errors: list[str] = []
    settings_text = (ROOT / "src" / "settings_window.py").read_text(encoding="utf-8")
    memory_text = (ROOT / "core" / "memory_engine.py").read_text(encoding="utf-8")
    notes_text = (ROOT / "src" / "notes_manager.py").read_text(encoding="utf-8")
    if "清空记忆" not in settings_text:
        errors.append("settings_window.py missing visible clear-memory control")
    if "def clear_user_memory" not in memory_text:
        errors.append("memory_engine.py missing clear_user_memory()")
    if "def clear(" not in notes_text:
        errors.append("notes_manager.py missing clear()")
    return errors


def _is_public_surface_file(rel: str, path: Path) -> bool:
    if path.suffix.lower() not in PUBLIC_TEXT_EXTENSIONS:
        return False
    return any(rel == prefix or rel.startswith(prefix) for prefix in PUBLIC_SURFACE_PREFIXES)


if __name__ == "__main__":
    sys.exit(main())
