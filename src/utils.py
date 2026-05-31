from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "DaniyaSummerPet"


def bundled_root() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[1]


def user_data_root() -> Path:
    override = os.environ.get("DANIYA_RUNTIME_ROOT")
    if override:
        return Path(override).expanduser()

    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / APP_NAME
        return Path.home() / "AppData" / "Roaming" / APP_NAME

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME

    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME


def runtime_root() -> Path:
    override = os.environ.get("DANIYA_RUNTIME_ROOT")
    if override:
        return Path(override).expanduser()
    if getattr(sys, "frozen", False):
        return user_data_root()
    return Path(__file__).resolve().parents[1]


def resource_path(*parts: str) -> Path:
    external = runtime_root().joinpath(*parts)
    if external.exists():
        return external
    return bundled_root().joinpath(*parts)


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
