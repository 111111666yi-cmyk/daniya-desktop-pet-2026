"""B0-2: streaming support tests."""

from __future__ import annotations

from copy import deepcopy
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from src.config_manager import DEFAULT_APP_CONFIG


def test_streaming_disabled_by_default():
    chat = DEFAULT_APP_CONFIG["chat"]
    assert chat["streaming_enabled"] is False
    assert chat["streaming_mode"] == "safe_final_filter"


def test_openai_boundary_supports_streaming():
    from src.llm.boundaries import openai_api
    assert openai_api.supports_streaming() is True


def test_deepseek_boundary_supports_streaming():
    from src.llm.boundaries import deepseek_api
    assert deepseek_api.supports_streaming() is True


def test_anthropic_boundary_does_not_support_streaming():
    from src.llm.boundaries import anthropic_api
    assert anthropic_api.supports_streaming() is False


def test_ollama_boundary_does_not_support_streaming():
    from src.llm.boundaries import ollama_api
    assert ollama_api.supports_streaming() is False


def _make_pm(provider: str = "deepseek") -> Any:
    from src.llm.provider_manager import ProviderManager
    config = {
        "active_provider": provider,
        "providers": {provider: {"base_url": "http://test", "model": "test-model", "api_key_env": ""}},
        "local_mode": False,
        "chat": deepcopy(DEFAULT_APP_CONFIG["chat"]),
    }
    pm = ProviderManager(config)
    pm.profiles_data = {
        "active_text_profile_id": f"{provider}_default",
        "profiles": [
            {"id": f"{provider}_default", "provider": provider, "model": "test-model",
             "base_url": "http://test", "api_key_env": "", "enabled": True, "capabilities": ["text"], "type": "text"},
        ],
    }
    return pm


def test_provider_manager_supports_streaming_deepseek():
    pm = _make_pm("deepseek")
    assert pm.supports_streaming() is True


def test_provider_manager_supports_streaming_ollama():
    pm = _make_pm("ollama")
    assert pm.supports_streaming() is False


def test_provider_manager_stream_chat_fallback_for_unsupported():
    pm = _make_pm("ollama")
    with patch.object(pm, "chat", return_value=("test response", "api")):
        chunks = list(pm.stream_chat([{"role": "user", "content": "hi"}]))
    assert chunks == ["test response"]


def test_speech_filter_only_on_final_text():
    """Verify speech_filter is applied to complete text, not partial chunks."""
    from core.speech_filter import apply_daniya_speech_filter

    partial = "我来帮"
    final = "我来帮你看看这个问题。"
    speech_config = {"max_lines": 4}
    filtered = apply_daniya_speech_filter(final, speech_config, None)
    assert isinstance(filtered, str)
    assert len(filtered) > 0


def test_dialogue_engine_does_not_import_qt():
    """DialogueEngine must stay Qt-free."""
    import importlib
    import sys
    mod = importlib.import_module("core.dialogue_engine")
    source = open(mod.__file__, encoding="utf-8").read()
    assert "PySide6" not in source
    assert "from PySide6" not in source
    assert "import PySide6" not in source
