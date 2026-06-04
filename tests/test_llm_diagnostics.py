import pytest
from unittest.mock import MagicMock
from src.llm.provider_manager import ProviderManager
from src.diagnostics_panel import run_diagnostics

def test_llm_diagnostics_tracking():
    # Mock api_config
    api_config = {
        "chat": {
            "fallback_reply": "Fallback reply test",
            "fallback_replies": ["Fallback reply test"],
            "api_error_fallback_reply": "Fallback reply test",
            "api_error_fallback_replies": ["Fallback reply test"]
        }
    }
    
    # Instantiate ProviderManager
    pm = ProviderManager(api_config=api_config)
    
    # Mock get_active_profile
    pm.get_active_profile = MagicMock(return_value={
        "provider": "deepseek",
        "model": "deepseek-chat",
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "source": "cloud"
    })
    
    # Mock deepseek_api.chat to raise an exception to trigger fallback
    from src.llm.boundaries import deepseek_api
    original_chat = deepseek_api.chat
    deepseek_api.chat = MagicMock(side_effect=ValueError("Test connection error"))
    
    try:
        reply, source = pm.chat([{"role": "user", "content": "hello"}])
        
        assert reply == "Fallback reply test"
        assert source == "local"
        assert pm.last_provider == "deepseek"
        assert pm.last_model == "deepseek-chat"
        assert pm.fallback_used is True
        assert "Test connection error" in pm.fallback_reason
        assert pm.last_error_type == "ValueError"
        assert "Test connection error" in pm.last_error_traceback
    finally:
        deepseek_api.chat = original_chat

def test_run_diagnostics_with_chat_client():
    # Mock settings, asset manager, and chat client
    settings = MagicMock()
    settings.load_api_config.return_value = {
        "active_provider": "deepseek",
        "providers": {
            "deepseek": {
                "model": "deepseek-chat",
                "api_key_env": "DEEPSEEK_API_KEY",
                "api_key_masked": "sk-****"
            }
        }
    }
    settings.current_api_key.return_value = ""
    settings.test_api_connection.return_value = (False, "mocked fail")
    
    assets = MagicMock()
    assets.manifest.return_value = {"animations": {}}
    
    pm = MagicMock()
    pm.last_provider = "deepseek"
    pm.last_model = "deepseek-chat"
    pm.fallback_used = True
    pm.fallback_reason = "Connection Timeout"
    pm.last_error_type = "TimeoutError"
    pm.last_error_traceback = "Traceback lines here"
    
    chat_client = MagicMock()
    chat_client.provider_manager = pm
    
    results = run_diagnostics(settings_manager=settings, asset_manager=assets, chat_client=chat_client)
    
    # Find the LLM runtime check in results
    llm_check = next((r for r in results if r["name"] == "LLM 运行时状态"), None)
    assert llm_check is not None
    assert llm_check["status"] == "warn"
    assert "deepseek-chat" in llm_check["message"]
    assert "TimeoutError" in llm_check["message"]
    assert "Traceback lines here" in llm_check["message"]
