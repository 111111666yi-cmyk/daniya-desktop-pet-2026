from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

import yaml

from core.character_loader import safe_load_character, validate_character_pack, character_pack_path

from .backup_manager import BackupManager
from .utils import runtime_root


EDITABLE_FILES = {"character.yaml", "speech.yaml", "relationship.yaml", "events.yaml"}
READONLY_FILES = {"lore.md", "lore_index.yaml", "actions.yaml", "prompt_pack.md", "story.yaml"}
REQUIRED_FILES = {
    "character.yaml",
    "speech.yaml",
    "lore.md",
    "lore_index.yaml",
    "relationship.yaml",
    "events.yaml",
    "actions.yaml",
}
class CharacterPackEditor:
    def __init__(self, character_id: str = "daniya", root: Path | None = None, backup_manager: BackupManager | None = None) -> None:
        self.character_id = character_id
        self.root = root or runtime_root()
        self.character_root = self.root / "characters"
        self.pack_path = character_pack_path(character_id, root=self.character_root)
        self.backup_manager = backup_manager or BackupManager(self.root)
    def status(self) -> dict[str, Any]:
        pack, result = safe_load_character(self.character_id, root=self.character_root)
        files: dict[str, dict[str, Any]] = {}
        for name in sorted(REQUIRED_FILES | READONLY_FILES):
            path = self.pack_path / name
            files[name] = {
                "exists": path.exists(),
                "editable": name in EDITABLE_FILES,
                "readable": _is_readable(path),
                "yaml_ok": _yaml_ok(path) if path.suffix in {".yaml", ".yml"} and path.exists() else None,
            }
        return {
            "path": str(self.pack_path),
            "loaded": pack is not None,
            "validation_ok": result.ok,
            "validation_errors": result.error_summary(),
            "files": files,
        }

    def read_file(self, name: str) -> str:
        self._assert_known_file(name)
        path = self.pack_path / name
        if not path.exists() and self.character_id != "template":
            template_path = self.character_root / "template" / name
            if template_path.exists():
                return template_path.read_text(encoding="utf-8")
        return path.read_text(encoding="utf-8")

    def save_yaml_safely(self, name: str, text: str) -> tuple[bool, str, Path | None]:
        if name not in EDITABLE_FILES:
            return False, f"{name} 不允许在设置中心编辑。", None
        path = self.pack_path / name
        path.parent.mkdir(parents=True, exist_ok=True)

        backup = None
        original = ""
        if path.exists():
            backup = self.backup_manager.backup_file(path, f"character_pack_{self.character_id}")
            original = path.read_text(encoding="utf-8")

        try:
            yaml.safe_load(text)
        except yaml.YAMLError as exc:
            return False, f"YAML 解析失败：{exc.__class__.__name__}", None

        path.write_text(text, encoding="utf-8")
        result = validate_character_pack(self.character_id, root=self.character_root)
        if result.ok:
            return True, "保存并校验通过。", backup

        if original:
            path.write_text(original, encoding="utf-8")
        else:
            path.unlink(missing_ok=True)
        return False, "校验失败，已回滚/取消创建当前文件。\n" + result.error_summary(), backup

    def restore_backup(self, backup_path: Path, target_name: str) -> tuple[bool, str]:
        if target_name not in EDITABLE_FILES:
            return False, f"{target_name} 不允许恢复。"
        target = self.pack_path / target_name
        if not backup_path.exists():
            return False, "备份文件不存在。"
        self.backup_manager.backup_file(target, f"restore_before_{self.character_id}")
        shutil.copy2(backup_path, target)
        result = validate_character_pack(self.character_id, root=self.character_root)
        if result.ok:
            return True, "恢复成功，校验通过。"
        return False, "恢复后校验失败：\n" + result.error_summary()

    def _assert_known_file(self, name: str) -> None:
        if name not in REQUIRED_FILES and name not in READONLY_FILES:
            raise ValueError(f"Unknown character pack file: {name}")


def _is_readable(path: Path) -> bool:
    try:
        return path.exists() and path.read_text(encoding="utf-8") is not None
    except OSError:
        return False


def _yaml_ok(path: Path) -> bool:
    try:
        yaml.safe_load(path.read_text(encoding="utf-8"))
        return True
    except (OSError, yaml.YAMLError):
        return False
