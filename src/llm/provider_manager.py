from typing import Any

from src.utils import runtime_root

from .base import ChatProvider, ProviderTestResult
from .claude_provider import ClaudeProvider
from .deepseek_provider import DeepSeekProvider
from .errors import ProviderError
from .local_provider import LocalProvider
from .openai_compatible import OpenAICompatibleProvider
from .openai_provider import OpenAIProvider


class ProviderManager:
    """
    负责管理不同的大模型提供商 (Provider)，
    并根据 api_config.json 的配置自动路由对话请求。
    包含了失败降级 (Fallback) 的逻辑。
    """

    def __init__(self, api_config: dict[str, Any], system_prompt: str = "", prompt_prefix: str = ""):
        self.api_config = api_config
        self.system_prompt = system_prompt
        self.prompt_prefix = prompt_prefix
        
        self.providers: dict[str, ChatProvider] = {
            "deepseek": DeepSeekProvider(),
            "openai_compatible": OpenAICompatibleProvider("openai_compatible", "OpenAI-Compatible"),
            "openai": OpenAIProvider(),
            "claude": ClaudeProvider(),
            "local_openai_compatible": LocalProvider(),
        }

    def get_active_provider(self) -> ChatProvider:
        """获取当前配置激活的 Provider，默认降级到 deepseek"""
        active_id = str(self.api_config.get("active_provider", "deepseek")).strip()
        # 兼容旧版本 api_config.json，旧版本没有 active_provider 而是 provider
        if not active_id or active_id not in self.providers:
            active_id = str(self.api_config.get("provider", "deepseek")).strip()
        
        provider = self.providers.get(active_id)
        if not provider:
            provider = self.providers["deepseek"]
        return provider

    def get_provider_config(self, provider_id: str) -> dict[str, Any]:
        """获取指定 Provider 的配置"""
        providers_config = self.api_config.get("providers", {})
        if provider_id in providers_config:
            return providers_config[provider_id]
        
        # 兼容旧版本 api_config.json
        if provider_id == self.api_config.get("provider", "deepseek"):
            return self.api_config
            
        return {}

    def chat(self, messages: list[dict[str, str]]) -> tuple[str, str]:
        """
        发送消息给当前激活的 Provider。
        如果请求失败且开启了 fallback，返回 fallback 的回复。
        返回 (response_text, source)
        """
        provider = self.get_active_provider()
        config = self.get_provider_config(provider.provider_id)
        
        try:
            response = provider.chat(messages, config)
            return response, "api"
        except ProviderError as e:
            print(f"[Daniya] Provider {provider.provider_id} error: {e}; source=local")
            return self.local_fallback(api_error=True), "local"
        except Exception as e:
            print(f"[Daniya] Provider {provider.provider_id} unexpected error: {e}; source=local")
            return self.local_fallback(api_error=True), "local"

    def test_connection(self, provider_id: str) -> ProviderTestResult:
        """测试指定 Provider 的连接"""
        provider = self.providers.get(provider_id)
        if not provider:
            return ProviderTestResult(success=False, message=f"未找到 Provider: {provider_id}")
            
        config = self.get_provider_config(provider_id)
        errors = provider.validate_config(config)
        if errors:
            return ProviderTestResult(success=False, message="配置无效:\n" + "\n".join(errors))
            
        return provider.test_connection(config)

    def prompt_to_messages(self, prompt: str, history_messages: list[dict[str, str]] | None = None) -> list[dict[str, str]]:
        """
        将旧版的单个 prompt 字符串加上历史记录转换为 messages 列表。
        这用于兼容 v0.415 的 PromptBuilder。
        """
        # 注意：这里的 prompt 是 PromptBuilder 生成的包含系统设定的全量文本
        # 为了兼容 OpenAI 和 Claude 的最佳实践，如果历史消息存在，
        # 我们最好将系统设定分离为 system role，当前对话为 user role。
        # 但在 v0.415 中，prompt 已经包含了对话历史（如果我们没传入 recent_messages 的话）。
        # 所以简单处理就是将整个 prompt 作为 user message 发送，
        # 并在顶部加上固定的系统前缀。
        system_content = f"{self.prompt_prefix}\n\n角色设定：\n{self.system_prompt}".strip()
        messages = [{"role": "system", "content": system_content}]
        
        if history_messages:
            messages.extend(history_messages)
            
        messages.append({"role": "user", "content": prompt})
        return messages

    def local_fallback(self, api_error: bool = False) -> str:
        """返回本地的回退消息"""
        chat_config = self.api_config.get("chat", {})
        if api_error:
            return str(chat_config.get("api_error_fallback_reply", "达妮娅刚刚走神了一下……但我还在哦。"))
        return str(chat_config.get("fallback_reply", "达妮娅现在还没有连上大脑，但我已经在这里啦！"))
