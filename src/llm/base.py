import abc
from dataclasses import dataclass
from typing import Any


@dataclass
class ProviderTestResult:
    success: bool
    message: str


class ChatProvider(abc.ABC):
    """大模型提供商的统一接口基类"""
    
    @property
    @abc.abstractmethod
    def provider_id(self) -> str:
        """提供商的唯一标识符（例如 deepseek, openai 等）"""
        pass

    @property
    @abc.abstractmethod
    def display_name(self) -> str:
        """用于在设置中心下拉框展示的友好名称"""
        pass

    @abc.abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        config: dict[str, Any],
    ) -> str:
        """
        发送对话请求并返回响应字符串。
        :param messages: OpenAI 格式的消息列表 [{"role": "system", "content": "..."}, ...]
        :param config: 此 Provider 在 api_config.json 里的具体配置字典
        :raises ProviderError: 如果请求失败，抛出对应的异常
        """
        pass

    @abc.abstractmethod
    def test_connection(self, config: dict[str, Any]) -> ProviderTestResult:
        """
        测试连接（可用于设置中心的“测试连接”功能）。
        应该在后台执行轻量请求验证配置是否正确。
        """
        pass

    @abc.abstractmethod
    def validate_config(self, config: dict[str, Any]) -> list[str]:
        """验证配置是否有缺失的必填项，返回错误信息列表。为空则表示校验通过。"""
        pass

    def supports_streaming(self) -> bool:
        """是否支持流式输出（预留功能）"""
        return False

    def mask_sensitive_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """将包含敏感信息（如 API Key）的配置项脱敏"""
        masked = dict(config)
        api_key = str(config.get("api_key_masked") or "").strip()
        if not api_key:
            masked["api_key_masked"] = "<empty>"
        elif len(api_key) <= 8:
            masked["api_key_masked"] = "****"
        else:
            masked["api_key_masked"] = f"{api_key[:4]}****{api_key[-4:]}"
        return masked
