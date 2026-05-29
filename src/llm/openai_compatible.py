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


class OpenAICompatibleProvider(ChatProvider):
    """
    实现了标准 OpenAI API 格式的 Provider。
    DeepSeek, 官方 OpenAI, 本地 LM Studio 等都可以继承或直接使用此实现。
    """

    def __init__(self, provider_id: str, display_name: str):
        self._provider_id = provider_id
        self._display_name = display_name

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def display_name(self) -> str:
        return self._display_name

    def validate_config(self, config: dict[str, Any]) -> list[str]:
        errors = []
        if not self._get_base_url(config):
            errors.append("Base URL 不能为空")
        return errors

    def _get_api_key(self, config: dict[str, Any]) -> str:
        # 优先从 .env 读取
        env_path = runtime_root() / ".env"
        env = dotenv_values(env_path) if env_path.exists() else {}
        env_key_name = config.get("api_key_env", "")
        if env_key_name:
            # 优先读系统变量，再读 .env 文件
            key = os.environ.get(env_key_name) or env.get(env_key_name)
            if key and str(key).strip() and str(key).strip() != "your_api_key_here":
                return str(key).strip()
        # 作为 fallback 尝试从 config 里读 (虽然按规范不应该把 key 存入 api_config.json)
        # 我们假设 api_config.json 不含真实 key，如果有则用作兜底
        return ""

    def _get_base_url(self, config: dict[str, Any]) -> str:
        url = str(config.get("base_url", "")).strip()
        return url.rstrip("/")

    def _get_model(self, config: dict[str, Any]) -> str:
        return str(config.get("model", "")).strip()

    def _build_payload(self, messages: list[dict[str, str]], config: dict[str, Any]) -> dict[str, Any]:
        return {
            "model": self._get_model(config),
            "messages": messages,
            "temperature": float(config.get("temperature", 0.8)),
            "max_tokens": int(config.get("max_tokens", 360)),
        }

    def chat(self, messages: list[dict[str, str]], config: dict[str, Any]) -> str:
        api_key = self._get_api_key(config)
        base_url = self._get_base_url(config)
        timeout = int(config.get("timeout", 20))

        if not base_url:
            raise ProviderConfigError(f"[{self.display_name}] 缺少 base_url")

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        endpoint = f"{base_url}/chat/completions"
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
            content = data["choices"][0]["message"]["content"]
            if not str(content).strip():
                raise ProviderFormatError(f"[{self.display_name}] 返回的内容为空")
            return str(content).strip()
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ProviderFormatError(f"[{self.display_name}] 解析响应失败: {exc}") from exc

    def test_connection(self, config: dict[str, Any]) -> ProviderTestResult:
        # 使用很小的请求来测试
        messages = [{"role": "user", "content": "Hi"}]
        test_config = dict(config)
        test_config["max_tokens"] = 5
        try:
            self.chat(messages, test_config)
            return ProviderTestResult(success=True, message=f"{self.display_name} 连接成功")
        except ProviderAuthError as e:
            return ProviderTestResult(success=False, message=str(e))
        except ProviderError as e:
            # 有时候 model 名称不对会导致 HTTP 404/400，这也算连接测试能够探测到的错误
            return ProviderTestResult(success=False, message=str(e))
        except Exception as e:
            return ProviderTestResult(success=False, message=f"未知错误: {e}")
