"""Anthropic Claude API 边界模块。

失败模式：鉴权失败(401)、限流(429)、服务端错误(5xx)、网络不可达、响应格式异常。
"""

from __future__ import annotations

from typing import Any

import requests

from . import AuthError, MalformedResponse, _retry_request


def chat(
    messages: list[dict[str, str]],
    api_key: str,
    *,
    base_url: str = "https://api.anthropic.com/v1",
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 1024,
    temperature: float = 0.8,
    timeout: int = 30,
) -> str:
    """向 Anthropic Messages API 发送请求，返回响应文本。"""
    if not api_key:
        raise AuthError("未配置 Claude API Key，请在设置中填写。")

    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    }

    # 分离 system 消息
    system_parts: list[dict[str, Any]] = []
    chat_messages: list[dict[str, Any]] = []
    for msg in messages:
        if msg["role"] == "system":
            system_parts.append({"type": "text", "text": msg["content"]})
        else:
            chat_messages.append({"role": msg["role"], "content": msg["content"]})

    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": chat_messages,
    }
    if system_parts:
        payload["system"] = system_parts

    def _call() -> requests.Response:
        return requests.post(
            f"{base_url.rstrip('/')}/messages",
            headers=headers,
            json=payload,
            timeout=timeout,
        )

    resp = _retry_request(_call)
    try:
        data: dict[str, Any] = resp.json()
        content_blocks = data.get("content", [])
        text = "".join(
            block.get("text", "")
            for block in content_blocks
            if isinstance(block, dict) and block.get("type") == "text"
        )
        if not text.strip():
            raise MalformedResponse("Claude returned empty content")
        return text.strip()
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise MalformedResponse(f"Failed to parse Claude response: {exc}") from exc
