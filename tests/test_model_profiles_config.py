import json
import pytest
from pathlib import Path
from src.settings_manager import SettingsManager
from src.llm.provider_registry import Provider

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

    zai_profile = next(p for p in loaded["profiles"] if p["id"] == "zai_default")
    assert zai_profile["provider"] == Provider.ZAI
    assert zai_profile["base_url"] == "https://api.z.ai/api/paas/v4"
    assert zai_profile["model"] == "glm-5.1"
    assert zai_profile["api_key_env"] == "ZAI_API_KEY"


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


def test_mimo_openai_compatible_profile_uses_api_key_auth_header(tmp_path):
    fake = FakeConfigManager()
    manager = SettingsManager(fake, root=tmp_path)

    manager.save_api_settings(
        provider=Provider.OPENAI_COMPATIBLE,
        base_url="https://api.xiaomimimo.com/v1",
        model="mimo-v2.5",
        api_key="fake-secret",
        auth_header="bearer",
        activate=False,
    )

    profiles = json.loads((tmp_path / "config" / "model_profiles.json").read_text(encoding="utf-8"))
    profile = next(p for p in profiles["profiles"] if p["id"] == "openai_compatible_default")
    assert profile["auth_header"] == "api-key"
    assert profiles["active_text_profile_id"] == "deepseek_default"

    api_config = json.loads((tmp_path / "config" / "api_config.json").read_text(encoding="utf-8"))
    assert api_config["active_provider"] == Provider.DEEPSEEK
    assert api_config["providers"][Provider.OPENAI_COMPATIBLE]["auth_header"] == "api-key"
    assert "fake-secret" not in json.dumps(api_config)
    assert "OPENAI_COMPATIBLE_API_KEY=fake-secret" in (tmp_path / ".env").read_text(encoding="utf-8")


def test_activate_text_profile_validates_and_syncs_active_provider(tmp_path, monkeypatch):
    fake = FakeConfigManager()
    manager = SettingsManager(fake, root=tmp_path)
    manager.save_api_settings(
        provider=Provider.OPENAI_COMPATIBLE,
        base_url="https://api.xiaomimimo.com/v1",
        model="mimo-v2.5",
        api_key="fake-secret",
        auth_header="bearer",
        activate=False,
    )

    import src.llm.boundaries.openai_api as openai_boundary

    monkeypatch.setattr(openai_boundary, "test_connection", lambda **_kwargs: True)

    ok, msg = manager.activate_text_profile("openai_compatible_default")

    assert ok is True
    assert msg == "切换成功"
    profiles = manager.load_model_profiles()
    assert profiles["active_text_profile_id"] == "openai_compatible_default"
    assert profiles["profile_history"]["text"][0] == "openai_compatible_default"
    api_config = manager.load_api_config()
    assert api_config["active_provider"] == Provider.OPENAI_COMPATIBLE


def test_save_local_model_profile_does_not_activate_until_validated(tmp_path):
    fake = FakeConfigManager()
    manager = SettingsManager(fake, root=tmp_path)

    manager.save_local_model_profile(
        provider=Provider.OLLAMA,
        base_url="http://localhost:11434",
        model="qwen2.5:0.5b",
        service_label="Ollama",
    )

    profiles = manager.load_model_profiles()
    assert profiles["active_text_profile_id"] == "deepseek_default"
    saved = next(p for p in profiles["profiles"] if p["id"] == "ollama_qwen2_5_0_5b")
    assert saved["enabled"] is True


def test_set_profile_enabled_refuses_active_text_profile(tmp_path):
    fake = FakeConfigManager()
    manager = SettingsManager(fake, root=tmp_path)

    ok, msg = manager.set_profile_enabled("deepseek_default", False, slot="text")

    assert ok is False
    assert "当前生效模型不能停用" in msg
    profile = next(p for p in manager.load_model_profiles()["profiles"] if p["id"] == "deepseek_default")
    assert profile["enabled"] is True
