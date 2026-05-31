from __future__ import annotations

import sys
from pathlib import Path

from src import utils
from src.config_manager import ConfigManager
from src.settings_manager import SettingsManager


def _simulate_frozen(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    install_dir = tmp_path / "Program Files" / "Daniya"
    install_dir.mkdir(parents=True)
    exe = install_dir / "DaniyaSummerPet.exe"
    exe.write_text("", encoding="utf-8")

    bundle = tmp_path / "_internal"
    (bundle / "config").mkdir(parents=True)
    (bundle / "config" / "app_config.json").write_text('{"version":"test-bundle"}', encoding="utf-8")
    (bundle / "config" / "bookmarks.json").write_text("[]", encoding="utf-8")
    (bundle / "config" / "system_prompt.txt").write_text("bundle prompt", encoding="utf-8")

    appdata = tmp_path / "Roaming"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe), raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    monkeypatch.setenv("APPDATA", str(appdata))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("DANIYA_RUNTIME_ROOT", raising=False)
    return install_dir, bundle, appdata


def test_frozen_runtime_root_uses_appdata_not_exe_dir(monkeypatch, tmp_path):
    install_dir, bundle, appdata = _simulate_frozen(monkeypatch, tmp_path)

    assert utils.bundled_root() == bundle
    assert utils.runtime_root() == appdata / "DaniyaSummerPet"
    assert utils.runtime_root() != install_dir


def test_runtime_root_override(monkeypatch, tmp_path):
    override = tmp_path / "custom-runtime"
    monkeypatch.setenv("DANIYA_RUNTIME_ROOT", str(override))
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    assert utils.runtime_root() == override
    assert utils.user_data_root() == override


def test_resource_path_prefers_appdata_then_bundle(monkeypatch, tmp_path):
    _install_dir, bundle, appdata = _simulate_frozen(monkeypatch, tmp_path)
    runtime = appdata / "DaniyaSummerPet"
    runtime_config = runtime / "config"
    runtime_config.mkdir(parents=True)
    runtime_file = runtime_config / "app_config.json"
    runtime_file.write_text("{}", encoding="utf-8")

    assert utils.resource_path("config", "app_config.json") == runtime_file
    assert utils.resource_path("config", "system_prompt.txt") == bundle / "config" / "system_prompt.txt"


def test_config_and_settings_write_to_appdata_when_frozen(monkeypatch, tmp_path):
    install_dir, _bundle, appdata = _simulate_frozen(monkeypatch, tmp_path)
    runtime = appdata / "DaniyaSummerPet"

    config_manager = ConfigManager()
    settings_manager = SettingsManager(config_manager=config_manager)

    assert config_manager.root == runtime
    assert config_manager.config_dir == runtime / "config"
    assert settings_manager.env_path == runtime / ".env"
    assert settings_manager.api_config_path == runtime / "config" / "api_config.json"
    assert (runtime / "config" / "app_config.json").exists()
    assert (runtime / "config" / "api_config.json").exists()
    assert not (install_dir / "config").exists()
    assert not (install_dir / "data").exists()
