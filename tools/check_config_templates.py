from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

REQUIRED_FILES = [
    "config/app_config.example.json",
    "config/app_config.json",
    "config/setup_config.json",
    "config/api_config.example.json",
    ".env.example",
]
SECRET_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{20,}|api[_-]?key\s*[:=]\s*['\"][^'\"]{12,}['\"])",
    re.IGNORECASE,
)
QUIET_DEFAULT_CONFIGS = [
    "config/app_config.example.json",
    "config/app_config.json",
]


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def main() -> int:
    root = project_root()
    failures: list[str] = []
    app_version = _load_app_version(root)

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
                data, duplicate_keys = _load_json_with_duplicate_keys(text)
            except json.JSONDecodeError as exc:
                failures.append(f"Invalid JSON in {relative}: {exc}")
                continue
            if duplicate_keys:
                failures.append(
                    f"Duplicate JSON keys in {relative}: {', '.join(sorted(set(duplicate_keys)))}"
                )
            if relative in QUIET_DEFAULT_CONFIGS:
                failures.extend(_check_quiet_defaults(relative, data, app_version))
            if relative == "config/setup_config.json":
                failures.extend(_check_setup_defaults(relative, data))

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


def _load_app_version(root: Path) -> str:
    version_text = (root / "src" / "version.py").read_text(encoding="utf-8")
    match = re.search(r"APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]", version_text)
    if not match:
        raise RuntimeError("src/version.py missing APP_VERSION")
    return match.group(1)


def _load_json_with_duplicate_keys(text: str) -> tuple[Any, list[str]]:
    duplicates: list[str] = []

    def build_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                duplicates.append(key)
            value[key] = item
        return value

    return json.loads(text, object_pairs_hook=build_object), duplicates


def _check_quiet_defaults(relative: str, data: object, app_version: str) -> list[str]:
    if not isinstance(data, dict):
        return [f"{relative} must contain a JSON object"]
    pet = data.get("pet") if isinstance(data.get("pet"), dict) else {}
    window = data.get("window") if isinstance(data.get("window"), dict) else {}
    growth = data.get("growth") if isinstance(data.get("growth"), dict) else {}
    failures: list[str] = []
    if data.get("version") != app_version:
        failures.append(f"{relative} expected version={app_version!r}, got {data.get('version')!r}")
    if data.get("quiet_defaults_migration") != "v0.61-quiet-defaults":
        failures.append(
            f"{relative} expected quiet_defaults_migration='v0.61-quiet-defaults', "
            f"got {data.get('quiet_defaults_migration')!r}"
        )
    if window.get("show_input") is not False:
        failures.append(f"{relative} expected window.show_input=false, got {window.get('show_input')!r}")
    expected_false = {
        "idle_chat_enabled": data.get("idle_chat_enabled"),
        "hourly_chime_enabled": data.get("hourly_chime_enabled"),
        "idle_behavior_enabled": data.get("idle_behavior_enabled"),
        "pet.edge_peek_enabled": pet.get("edge_peek_enabled"),
        "file_organizer_enabled": data.get("file_organizer_enabled"),
        "system_status_enabled": data.get("system_status_enabled"),
        "system_status_network_check_enabled": data.get("system_status_network_check_enabled"),
        "clipboard_interaction_enabled": data.get("clipboard_interaction_enabled"),
        "clipboard_show_preview": data.get("clipboard_show_preview"),
        "focus_mode_enabled": data.get("focus_mode_enabled"),
        "focus_mode_manual": data.get("focus_mode_manual"),
        "focus_mode_auto_game_detect": data.get("focus_mode_auto_game_detect"),
        "growth.enabled": growth.get("enabled"),
    }
    failures.extend(
        f"{relative} expected {key}=false, got {value!r}"
        for key, value in expected_false.items()
        if value is not False
    )
    try:
        idle_seconds = int(data.get("idle_behavior_seconds", 0))
    except (TypeError, ValueError):
        idle_seconds = 0
    if idle_seconds < 600:
        failures.append(f"{relative} expected idle_behavior_seconds >= 600, got {idle_seconds!r}")
    for key in ("system_status_interval_seconds", "system_status_cooldown_seconds"):
        try:
            seconds = int(data.get(key, 0))
        except (TypeError, ValueError):
            seconds = 0
        if seconds < 300:
            failures.append(f"{relative} expected {key} >= 300, got {seconds!r}")
    return failures


def _check_setup_defaults(relative: str, data: object) -> list[str]:
    if not isinstance(data, dict):
        return [f"{relative} must contain a JSON object"]
    failures: list[str] = []
    if data.get("first_run_setup") is not False:
        failures.append(f"{relative} expected first_run_setup=false, got {data.get('first_run_setup')!r}")
    if data.get("run_mode") != "local_fallback":
        failures.append(f"{relative} expected run_mode='local_fallback', got {data.get('run_mode')!r}")
    multimodal = data.get("multimodal_enabled")
    if not isinstance(multimodal, dict):
        failures.append(f"{relative} expected multimodal_enabled object")
    else:
        for key in ("tts", "text_to_image", "image_to_image", "video"):
            if multimodal.get(key) is not False:
                failures.append(f"{relative} expected multimodal_enabled.{key}=false, got {multimodal.get(key)!r}")
    return failures


if __name__ == "__main__":
    raise SystemExit(main())
