from typing import Any

from .openai_compatible import OpenAICompatibleProvider


class LocalProvider(OpenAICompatibleProvider):
    """
    连接本地 OpenAI-Compatible 服务的 Provider（如 LM Studio, Ollama 等）。
    """

    def __init__(self) -> None:
        super().__init__(provider_id="local_openai_compatible", display_name="Local OpenAI-Compatible")

    def _get_api_key(self, config: dict[str, Any]) -> str:
        # 本地服务通常不需要真实的 API Key，但也可能配置。
        key = super()._get_api_key(config)
        return key if key else "not-needed"

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors = []
        if not self._get_base_url(config):
            errors.append("Base URL 不能为空，通常为 http://localhost:1234/v1 或 http://localhost:11434/v1")
        return errors
