"""Provider Registry 单元测试 — 验证 normalize / metadata / constants。"""

from __future__ import annotations

import pytest
from src.llm.provider_registry import Provider, ProviderMeta


class TestProviderConstants:
    def test_all_cloud_contains_standard_keys(self) -> None:
        clouds = Provider.all_cloud()
        assert Provider.DEEPSEEK in clouds
        assert Provider.OPENAI in clouds
        assert Provider.CLAUDE in clouds

    def test_all_local_contains_standard_keys(self) -> None:
        locals_ = Provider.all_local()
        assert Provider.OLLAMA in locals_
        assert Provider.LM_STUDIO in locals_
        assert Provider.LLAMA_CPP in locals_

    def test_aliases_are_valid(self) -> None:
        for alias, canonical in Provider._ALIASES.items():
            meta = ProviderMeta.get(canonical)
            assert meta is not None, f"Alias {alias} → {canonical} has no metadata"


class TestProviderMetaNormalize:
    def test_exact_key_passthrough(self) -> None:
        assert ProviderMeta.normalize("deepseek") == Provider.DEEPSEEK
        assert ProviderMeta.normalize("openai") == Provider.OPENAI
        assert ProviderMeta.normalize("claude") == Provider.CLAUDE
        assert ProviderMeta.normalize("ollama") == Provider.OLLAMA

    def test_alias_anthropic_to_claude(self) -> None:
        assert ProviderMeta.normalize("anthropic") == Provider.CLAUDE
        assert ProviderMeta.normalize("ANTHROPIC") == Provider.CLAUDE

    def test_alias_openai_compatible_local(self) -> None:
        assert ProviderMeta.normalize("openai-compatible local") == Provider.LOCAL_OPENAI_COMPATIBLE
        assert ProviderMeta.normalize("openai-compatible local ") == Provider.LOCAL_OPENAI_COMPATIBLE

    def test_alias_llama_cpp(self) -> None:
        assert ProviderMeta.normalize("llama.cpp server") == Provider.LLAMA_CPP
        assert ProviderMeta.normalize("llama.cpp") == Provider.LLAMA_CPP

    def test_alias_lm_studio(self) -> None:
        assert ProviderMeta.normalize("lm studio") == Provider.LM_STUDIO
        assert ProviderMeta.normalize("LM Studio") == Provider.LM_STUDIO

    def test_alias_custom(self) -> None:
        assert ProviderMeta.normalize("custom") == Provider.LOCAL_OPENAI_COMPATIBLE

    def test_empty_string(self) -> None:
        assert ProviderMeta.normalize("") == Provider.LOCAL_OPENAI_COMPATIBLE

    def test_unknown_passthrough(self) -> None:
        assert ProviderMeta.normalize("some_unknown_provider") == Provider.LOCAL_OPENAI_COMPATIBLE


class TestProviderMetaGetters:
    def test_display_name(self) -> None:
        assert ProviderMeta.get_display_name(Provider.DEEPSEEK) == "DeepSeek"
        assert ProviderMeta.get_display_name(Provider.OPENAI) == "OpenAI"
        assert ProviderMeta.get_display_name(Provider.OLLAMA) == "Ollama"

    def test_default_url(self) -> None:
        assert ProviderMeta.get_default_url(Provider.DEEPSEEK) == "https://api.deepseek.com"
        assert ProviderMeta.get_default_url(Provider.OLLAMA) == "http://localhost:11434"

    def test_default_model(self) -> None:
        assert ProviderMeta.get_default_model(Provider.DEEPSEEK) == "deepseek-chat"
        assert ProviderMeta.get_default_model(Provider.OPENAI) == "gpt-4.1-mini"

    def test_api_key_env(self) -> None:
        assert ProviderMeta.get_api_key_env(Provider.DEEPSEEK) == "DEEPSEEK_API_KEY"
        assert ProviderMeta.get_api_key_env(Provider.OPENAI) == "OPENAI_API_KEY"
        assert ProviderMeta.get_api_key_env(Provider.OPENAI_COMPATIBLE) == "OPENAI_COMPATIBLE_API_KEY"
        assert ProviderMeta.get_api_key_env(Provider.OLLAMA) == ""

    def test_auth_header(self) -> None:
        assert ProviderMeta.get_auth_header(Provider.DEEPSEEK) == "bearer"
        assert ProviderMeta.get_auth_header(Provider.OPENAI_COMPATIBLE) == "bearer"
        assert ProviderMeta.get_auth_header(Provider.OLLAMA) == ""

    def test_source_classification(self) -> None:
        assert ProviderMeta.is_cloud(Provider.DEEPSEEK) is True
        assert ProviderMeta.is_cloud(Provider.OPENAI) is True
        assert ProviderMeta.is_cloud(Provider.CLAUDE) is True
        assert ProviderMeta.is_cloud(Provider.OLLAMA) is False
        assert ProviderMeta.is_local(Provider.OLLAMA) is True
        assert ProviderMeta.is_local(Provider.LM_STUDIO) is True

    def test_timeout(self) -> None:
        assert ProviderMeta.get_timeout(Provider.DEEPSEEK) == 30
        assert ProviderMeta.get_timeout(Provider.OPENAI) == 30
        assert ProviderMeta.get_timeout(Provider.LM_STUDIO) == 60

    def test_max_tokens(self) -> None:
        assert ProviderMeta.get_max_tokens(Provider.CLAUDE) == 4096
        assert ProviderMeta.get_max_tokens(Provider.DEEPSEEK) == 4096

    def test_all_display_names(self) -> None:
        names = ProviderMeta.all_display_names()
        assert names[Provider.DEEPSEEK] == "DeepSeek"
        assert names[Provider.OPENAI] == "OpenAI"

    def test_api_style(self) -> None:
        assert ProviderMeta.get_api_style(Provider.DEEPSEEK) == "openai_compatible"
        assert ProviderMeta.get_api_style(Provider.OLLAMA) == "ollama"
        assert ProviderMeta.get_api_style(Provider.CLAUDE) == "anthropic"


class TestProviderMetaServiceLabels:
    def test_all_service_labels(self) -> None:
        labels = ProviderMeta.all_service_labels()
        assert "Ollama" in labels
        assert "LM Studio" in labels
        assert "llama.cpp server" in labels
        assert "OpenAI-compatible local" in labels
        assert "Custom" in labels
        assert len(labels) == 5

    def test_service_label_to_key(self) -> None:
        assert ProviderMeta.service_label_to_key("Ollama") == Provider.OLLAMA
        assert ProviderMeta.service_label_to_key("LM Studio") == Provider.LM_STUDIO
        assert ProviderMeta.service_label_to_key("llama.cpp server") == Provider.LLAMA_CPP
        assert ProviderMeta.service_label_to_key("Custom") == Provider.LOCAL_OPENAI_COMPATIBLE
        assert ProviderMeta.service_label_to_key("OpenAI-compatible local") == Provider.LOCAL_OPENAI_COMPATIBLE


class TestProviderMetaMakeProfileId:
    def test_cloud_default(self) -> None:
        assert ProviderMeta.make_profile_id(Provider.DEEPSEEK) == "deepseek_default"
        assert ProviderMeta.make_profile_id(Provider.OPENAI) == "openai_default"

    def test_local_with_model(self) -> None:
        pid = ProviderMeta.make_profile_id(Provider.OLLAMA, "qwen2.5:0.5b")
        assert pid == "ollama_qwen2_5_0_5b"

    def test_model_with_slashes(self) -> None:
        pid = ProviderMeta.make_profile_id(Provider.OLLAMA, "library/qwen2.5:0.5b")
        assert pid == "ollama_library_qwen2_5_0_5b"

    def test_normalize_first(self) -> None:
        pid = ProviderMeta.make_profile_id("anthropic", "claude-3")
        assert pid == "claude_claude-3"


class TestProviderMetaRoundTrip:
    """验证 normalize → get 的往返一致性。"""

    def test_normalize_then_get(self) -> None:
        for key in Provider.all_cloud() + Provider.all_local():
            normalized = ProviderMeta.normalize(key)
            meta = ProviderMeta.get(normalized)
            assert meta is not None
            assert meta["key"] == key, f"Round-trip failed for {key}"

    def test_alias_round_trip(self) -> None:
        for alias, canonical in Provider._ALIASES.items():
            normalized = ProviderMeta.normalize(alias)
            assert normalized == canonical, f"Alias {alias} normalized to {normalized}, expected {canonical}"

    def test_service_label_round_trip(self) -> None:
        for label in ProviderMeta.all_service_labels():
            key = ProviderMeta.service_label_to_key(label)
            meta = ProviderMeta.get(key)
            assert meta is not None, f"Service label '{label}' → key '{key}' has no metadata"
