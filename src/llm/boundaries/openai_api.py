"""OpenAI / OpenAI-compatible API 边界模块。

适用于：DeepSeek、OpenAI、LM Studio、llama.cpp server、自定义兼容端点。
失败模式：鉴权失败(401)、限流(429)、服务端错误(5xx)、网络不可达、响应格式异常。

注：deepseek_api.py 现为此模块的薄封装（保持向后兼容）。
"""

from __future__ import annotations

from typing import Any

import requests

from . import AuthError, MalformedResponse, _retry_request


def chat(
    messages: list[dict[str, str]],
    api_key: str,
    *,
    base_url: str,
    model: str,
    auth_header: str = "bearer",
    temperature: float = 0.8,
    max_tokens: int = 360,
    timeout: int = 20,
) -> str:
    """向 OpenAI-compatible 端点发送对话请求，返回响应文本。

    适用于 DeepSeek / OpenAI / LM Studio / llama.cpp / 自定义端点。
    api_key 为空时不发送 Authorization header（本地无鉴权服务）。
    """
    headers: dict[str, str] = {"Content-Type": "application/json"}
    headers.update(_auth_headers(api_key, auth_header))

    payload: dict[str, Any] = {
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
            raise MalformedResponse("API returned empty content")
        return str(content).strip()
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise MalformedResponse(f"Failed to parse API response: {exc}") from exc


def test_connection(
    api_key: str,
    *,
    base_url: str,
    model: str,
    auth_header: str = "bearer",
    timeout: int = 8,
) -> bool:
    """轻量连接测试。"""
    try:
        chat(
            [{"role": "user", "content": "Hi"}],
            api_key=api_key,
            base_url=base_url,
            model=model,
            auth_header=auth_header,
            max_tokens=5,
            timeout=timeout,
        )
        return True
    except Exception:
        return False


def _auth_headers(api_key: str, auth_header: str = "bearer") -> dict[str, str]:
    if not api_key:
        return {}

    mode = (auth_header or "bearer").strip().lower().replace("_", "-")
    if mode in {"bearer", "authorization-bearer"}:
        return {"Authorization": f"Bearer {api_key}"}
    if mode in {"api-key", "apikey"}:
        return {"api-key": api_key}
    if mode == "x-api-key":
        return {"x-api-key": api_key}
    if mode in {"none", "no-auth"}:
        return {}
    return {"Authorization": f"Bearer {api_key}"}
