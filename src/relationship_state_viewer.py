from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from core.character_loader import load_character
from core.memory_engine import data_root as relation_data_root
from core.relationship_engine import save_state, state_path

from .backup_manager import BackupManager
from .utils import runtime_root


class RelationshipStateViewer:
    def __init__(self, backup_manager: BackupManager | None = None, character_id: str = "daniya") -> None:
        self.backup_manager = backup_manager or BackupManager(runtime_root())
        self.data_dir = relation_data_root()
        self.character_id = character_id

    def status(self, event_limit: int | None = 20) -> dict[str, Any]:
        paths = self.paths()
        state, state_error = _read_json_safe(paths["relationship_state"], {})
        from core.memory_engine import load_event_log
        try:
            events = load_event_log(limit=event_limit)
            event_error = None
        except Exception as exc:
            events = []
            event_error = str(exc)
        memory, memory_error = _read_json_safe(paths["user_memory"], {})
        return {
            "data_dir": str(self.data_dir),
            "exists": self.data_dir.exists(),
            "relationship_state": state if isinstance(state, dict) else {},
            "relationship_state_readable": state_error is None,
            "relationship_state_error": state_error,
            "event_log": events if isinstance(events, list) else [],
            "event_log_readable": event_error is None,
            "event_log_error": event_error,
            "user_memory": memory if isinstance(memory, dict) else {},
            "user_memory_readable": memory_error is None,
            "user_memory_error": memory_error,
        }

    def paths(self) -> dict[str, Path]:
        event_log_jsonl = self.data_dir / "event_log.jsonl"
        return {
            "relationship_state": state_path(self.character_id),
            "event_log": event_log_jsonl if event_log_jsonl.exists() else self.data_dir / "event_log.json",
            "user_memory": self.data_dir / "user_memory.json",
        }

    def export_state(self) -> Path:
        status = self.status(event_limit=None)
        return self.backup_manager.backup_json_value("relationship_state_export", status, "relationship_state_exports")

    def reset_state_with_backup(self) -> tuple[bool, str, Path | None]:
        path = self.paths()["relationship_state"]
        if not path.exists():
            return False, "重置已取消：relationship_state.json 不存在，无法创建重置前备份。", None
        try:
            backup = self.backup_manager.backup_file(path, "relationship_state_reset")
        except Exception as exc:
            return False, f"重置已取消：备份失败（{exc.__class__.__name__}）。", None
        pack = load_character(self.character_id)
        initial = dict(pack.relationship.get("initial_state") or {})
        initial.setdefault("character_id", self.character_id)
        initial.setdefault("relationship_stage", "default_stay")
        save_state(initial)
        return True, "关系状态已备份并重置。", backup

    def backup_data_dir(self) -> Path:
        return self.backup_manager.backup_directory(self.data_dir, "daniya_relation_data")


def _read_json_safe(path: Path, fallback: Any) -> tuple[Any, str | None]:
    if not path.exists():
        return fallback, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return fallback, f"json_error:{exc.__class__.__name__}"
    except OSError as exc:
        return fallback, f"os_error:{exc.__class__.__name__}"
