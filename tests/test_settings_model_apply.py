import os
import subprocess
import sys
from pathlib import Path

import pytest

def test_gitignore_excludes_sensitive_files():
    gitignore_path = Path(".gitignore")
    assert gitignore_path.exists()
    content = gitignore_path.read_text(encoding="utf-8")
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.strip().startswith("#")]
    
    # Assert crucial local directories and files are ignored
    assert ".env" in lines
    assert "models/" in lines
    assert "data/" in lines
    assert "assets/private/" in lines
    assert "backups/" in lines
    assert "dist/" in lines
    assert "build/" in lines
    assert "config/api_config.json" in lines

def test_release_packaging_constraints_if_built():
    release_dir = Path("release")
    if release_dir.exists():
        # Only verify the current release pack (v0.49)
        for item in release_dir.iterdir():
            if item.is_dir() and item.name.startswith("DaniyaSummerPet-v0.49"):
                for root, dirs, files in os.walk(item):
                    for file in files:
                        assert not file.endswith(".gguf"), f"Forbidden model file found in release: {file}"
                        assert file != ".env", f"Forbidden secrets file found in release: {file}"
                    for d in dirs:
                        assert d != "models", "Forbidden models directory found in release"
                        assert d != "data", "Forbidden data directory found in release"
                        assert d != "assets/private", "Forbidden private assets directory found in release"

@pytest.mark.skip(reason="_save_local_settings_only 已移除, 本地模型保存已合并到 _save_api_settings + _sync_model_profiles")
def test_gui_saving_and_applying_profile_in_subprocess(tmp_path):
    env = os.environ.copy()
    env["QT_QPA_PLATFORM"] = "offscreen"
    env["DANIYA_RELATION_DATA_DIR"] = str(tmp_path / "relation")
    
    script = rf"""
import os, sys, json
from PySide6.QtWidgets import QApplication
from src.app import AppController
from pathlib import Path
from src.settings_manager import SettingsManager

app = QApplication.instance() or QApplication(sys.argv)
controller = AppController(app)

# Open settings center GUI
controller.open_settings_center()
app.processEvents()

window = controller.settings_window

# Overwrite settings paths to tmp_path
settings_manager = window.settings_manager
settings_manager.root = Path(r"{tmp_path}")
settings_manager.config_dir = Path(r"{tmp_path}") / "config"
settings_manager.env_path = Path(r"{tmp_path}") / ".env"
settings_manager.api_config_path = settings_manager.config_dir / "api_config.json"
settings_manager.model_profiles_path = settings_manager.config_dir / "model_profiles.json"
settings_manager.ensure_configs()

# 1. Test standard api tab save with sensitive key
window.provider_input.setCurrentText("deepseek")
window.base_url_input.setText("https://api.deepseek.com")
window.model_input.setText("deepseek-chat")
window.api_key_input.setText("secret-api-key-123")

window._save_api_settings()
app.processEvents()

# Verify no plain key in api_config.json, but present in .env
api_config = json.loads(settings_manager.api_config_path.read_text(encoding="utf-8"))
assert "secret-api-key-123" not in json.dumps(api_config)
assert "DEEPSEEK_API_KEY=secret-api-key-123" in settings_manager.env_path.read_text(encoding="utf-8")

# 2. Test local model tab save only (without applying yet)
window.local_service_combo.setCurrentText("Ollama")
window.local_base_url.setText("http://localhost:11434")

# Mock the model dropdown value
window.local_model_list.clear()
window.local_model_list.addItem("qwen2.5:0.5b")
window.local_model_list.setCurrentText("qwen2.5:0.5b")

# Save local settings
profile_id = window._save_local_settings_only()
app.processEvents()

# Verify local profile is written to model_profiles.json
profiles_data = json.loads(settings_manager.model_profiles_path.read_text(encoding="utf-8"))
saved_profile = next(p for p in profiles_data["profiles"] if p["id"] == profile_id)
assert saved_profile["name"] == "Ollama qwen2.5:0.5b"
assert saved_profile["base_url"] == "http://localhost:11434"
assert saved_profile["model"] == "qwen2.5:0.5b"

print("SETTINGS_APPLY_OK", flush=True)
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
    assert "SETTINGS_APPLY_OK" in completed.stdout
