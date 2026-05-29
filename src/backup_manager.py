from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .utils import ensure_dir, runtime_root


class BackupManager:
    def __init__(self, root: Path | None = None) -> None:
        self.root = root or runtime_root()
        self.backup_root = ensure_dir(self.root / "backups")

    def backup_file(self, path: Path, reason: str = "backup") -> Path:
        if not path.exists():
            raise FileNotFoundError(path)
        target_dir = ensure_dir(self.backup_root / _safe_name(reason))
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = target_dir / f"{path.name}.{stamp}.bak"
        shutil.copy2(path, target)
        return target

    def backup_json_value(self, name: str, value: Any, reason: str = "export") -> Path:
        target_dir = ensure_dir(self.backup_root / _safe_name(reason))
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = target_dir / f"{_safe_name(name)}.{stamp}.json"
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    def backup_directory(self, path: Path, reason: str = "directory") -> Path:
        if not path.exists():
            raise FileNotFoundError(path)
        target_dir = ensure_dir(self.backup_root / _safe_name(reason))
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = target_dir / f"{path.name}.{stamp}"
        shutil.copytree(path, target)
        return target


def _safe_name(value: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)
    return clean.strip("_") or "backup"
