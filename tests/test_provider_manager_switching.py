import pytest
from pathlib import Path
from src.llm.provider_manager import ProviderManager
from src.llm.provider_registry import Provider
from src.settings_manager import SettingsManager


class FakeConfigManager:
    def __init__(self) -> None:
        self.config = {"api": {}, "ui": {}, "chat": {}}
    def load_app_config(self):
        return self.config
    def save_app_config(self, value):
        self.config = value


@pytest.fixture
def setup_provider_manager(tmp_path):
    fake = FakeConfigManager()
    settings = SettingsManager(fake, root=tmp_path)
    settings.ensure_configs()

    pm = ProviderManager(api_config={}, system_prompt="Test Daniya", prompt_prefix="Daniya prefix")
    pm.model_profiles_path = tmp_path / "config" / "model_profiles.json"
    pm.reload()
    return pm, tmp_path


def test_switch_active_profile_success(setup_provider_manager, monkeypatch):
    pm, tmp_path = setup_provider_manager
    assert pm.get_active_profile()["id"] == "deepseek_default"
    next(p for p in pm.profiles_data["profiles"] if p["id"] == "ollama_qwen25_05b")["enabled"] = True

    # Mock test_profile_model to return success (returns tuple now)
    monkeypatch.setattr(pm, "test_profile_model", lambda p: (True, "Success"))

    success, msg = pm.switch_active_profile("ollama_qwen25_05b")
    assert success is True
    assert msg == "切换成功"

    assert pm.get_active_profile()["id"] == "ollama_qwen25_05b"

    pm2 = ProviderManager(api_config={})
    pm2.model_profiles_path = tmp_path / "config" / "model_profiles.json"
    pm2.reload()
    assert pm2.get_active_profile()["id"] == "ollama_qwen25_05b"
    assert pm2.profiles_data["profile_history"]["text"][0] == "ollama_qwen25_05b"


def test_switch_active_profile_failure_and_rollback(setup_provider_manager, monkeypatch):
    pm, tmp_path = setup_provider_manager
    assert pm.get_active_profile()["id"] == "deepseek_default"
    next(p for p in pm.profiles_data["profiles"] if p["id"] == "ollama_qwen25_05b")["enabled"] = True

    # Mock test_profile_model to return failure
    monkeypatch.setattr(pm, "test_profile_model", lambda p: (False, "Connection failed"))

    success, msg = pm.switch_active_profile("ollama_qwen25_05b")
    assert success is False
    assert "模型测试未通过: Connection failed" in msg

    assert pm.get_active_profile()["id"] == "deepseek_default"


def test_switch_active_profile_does_not_touch_other_capability_slots(setup_provider_manager, monkeypatch):
    pm, tmp_path = setup_provider_manager
    next(p for p in pm.profiles_data["profiles"] if p["id"] == "ollama_qwen25_05b")["enabled"] = True
    pm.profiles_data["active_tts_profile_id"] = "tts_voice_profile"
    pm.profiles_data["profile_history"] = {"tts": ["tts_voice_profile"], "text": ["deepseek_default"]}
    monkeypatch.setattr(pm, "test_profile_model", lambda p: (True, "Success"))

    success, _msg = pm.switch_active_profile("ollama_qwen25_05b")

    assert success is True
    assert pm.profiles_data["active_text_profile_id"] == "ollama_qwen25_05b"
    assert pm.profiles_data["active_tts_profile_id"] == "tts_voice_profile"
    assert pm.profiles_data["profile_history"]["tts"] == ["tts_voice_profile"]


def test_switch_active_profile_rejects_disabled_profile(setup_provider_manager, monkeypatch):
    pm, _tmp_path = setup_provider_manager
    profiles = pm.profiles_data["profiles"]
    target = next(p for p in profiles if p["id"] == "ollama_qwen25_05b")
    target["enabled"] = False

    def fail_if_called(_profile):
        raise AssertionError("disabled profile should not be tested")

    monkeypatch.setattr(pm, "test_profile_model", fail_if_called)

    success, msg = pm.switch_active_profile("ollama_qwen25_05b")

    assert success is False
    assert "已停用" in msg
    assert pm.profiles_data["active_text_profile_id"] == "deepseek_default"


def test_chat_error_fallback_handling(setup_provider_manager, monkeypatch):
    pm, tmp_path = setup_provider_manager
    active_profile = pm.get_active_profile()
    assert active_profile["id"] == "deepseek_default"

    # Mock the deepseek_api boundary module's chat to raise an error
    import src.llm.boundaries.deepseek_api as ds_api
    def mock_chat(messages, api_key, base_url="", model="", max_tokens=360, timeout=20):
        raise RuntimeError("API Timeout")

    monkeypatch.setattr(ds_api, "chat", mock_chat)

    response, source = pm.chat([{"role": "user", "content": "hello"}])

    assert source == "local"
    assert "达妮娅刚刚走神了一下" in response

    assert pm.last_source == "local_fallback"
    assert "API Timeout" in pm.last_error


def test_prompt_to_messages_keeps_user_memory_prefix_for_provider_channels(setup_provider_manager):
    pm, _tmp_path = setup_provider_manager
    pm.system_prompt = "达妮娅基础设定"
    pm.prompt_prefix = "用户档案：\n称呼：小夏\n\n达妮娅记忆备忘录：\n- 喜欢安静陪伴"

    for active_id in ("deepseek_default", "ollama_qwen25_05b", "openai_compatible_default"):
        pm.profiles_data["active_text_profile_id"] = active_id
        messages = pm.prompt_to_messages("你好", history_messages=[{"role": "assistant", "content": "嗯。"}])

        assert messages[0]["role"] == "system"
        assert "称呼：小夏" in messages[0]["content"]
        assert "达妮娅记忆备忘录" in messages[0]["content"]
        assert "喜欢安静陪伴" in messages[0]["content"]
        assert "达妮娅基础设定" in messages[0]["content"]
        assert messages[-1] == {"role": "user", "content": "你好"}


def test_openai_compatible_api_key_auth_header_is_forwarded(setup_provider_manager, monkeypatch):
    pm, tmp_path = setup_provider_manager
    pm.env_path = tmp_path / ".env"
    pm.env_path.write_text("OPENAI_COMPATIBLE_API_KEY=fake-secret\n", encoding="utf-8")
    pm.profiles_data = {
        "active_text_profile_id": "openai_compatible_default",
        "profiles": [
            {
                "id": "openai_compatible_default",
                "provider": Provider.OPENAI_COMPATIBLE,
                "base_url": "https://api.xiaomimimo.com/v1",
                "model": "mimo-v2.5",
                "api_key_env": "OPENAI_COMPATIBLE_API_KEY",
                "auth_header": "api-key",
                "max_tokens": 16,
                "timeout": 8,
                "source": "cloud",
            }
        ],
    }
    captured = {}

    def mock_chat(messages, api_key, base_url="", model="", auth_header="bearer", max_tokens=360, timeout=20):
        captured.update(
            {
                "api_key": api_key,
                "base_url": base_url,
                "model": model,
                "auth_header": auth_header,
            }
        )
        return "OK"

    import src.llm.boundaries.openai_api as openai_boundary

    monkeypatch.setattr(openai_boundary, "chat", mock_chat)

    response, source = pm.chat([{"role": "user", "content": "hello"}])

    assert response == "OK"
    assert source == "api"
    assert captured == {
        "api_key": "fake-secret",
        "base_url": "https://api.xiaomimimo.com/v1",
        "model": "mimo-v2.5",
        "auth_header": "api-key",
    }


def test_openai_compatible_profile_test_forwards_auth_header(setup_provider_manager, monkeypatch):
    pm, tmp_path = setup_provider_manager
    pm.env_path = tmp_path / ".env"
    pm.env_path.write_text("OPENAI_COMPATIBLE_API_KEY=fake-secret\n", encoding="utf-8")
    profile = {
        "id": "openai_compatible_default",
        "provider": Provider.OPENAI_COMPATIBLE,
        "base_url": "https://api.xiaomimimo.com/v1",
        "model": "mimo-v2.5",
        "api_key_env": "OPENAI_COMPATIBLE_API_KEY",
        "auth_header": "api-key",
        "source": "cloud",
        "capabilities": ["text"],
    }
    captured = {}

    def mock_test_connection(api_key, base_url="", model="", auth_header="bearer", timeout=8):
        captured.update(
            {
                "api_key": api_key,
                "base_url": base_url,
                "model": model,
                "auth_header": auth_header,
                "timeout": timeout,
            }
        )
        return True

    import src.llm.boundaries.openai_api as openai_boundary

    monkeypatch.setattr(openai_boundary, "test_connection", mock_test_connection)

    ok, msg = pm.test_profile_model(profile)

    assert ok is True
    assert msg == "连接成功"
    assert captured == {
        "api_key": "fake-secret",
        "base_url": "https://api.xiaomimimo.com/v1",
        "model": "mimo-v2.5",
        "auth_header": "api-key",
        "timeout": 8,
    }
