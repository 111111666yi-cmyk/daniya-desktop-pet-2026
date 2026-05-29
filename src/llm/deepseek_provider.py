from typing import Any

from .errors import ProviderAuthError, ProviderConfigError
from .openai_compatible import OpenAICompatibleProvider


class DeepSeekProvider(OpenAICompatibleProvider):
    """
    专用于 DeepSeek 的 Provider。
    默认集成 api.deepseek.com。
    """

    def __init__(self) -> None:
        super().__init__(provider_id="deepseek", display_name="DeepSeek")

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors = super().validate_config(config)
        if not self._get_api_key(config):
            errors.append(f"缺少 {config.get('api_key_env', 'DEEPSEEK_API_KEY')} 环境变量配置")
        return errors

    def _get_base_url(self, config: dict[str, Any]) -> str:
        url = super()._get_base_url(config)
        return url if url else "https://api.deepseek.com"

    def chat(self, messages: list[dict[str, str]], config: dict[str, Any]) -> str:
        api_key = self._get_api_key(config)
        if not api_key:
            raise ProviderAuthError(f"[{self.display_name}] 缺少 API Key，请在 .env 中配置 {config.get('api_key_env', 'DEEPSEEK_API_KEY')}")
        return super().chat(messages, config)
