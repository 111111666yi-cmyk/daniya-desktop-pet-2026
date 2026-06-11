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
from src.settings_window import (
    SettingsWindow,
    _api_key_placeholder,
    _format_data_status_summary,
    _format_event_log_summary,
    _format_user_memory_summary,
    _format_relationship_summary,
    _saved_api_key_status,
)


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


def test_application_lifecycle_keeps_process_alive_when_windows_are_hidden():
    from src.app import _configure_application_lifecycle

    class FakeApplication:
        def __init__(self) -> None:
            self.quit_on_last_window_closed = None

        def setQuitOnLastWindowClosed(self, value: bool) -> None:
            self.quit_on_last_window_closed = value

    app = FakeApplication()
    _configure_application_lifecycle(app)

    assert app.quit_on_last_window_closed is False


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
    assert ok is False
    assert "云端 API 未测试" in message


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


def test_character_pack_editor_default_root_uses_public_character_pack(monkeypatch, tmp_path):
    from src import character_pack_editor as editor_module

    runtime = tmp_path / "runtime"
    public_character_root = tmp_path / "public_characters"
    monkeypatch.setattr(editor_module, "runtime_root", lambda: runtime)
    monkeypatch.setattr(editor_module, "default_character_root", lambda: public_character_root)

    editor = CharacterPackEditor()

    assert editor.root == runtime
    assert editor.character_root == public_character_root


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


def test_api_key_placeholder_separates_saved_mask_from_input():
    masked = "sk-0****44ef"

    assert masked not in _api_key_placeholder(masked)
    assert masked in _saved_api_key_status(masked)
    assert "留空" in _api_key_placeholder(masked)


def test_settings_status_summaries_hide_raw_engine_details(tmp_path):
    rel_text = _format_relationship_summary(
        {
            "character_id": "daniya",
            "relationship_stage": "default_stay",
            "affection": 45,
            "defense_level": 86,
            "internal_debug": "hidden",
        }
    )
    assert "关系阶段：default_stay" in rel_text
    assert "relationship_stage" not in rel_text
    assert "internal_debug" not in rel_text

    event_text = _format_event_log_summary(
        [
            {
                "timestamp": "2026-06-01T20:19:42",
                "event_id": "user_drag",
                "source": "physical_event",
                "relationship_effect": {"defense_level": 1},
                "lore_fragments_used": [],
                "stage_before": "default_stay",
                "stage_after": "default_stay",
            }
        ]
    )
    assert "拖拽互动" in event_text
    assert "防御强度 +1" in event_text
    assert "event=" not in event_text
    assert "effect={" not in event_text

    state_path = tmp_path / "relationship_state.json"
    paths = {"relationship_state": state_path}
    data_text = _format_data_status_summary(
        {"exists": True, "relationship_state_readable": True, "relationship_state_error": None},
        paths,
    )
    assert "关系状态：" in data_text
    assert "relationship_state" not in data_text

    memory_text = _format_user_memory_summary(
        {"user_name": "你", "relationship": "陪伴角色与用户", "style": "简短"},
        {
            "user_preferences": {"likes_short_reply": True},
            "important_user_phrases": ["我不会先走"],
            "unlocked_lore": ["birthday_sovereignty"],
            "last_events": ["birthday_sovereignty"],
        },
        ["[2026-06-03 00:00:00] 喜欢安静陪伴"],
    )
    assert "用户档案" in memory_text
    assert "我不会先走" in memory_text
    assert "喜欢安静陪伴" in memory_text


def test_open_settings_center_warning_includes_attribute_detail(monkeypatch):
    from src import app as app_module

    warnings = []
    tracebacks = []

    class BrokenSettingsWindow:
        def __init__(self, *_args, **_kwargs):
            raise AttributeError("missing relation_tab")

    def fake_warning(_parent, title, text):
        warnings.append((title, text))

    monkeypatch.setattr(app_module, "SettingsWindow", BrokenSettingsWindow)
    monkeypatch.setattr(app_module.QMessageBox, "warning", fake_warning)
    monkeypatch.setattr(app_module.traceback, "print_exc", lambda: tracebacks.append(True))

    controller = SimpleNamespace(settings_window=None, window=object())
    app_module.AppController.open_settings_center(controller)

    assert controller.settings_window is None
    assert tracebacks == [True]
    assert warnings == [
        (
            "\u8bbe\u7f6e\u4e2d\u5fc3",
            "\u8bbe\u7f6e\u4e2d\u5fc3\u6253\u5f00\u5931\u8d25\uff1aAttributeError: missing relation_tab",
        )
    ]


def test_open_settings_center_restores_existing_minimized_window(monkeypatch):
    from PySide6.QtCore import Qt
    from src import app as app_module

    calls = []

    class ExistingSettingsWindow:
        def isMinimized(self):
            return True

        def showNormal(self):
            calls.append("showNormal")

        def show(self):
            calls.append("show")

        def windowState(self):
            return Qt.WindowState.WindowMinimized

        def setWindowState(self, _state):
            calls.append("setWindowState")

        def raise_(self):
            calls.append("raise")

        def activateWindow(self):
            calls.append("activate")

    monkeypatch.setattr(app_module, "SettingsWindow", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should reuse existing window")))

    existing = ExistingSettingsWindow()
    controller = SimpleNamespace(settings_window=existing, window=object())
    app_module.AppController.open_settings_center(controller)

    assert controller.settings_window is existing
    assert calls == ["showNormal", "setWindowState", "raise", "activate"]


def test_open_settings_center_creates_independent_taskbar_window(monkeypatch):
    from src import app as app_module

    calls = []

    class FinishedSignal:
        def connect(self, _callback):
            calls.append(("connect", None))

    class FakeSettingsWindow:
        def __init__(self, _controller, parent):
            calls.append(("parent", parent))
            self.finished = FinishedSignal()

        def show(self):
            calls.append(("show", None))

        def raise_(self):
            calls.append(("raise", None))

        def activateWindow(self):
            calls.append(("activate", None))

    monkeypatch.setattr(app_module, "SettingsWindow", FakeSettingsWindow)

    controller = SimpleNamespace(settings_window=None, window=object())
    app_module.AppController.open_settings_center(controller)

    assert calls == [("parent", None), ("connect", None), ("show", None), ("raise", None), ("activate", None)]
    assert isinstance(controller.settings_window, FakeSettingsWindow)


def test_story_mode_loads_chapters_from_character_pack(tmp_path):
    from src.menu_manager import MenuManager

    story_file = tmp_path / "story.yaml"
    story_file.write_text(
        """
chapters:
  - id: 7
    title: 测试章节
    body: 这是角色包里的剧情。
    prompt: 继续讲。
""".strip(),
        encoding="utf-8",
    )
    controller = SimpleNamespace(
        daniya_adapter=SimpleNamespace(character_pack=SimpleNamespace(root=tmp_path)),
    )
    manager = MenuManager(window=object(), controller=controller)

    assert manager._load_story_chapters() == [(7, "测试章节", "这是角色包里的剧情。", "继续讲。", None)]


def test_settings_window_opens_with_expected_tabs_in_subprocess(tmp_path):
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["DANIYA_RELATION_DATA_DIR"] = str(tmp_path / "relation")
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    shutil.copytree(Path("characters"), runtime_root / "characters")
    shutil.copytree(Path("config"), runtime_root / "config")
    app_cfg_path = runtime_root / "config" / "app_config.json"
    app_cfg = json.loads(app_cfg_path.read_text(encoding="utf-8"))
    for key in ["file_organizer_enabled", "system_status_enabled", "clipboard_enabled", "focus_mode_enabled"]:
        app_cfg[key] = False
    app_cfg_path.write_text(json.dumps(app_cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    env["DANIYA_RUNTIME_ROOT"] = str(runtime_root)
    script = r"""
import os, sys
from PySide6.QtWidgets import QApplication
from PySide6.QtWidgets import QPushButton
from src.config_manager import ConfigManager
from src.asset_manager import AssetManager
from src.app import AppController
app = QApplication.instance() or QApplication(sys.argv)
controller = AppController(app)
controller.open_settings_center()
app.processEvents()
tabs = [controller.settings_window.tabs.tabText(i) for i in range(controller.settings_window.tabs.count())]
assert tabs == [
    '\u6a21\u578b\u4e0e\u5f15\u64ce',
        '\u684c\u5ba0',
        '\u89d2\u8272\u4e0e\u8d44\u6e90',
        '\u5173\u7cfb\u4e0e\u4e8b\u4ef6',
        '\u517b\u6210',
        '\u7cfb\u7edf',
    '\u63d0\u9192',
    '\u6587\u4ef6\u6574\u7406',
    '\u7cfb\u7edf\u72b6\u6001',
    '\u526a\u8d34\u677f',
    '\u4e13\u6ce8\u6a21\u5f0f',
    '\u9690\u79c1\u4e0e\u5b89\u5168',
    '\u8bca\u65ad',
]
assert controller.settings_window.pack_editor_text.isReadOnly() is False
buttons = [button.text() for button in controller.settings_window.findChildren(QPushButton)]
assert '\u6e05\u7a7a\u8bb0\u5fc6' in buttons
assert '\u6062\u590d\u5b89\u5168\u9ed8\u8ba4' in buttons
assert '\u6062\u590d\u9690\u79c1\u9ed8\u8ba4' in buttons
assert '\u9000\u51fa\u4e13\u6ce8\u6a21\u5f0f' in buttons
assert controller.settings_window.file_organizer_enabled.isChecked() is False
assert controller.settings_window.system_status_enabled.isChecked() is False
assert controller.settings_window.clipboard_enabled.isChecked() is False
assert controller.settings_window.focus_enabled.isChecked() is False
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


@pytest.mark.skip(reason="_save_local_settings_only 已移除, 本地模型保存已合并到 _save_api_settings + _sync_model_profiles")
def test_settings_window_saves_local_model_settings_and_syncs_in_subprocess(tmp_path):
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["DANIYA_RELATION_DATA_DIR"] = str(tmp_path / "relation")
    env["DANIYA_RUNTIME_ROOT"] = str(tmp_path / "runtime")
    script = r"""
import os, sys, json
from PySide6.QtWidgets import QApplication
from src.app import AppController
app = QApplication.instance() or QApplication(sys.argv)
controller = AppController(app)
controller.open_settings_center()
app.processEvents()

# Simulate setting values on local model tab
window = controller.settings_window
window.local_service_combo.setCurrentText("Ollama")
window.local_base_url.setText("http://localhost:11434")

# Mock the model list dropdown selection
window.local_model_list.clear()
window.local_model_list.addItem("qwen2.5:0.5b")
window.local_model_list.setCurrentText("qwen2.5:0.5b")

# Trigger save
profile_id = window._save_local_settings_only()
app.processEvents()

# Verify that settings_manager saved the local model config in model_profiles.json
profiles_data = window.settings_manager.load_model_profiles()
active_profile = None
for p in profiles_data.get("profiles", []):
    if p.get("id") == profile_id:
        active_profile = p
        break

assert active_profile is not None
assert active_profile.get("provider") == "ollama"
assert active_profile.get("base_url") == "http://localhost:11434"
assert active_profile.get("model") == "qwen2.5:0.5b"

print('SETTINGS_LOCAL_SAVE_OK', flush=True)
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
    assert "SETTINGS_LOCAL_SAVE_OK" in completed.stdout

