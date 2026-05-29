from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from src.asset_manager import AssetManager
from src.backup_manager import BackupManager
from src.character_pack_editor import CharacterPackEditor
from src.diagnostics_panel import run_diagnostics
from src.relationship_state_viewer import RelationshipStateViewer
from src.settings_manager import SettingsManager
from src.settings_window import SettingsWindow


class FakeConfigManager:
    def __init__(self) -> None:
        self.config = {
            "window": {"always_on_top": True, "opacity_percent": 100},
            "pet": {"pet_height": 96, "target_height": 96, "min_pet_height": 80, "max_pet_height": 160},
            "api": {},
            "ui": {},
        }

    def load_app_config(self):
        return deepcopy(self.config)

    def save_app_config(self, value):
        self.config = deepcopy(value)


def test_settings_manager_saves_api_config_without_plain_key(tmp_path):
    fake = FakeConfigManager()
    manager = SettingsManager(fake, root=tmp_path)
    manager.save_api_settings(
        provider="deepseek",
        base_url="https://example.test",
        model="deepseek-chat",
        api_key="secret-key",
        local_mode=True,
    )
    api_config = json.loads((tmp_path / "config" / "api_config.json").read_text(encoding="utf-8"))
    assert "api_key" not in api_config
    assert "secret-key" not in (tmp_path / "config" / "api_config.json").read_text(encoding="utf-8")
    assert "DEEPSEEK_API_KEY=secret-key" in (tmp_path / ".env").read_text(encoding="utf-8")
    ok, message = manager.test_api_connection()
    assert ok is True
    assert "本地模式" in message


def test_character_pack_editor_backs_up_valid_save_and_rolls_back_invalid_pack(tmp_path):
    shutil.copytree(Path("characters"), tmp_path / "characters")
    editor = CharacterPackEditor(root=tmp_path, backup_manager=BackupManager(tmp_path))
    original = editor.read_file("character.yaml")

    ok, message, backup = editor.save_yaml_safely("character.yaml", original)
    assert ok is True
    assert backup is not None and backup.exists()

    data = yaml.safe_load(original)
    data.pop("display_name", None)
    invalid_text = yaml.safe_dump(data, allow_unicode=True, sort_keys=False)
    ok, message, backup = editor.save_yaml_safely("character.yaml", invalid_text)
    assert ok is False
    assert backup is not None and backup.exists()
    assert editor.read_file("character.yaml") == original

    ok, message, backup = editor.save_yaml_safely("lore.md", "bad")
    assert ok is False
    assert backup is None


def test_relationship_viewer_exports_and_resets_with_backup(tmp_path, monkeypatch):
    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(tmp_path / "relation"))
    viewer = RelationshipStateViewer(BackupManager(tmp_path))
    viewer.data_dir.mkdir(parents=True, exist_ok=True)
    state_path = viewer.paths()["relationship_state"]
    state_path.write_text(json.dumps({"character_id": "daniya", "relationship_stage": "x", "trust": 99}), encoding="utf-8")

    export = viewer.export_state()
    assert export.exists()
    ok, message, backup = viewer.reset_state_with_backup()
    assert ok is True
    assert backup is not None and backup.exists()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["relationship_stage"] == "default_stay"
    assert state["trust"] == 35


def test_relationship_reset_refuses_without_successful_backup(tmp_path, monkeypatch):
    class FailingBackupManager(BackupManager):
        def backup_file(self, path: Path, reason: str = "backup") -> Path:
            raise OSError("simulated backup failure")

    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(tmp_path / "relation"))
    viewer = RelationshipStateViewer(FailingBackupManager(tmp_path))
    viewer.data_dir.mkdir(parents=True, exist_ok=True)
    state_path = viewer.paths()["relationship_state"]
    original = {"character_id": "daniya", "relationship_stage": "x", "trust": 99}
    state_path.write_text(json.dumps(original), encoding="utf-8")

    ok, message, backup = viewer.reset_state_with_backup()

    assert ok is False
    assert backup is None
    assert "备份失败" in message
    assert json.loads(state_path.read_text(encoding="utf-8")) == original


def test_relationship_reset_refuses_when_state_file_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(tmp_path / "relation"))
    viewer = RelationshipStateViewer(BackupManager(tmp_path))
    viewer.data_dir.mkdir(parents=True, exist_ok=True)

    ok, message, backup = viewer.reset_state_with_backup()

    assert ok is False
    assert backup is None
    assert "不存在" in message
    assert not viewer.paths()["relationship_state"].exists()


def test_diagnostics_do_not_expose_full_api_key(tmp_path):
    fake = FakeConfigManager()
    manager = SettingsManager(fake, root=tmp_path)
    manager.save_api_settings("deepseek", "https://example.test", "deepseek-chat", api_key="secret-key", local_mode=True)
    results = run_diagnostics(manager, AssetManager({}))
    text = "\n".join(item["message"] for item in results)
    assert "secret-key" not in text
    assert any(item["name"] == "角色包校验" and item["status"] == "pass" for item in results)


def test_settings_window_opens_with_expected_tabs_in_subprocess(tmp_path):
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["DANIYA_RELATION_DATA_DIR"] = str(tmp_path / "relation")
    script = r"""
import os, sys
from PySide6.QtWidgets import QApplication
from src.config_manager import ConfigManager
from src.asset_manager import AssetManager
from src.app import AppController
app = QApplication.instance() or QApplication(sys.argv)
controller = AppController(app)
controller.open_settings_center()
app.processEvents()
tabs = [controller.settings_window.tabs.tabText(i) for i in range(controller.settings_window.tabs.count())]
assert tabs == ['API / 模型', '多模态配置', '本地模型', '桌宠', '动作资源', '角色包', '关系状态', '事件', '数据', '诊断']
assert controller.settings_window.pack_editor_text.isReadOnly() is False
print('SETTINGS_WINDOW_OK', flush=True)
os._exit(0)
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path.cwd(),
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "SETTINGS_WINDOW_OK" in completed.stdout
