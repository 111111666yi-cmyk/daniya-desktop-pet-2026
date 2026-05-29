import json
import pytest
from pathlib import Path
from src.settings_manager import SettingsManager

class FakeConfigManager:
    def __init__(self) -> None:
        self.config = {
            "window": {"always_on_top": True, "opacity_percent": 100},
            "pet": {"pet_height": 96, "target_height": 96, "min_pet_height": 80, "max_pet_height": 160},
            "api": {},
            "ui": {},
        }

    def load_app_config(self):
        return self.config

    def save_app_config(self, value):
        self.config = value


def test_model_profiles_initialization_and_loading(tmp_path):
    fake = FakeConfigManager()
    manager = SettingsManager(fake, root=tmp_path)
    
    # Assert model_profiles.json was created
    profiles_file = tmp_path / "config" / "model_profiles.json"
    assert profiles_file.exists()
    
    # Load and check loaded contents
    loaded = manager.load_model_profiles()
    assert loaded["active_text_profile_id"] == "deepseek_default"
    assert len(loaded["profiles"]) >= 3
    
    # Check default profile details
    deepseek_profile = next(p for p in loaded["profiles"] if p["id"] == "deepseek_default")
    assert deepseek_profile["provider"] == "deepseek"
    assert deepseek_profile["source"] == "cloud"


def test_model_profiles_broken_json_fallback(tmp_path):
    fake = FakeConfigManager()
    manager = SettingsManager(fake, root=tmp_path)
    
    profiles_file = tmp_path / "config" / "model_profiles.json"
    # Write invalid json
    profiles_file.write_text("invalid json content {", encoding="utf-8")
    
    # Loading should automatically detect corruption, back it up and return default profiles
    loaded = manager.load_model_profiles()
    assert loaded["active_text_profile_id"] == "deepseek_default"
    
    # Check that backup file with suffix ".broken-..." was created
    broken_files = list(profiles_file.parent.glob("model_profiles.json.broken-*"))
    assert len(broken_files) > 0


def test_model_profiles_sanitization_on_save(tmp_path):
    fake = FakeConfigManager()
    manager = SettingsManager(fake, root=tmp_path)
    
    test_profiles = {
        "active_text_profile_id": "custom_profile",
        "profiles": [
            {
                "id": "custom_profile",
                "name": "Custom Profile",
                "provider": "custom_openai_compatible",
                "api_key": "some-secret-key-to-strip",
                "api_key_masked": "some-masked-key-to-strip",
                "api_key_env": "CUSTOM_API_KEY",
                "base_url": "http://localhost:8000",
                "model": "qwen"
            }
        ]
    }
    
    manager.save_model_profiles(test_profiles)
    
    # Verify file content does not contain api_key or api_key_masked
    profiles_file = tmp_path / "config" / "model_profiles.json"
    file_content = json.loads(profiles_file.read_text(encoding="utf-8"))
    
    custom_profile = file_content["profiles"][0]
    assert "api_key" not in custom_profile
    assert "api_key_masked" not in custom_profile
    assert custom_profile["id"] == "custom_profile"
