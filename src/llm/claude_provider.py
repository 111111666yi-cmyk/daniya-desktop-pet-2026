import os
from typing import Any

import requests
from dotenv import dotenv_values

from src.utils import runtime_root

from .base import ChatProvider, ProviderTestResult
from .errors import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderConnectionError,
    ProviderFormatError,
)


class ClaudeProvider(ChatProvider):
    """
    Anthropic Claude Messages API Provider.
    """

    def __init__(self) -> None:
        self._provider_id = "claude"
        self._display_name = "Claude"

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def display_name(self) -> str:
        return self._display_name

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors = []
        if not self._get_api_key(config):
            errors.append(f"缺少 {config.get('api_key_env', 'ANTHROPIC_API_KEY')} 环境变量配置")
        if not self._get_model(config):
            errors.append("Model 不能为空")
        return errors

    def _get_api_key(self, config: dict[str, Any]) -> str:
        env_path = runtime_root() / ".env"
        env = dotenv_values(env_path) if env_path.exists() else {}
        env_key_name = config.get("api_key_env", "ANTHROPIC_API_KEY")
        if env_key_name:
            key = os.environ.get(env_key_name) or env.get(env_key_name)
            if key and str(key).strip() and str(key).strip() != "your_api_key_here":
                return str(key).strip()
        return ""

    def _get_base_url(self, config: dict[str, Any]) -> str:
        url = str(config.get("base_url", "")).strip()
        return url.rstrip("/") if url else "https://api.anthropic.com/v1"

    def _get_model(self, config: dict[str, Any]) -> str:
        return str(config.get("model", "")).strip()

    def _build_payload(self, messages: list[dict[str, str]], config: dict[str, Any]) -> dict[str, Any]:
        system_content = ""
        anthropic_messages = []

        for msg in messages:
            if msg.get("role") == "system":
                # Claude 的 Messages API 将 system prompt 作为顶级参数
                system_content += msg.get("content", "") + "\n"
            else:
                anthropic_messages.append(msg)

        payload = {
            "model": self._get_model(config),
            "messages": anthropic_messages,
            "temperature": float(config.get("temperature", 0.8)),
            "max_tokens": int(config.get("max_tokens", 1024)), # Claude 要求 max_tokens 为必填项
        }
        if system_content.strip():
            payload["system"] = system_content.strip()

        return payload

    def chat(self, messages: list[dict[str, str]], config: dict[str, Any]) -> str:
        api_key = self._get_api_key(config)
        base_url = self._get_base_url(config)
        timeout = int(config.get("timeout", 20))

        if not api_key:
            raise ProviderAuthError(f"[{self.display_name}] 缺少 API Key，请配置 {config.get('api_key_env', 'ANTHROPIC_API_KEY')}")

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        endpoint = f"{base_url}/messages"
        payload = self._build_payload(messages, config)

        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)
            if response.status_code == 401:
                raise ProviderAuthError(f"[{self.display_name}] API Key 验证失败 (401)")
            response.raise_for_status()
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            raise ProviderConnectionError(f"[{self.display_name}] HTTP 错误: {status}") from exc
        except requests.RequestException as exc:
            raise ProviderConnectionError(f"[{self.display_name}] 网络连接失败: {exc}") from exc

        try:
            data = response.json()
            # Claude 的响应结构是: {"content": [{"type": "text", "text": "..."}]}
            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
            if not content.strip():
                raise ProviderFormatError(f"[{self.display_name}] 返回的内容为空")
            return content.strip()
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderFormatError(f"[{self.display_name}] 解析响应失败: {exc}") from exc

    def test_connection(self, config: dict[str, Any]) -> ProviderTestResult:
        messages = [{"role": "user", "content": "Hi"}]
        test_config = dict(config)
        test_config["max_tokens"] = 5
        try:
            self.chat(messages, test_config)
            return ProviderTestResult(success=True, message=f"{self.display_name} 连接成功")
        except ProviderAuthError as e:
            return ProviderTestResult(success=False, message=str(e))
        except ProviderError as e:
            return ProviderTestResult(success=False, message=str(e))
        except Exception as e:
            return ProviderTestResult(success=False, message=f"未知错误: {e}")
