"""Provider Registry — 统一的 Provider 常量与元数据中心。

这是整个项目中所有 Provider 相关字符串的 **唯一来源**。
任何需要引用 Provider 名称、默认 URL、默认模型、API 风格的代码，
都必须从这里导入，禁止在其他文件中硬编码字符串字面量。

使用方式:
    from src.llm.provider_registry import Provider, ProviderMeta

    # 常量引用（避免拼写错误）
    key = Provider.DEEPSEEK          # "deepseek"
    key = Provider.OLLAMA            # "ollama"

    # 元数据查询
    display = ProviderMeta.get_display_name(key)   # "DeepSeek"
    url = ProviderMeta.get_default_url(key)        # "https://api.deepseek.com"
    model = ProviderMeta.get_default_model(key)    # "deepseek-chat"

    # 标准化（处理别名）
    canonical = ProviderMeta.normalize("anthropic")  # "claude"
    canonical = ProviderMeta.normalize("openai_compatible")  # "openai_compatible"

    # 分类查询
    clouds = ProviderMeta.cloud_providers()   # ["deepseek", "openai", "claude"]
    locals_ = ProviderMeta.local_providers()  # ["ollama", "lm_studio", ...]
"""

from __future__ import annotations

from typing import Any


# ── Provider Key Constants ────────────────────────────────────────

class Provider:
    """所有 Provider 的标准化键名常量。"""

    # 云端
    DEEPSEEK: str = "deepseek"
    OPENAI: str = "openai"
    CLAUDE: str = "claude"
    GEMINI: str = "gemini"
    MISTRAL: str = "mistral"
    GROQ: str = "groq"
    CUSTOM: str = "custom_cloud"

    # 本地
    OLLAMA: str = "ollama"
    LM_STUDIO: str = "lm_studio"
    LLAMA_CPP: str = "llama_cpp"
    LOCAL_OPENAI_COMPATIBLE: str = "local_openai_compatible"

    # 通用兼容
    OPENAI_COMPATIBLE: str = "openai_compatible"

    _ALIASES: dict[str, str] = {
        "anthropic": "claude",
        "google": "gemini",
        "gemini": "gemini",
        "mistral": "mistral",
        "groq": "groq",
        "openai-compatible local": "local_openai_compatible",
        "openai-compatible": "openai_compatible",
        "llama.cpp server": "llama_cpp",
        "llama.cpp": "llama_cpp",
        "lm studio": "lm_studio",
        "custom": "local_openai_compatible",
        "custom_cloud": "custom_cloud",
    }

    @classmethod
    def all_cloud(cls) -> list[str]:
        return [cls.DEEPSEEK, cls.OPENAI, cls.CLAUDE, cls.GEMINI, cls.MISTRAL, cls.GROQ, cls.CUSTOM]

    @classmethod
    def all_local(cls) -> list[str]:
        return [cls.OLLAMA, cls.LM_STUDIO, cls.LLAMA_CPP, cls.LOCAL_OPENAI_COMPATIBLE]

    @classmethod
    def all_standard(cls) -> list[str]:
        return cls.all_cloud() + cls.all_local()


# ── Provider Metadata ─────────────────────────────────────────────

# 每个 Provider 的完整元数据（单点维护）
_PROVIDER_META: dict[str, dict[str, Any]] = {
    Provider.DEEPSEEK: {
        "key": Provider.DEEPSEEK,
        "display_name": "DeepSeek",
        "base_url": "https://api.deepseek.com",
        "default_model": "deepseek-chat",
        "api_key_env": "DEEPSEEK_API_KEY",
        "auth_header": "bearer",
        "api_style": "openai_compatible",
        "source": "cloud",
        "timeout": 30,
        "max_tokens": 4096,
        "capabilities": ["text"],
    },
    Provider.OPENAI: {
        "key": Provider.OPENAI,
        "display_name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4.1-mini",
        "api_key_env": "OPENAI_API_KEY",
        "auth_header": "bearer",
        "api_style": "openai_compatible",
        "source": "cloud",
        "timeout": 30,
        "max_tokens": 4096,
        "capabilities": ["text"],
    },
    Provider.CLAUDE: {
        "key": Provider.CLAUDE,
        "display_name": "Claude (Anthropic)",
        "base_url": "https://api.anthropic.com/v1",
        "default_model": "claude-sonnet-4-6",
        "api_key_env": "ANTHROPIC_API_KEY",
        "auth_header": "x-api-key",
        "api_style": "anthropic",
        "source": "cloud",
        "timeout": 30,
        "max_tokens": 4096,
        "capabilities": ["text"],
    },
    Provider.GEMINI: {
        "key": Provider.GEMINI,
        "display_name": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "default_model": "gemini-2.5-flash",
        "api_key_env": "GEMINI_API_KEY",
        "auth_header": "bearer",
        "api_style": "openai_compatible",
        "source": "cloud",
        "timeout": 30,
        "max_tokens": 4096,
        "capabilities": ["text", "vision"],
    },
    Provider.MISTRAL: {
        "key": Provider.MISTRAL,
        "display_name": "Mistral AI",
        "base_url": "https://api.mistral.ai/v1",
        "default_model": "mistral-large-latest",
        "api_key_env": "MISTRAL_API_KEY",
        "auth_header": "bearer",
        "api_style": "openai_compatible",
        "source": "cloud",
        "timeout": 30,
        "max_tokens": 4096,
        "capabilities": ["text"],
    },
    Provider.GROQ: {
        "key": Provider.GROQ,
        "display_name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-4-maverick-17b-128e-instruct",
        "api_key_env": "GROQ_API_KEY",
        "auth_header": "bearer",
        "api_style": "openai_compatible",
        "source": "cloud",
        "timeout": 30,
        "max_tokens": 4096,
        "capabilities": ["text"],
    },
    Provider.CUSTOM: {
        "key": Provider.CUSTOM,
        "display_name": "自定义云端 (Custom)",
        "base_url": "",
        "default_model": "",
        "api_key_env": "CUSTOM_API_KEY",
        "auth_header": "bearer",
        "api_style": "openai_compatible",
        "source": "cloud",
        "timeout": 30,
        "max_tokens": 512,
        "capabilities": ["text"],
    },
    Provider.OLLAMA: {
        "key": Provider.OLLAMA,
        "display_name": "Ollama",
        "base_url": "http://localhost:11434",
        "default_model": "",
        "api_key_env": "",
        "auth_header": "",
        "api_style": "ollama",
        "source": "local",
        "timeout": 20,
        "max_tokens": 360,
        "capabilities": ["text"],
    },
    Provider.LM_STUDIO: {
        "key": Provider.LM_STUDIO,
        "display_name": "LM Studio",
        "base_url": "http://localhost:1234/v1",
        "default_model": "local-model",
        "api_key_env": "",
        "auth_header": "",
        "api_style": "openai_compatible",
        "source": "local",
        "timeout": 60,
        "max_tokens": 512,
        "capabilities": ["text"],
    },
    Provider.LLAMA_CPP: {
        "key": Provider.LLAMA_CPP,
        "display_name": "llama.cpp",
        "base_url": "http://localhost:8080/v1",
        "default_model": "local-model",
        "api_key_env": "",
        "auth_header": "",
        "api_style": "openai_compatible",
        "source": "local",
        "timeout": 60,
        "max_tokens": 512,
        "capabilities": ["text"],
    },
    Provider.LOCAL_OPENAI_COMPATIBLE: {
        "key": Provider.LOCAL_OPENAI_COMPATIBLE,
        "display_name": "OpenAI-Compatible Local",
        "base_url": "http://localhost:1234/v1",
        "default_model": "local-model",
        "api_key_env": "OPENAI_COMPATIBLE_API_KEY",
        "auth_header": "bearer",
        "api_style": "openai_compatible",
        "source": "local",
        "timeout": 60,
        "max_tokens": 512,
        "capabilities": ["text"],
    },
    Provider.OPENAI_COMPATIBLE: {
        "key": Provider.OPENAI_COMPATIBLE,
        "display_name": "OpenAI-Compatible",
        "base_url": "https://...",
        "default_model": "",
        "api_key_env": "OPENAI_COMPATIBLE_API_KEY",
        "auth_header": "bearer",
        "api_style": "openai_compatible",
        "source": "cloud",
        "timeout": 20,
        "max_tokens": 360,
        "capabilities": ["text"],
    },
}


class ProviderMeta:
    """Provider 元数据查询工具。

    所有方法都是类方法，无需实例化。数据源 `_PROVIDER_META` 是本模块内唯一需要维护的字典。
    """

    @classmethod
    def normalize(cls, raw: str) -> str:
        """将任意字符串标准化为规范 Provider key。

        处理流程：
        1. 去除首尾空白
        2. 检查原始形式的别名映射表（空格保留）
        3. 转小写 + 空格替换为下划线，再查别名映射表
        4. 检查是否是已知 key
        5. 兜底返回 local_openai_compatible
        """
        if not raw:
            return Provider.LOCAL_OPENAI_COMPATIBLE
        stripped = raw.strip()
        # 别名检查：先检查原始形式，再检查规范化形式
        lower_original = stripped.lower()
        if lower_original in Provider._ALIASES:
            return Provider._ALIASES[lower_original]
        cleaned = lower_original.replace(" ", "_")
        if cleaned in Provider._ALIASES:
            return Provider._ALIASES[cleaned]
        # 已知 key 直接返回
        if cleaned in _PROVIDER_META:
            return cleaned
        # 已知 key 的 display_name 匹配
        for key, meta in _PROVIDER_META.items():
            if meta.get("display_name", "").lower() == cleaned:
                return key
        # 兜底
        return Provider.LOCAL_OPENAI_COMPATIBLE

    @classmethod
    def get(cls, key: str) -> dict[str, Any]:
        """获取 Provider 完整元数据。key 会自动 normalize。"""
        key = cls.normalize(key)
        return _PROVIDER_META.get(key, _PROVIDER_META[Provider.LOCAL_OPENAI_COMPATIBLE])

    @classmethod
    def get_display_name(cls, key: str) -> str:
        return str(cls.get(key).get("display_name", key))

    @classmethod
    def get_default_url(cls, key: str) -> str:
        return str(cls.get(key).get("base_url", ""))

    @classmethod
    def get_default_model(cls, key: str) -> str:
        return str(cls.get(key).get("default_model", ""))

    @classmethod
    def get_api_key_env(cls, key: str) -> str:
        return str(cls.get(key).get("api_key_env", ""))

    @classmethod
    def get_auth_header(cls, key: str) -> str:
        return str(cls.get(key).get("auth_header", "bearer"))

    @classmethod
    def get_api_style(cls, key: str) -> str:
        return str(cls.get(key).get("api_style", "openai_compatible"))

    @classmethod
    def get_timeout(cls, key: str) -> int:
        return int(cls.get(key).get("timeout", 20))

    @classmethod
    def get_max_tokens(cls, key: str) -> int:
        return int(cls.get(key).get("max_tokens", 360))

    @classmethod
    def is_local(cls, key: str) -> bool:
        return cls.get(key).get("source") == "local"

    @classmethod
    def is_cloud(cls, key: str) -> bool:
        return cls.get(key).get("source") == "cloud"

    @classmethod
    def get_source(cls, key: str) -> str:
        return str(cls.get(key).get("source", "cloud"))

    @classmethod
    def cloud_providers(cls) -> list[str]:
        return [k for k, v in _PROVIDER_META.items() if v.get("source") == "cloud"]

    @classmethod
    def local_providers(cls) -> list[str]:
        return [k for k, v in _PROVIDER_META.items() if v.get("source") == "local"]

    @classmethod
    def all_display_names(cls) -> dict[str, str]:
        """返回 {key: display_name} 映射，供 UI 下拉框使用。"""
        return {k: str(v.get("display_name", k)) for k, v in _PROVIDER_META.items()}

    @classmethod
    def all_service_labels(cls) -> list[str]:
        """返回本地模型服务类型标签列表，供 UI 下拉框使用。"""
        return ["Ollama", "LM Studio", "llama.cpp server", "OpenAI-compatible local", "Custom"]

    @classmethod
    def service_label_to_key(cls, label: str) -> str:
        """将服务类型标签转换为 Provider key。"""
        mapping = {
            "ollama": Provider.OLLAMA,
            "lm studio": Provider.LM_STUDIO,
            "llama.cpp server": Provider.LLAMA_CPP,
            "llama.cpp": Provider.LLAMA_CPP,
            "openai-compatible local": Provider.LOCAL_OPENAI_COMPATIBLE,
            "custom": Provider.LOCAL_OPENAI_COMPATIBLE,
        }
        cleaned = label.strip().lower()
        return mapping.get(cleaned, Provider.LOCAL_OPENAI_COMPATIBLE)

    @classmethod
    def make_profile_id(cls, provider_key: str, model: str = "") -> str:
        """生成标准的 profile ID，例如 deepseek_default 或 ollama_qwen2.5_0.5b。"""
        key = cls.normalize(provider_key)
        if model:
            safe_model = model.replace(":", "_").replace(".", "_").replace("/", "_")
            return f"{key}_{safe_model}"
        return f"{key}_default"
