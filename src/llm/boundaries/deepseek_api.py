"""DeepSeek API 边界模块。只处理与 api.deepseek.com 的 HTTP 通信。

失败模式：鉴权失败(401)、限流(429)、服务端错误(5xx)、网络不可达、响应格式异常。
调用方只需处理 BoundaryError 及其子类。
"""

from __future__ import annotations

from typing import Any

import requests

from . import (
    AuthError,
    MalformedResponse,
    _retry_request,
)


def chat(
    messages: list[dict[str, str]],
    api_key: str,
    *,
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-chat",
    temperature: float = 0.8,
    max_tokens: int = 360,
    timeout: int = 20,
) -> str:
    """向 DeepSeek API 发送对话请求，返回响应文本。"""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    def _call() -> requests.Response:
        return requests.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers=headers,
            json=payload,
            timeout=timeout,
        )

    resp = _retry_request(_call)
    try:
        data: dict[str, Any] = resp.json()
        content = data["choices"][0]["message"]["content"]
        if not str(content).strip():
            raise MalformedResponse("DeepSeek returned empty content")
        return str(content).strip()
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise MalformedResponse(f"Failed to parse DeepSeek response: {exc}") from exc


def test_connection(
    api_key: str,
    *,
    base_url: str = "https://api.deepseek.com",
    model: str = "deepseek-chat",
    timeout: int = 8,
) -> bool:
    """轻量连接测试。返回 True/False。"""
    try:
        chat(
            [{"role": "user", "content": "Hi"}],
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_tokens=5,
            timeout=timeout,
        )
        return True
    except Exception:
        return False
