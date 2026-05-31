"""Ollama 本地 API 边界模块。

失败模式：服务不可达、模型不存在(404)、响应格式异常。
Ollama 没有鉴权和限流，但有自己的错误格式。
"""

from __future__ import annotations

from typing import Any

import requests

from . import BoundaryError, MalformedResponse, NetworkError, _retry_request


class ModelNotFoundError(BoundaryError):
    """Ollama 上未找到指定模型"""


def chat(
    messages: list[dict[str, str]],
    *,
    base_url: str = "http://localhost:11434",
    model: str = "",
    temperature: float = 0.8,
    timeout: int = 20,
) -> str:
    """向 Ollama /api/chat 发送请求，返回响应文本。"""
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if temperature:
        payload.setdefault("options", {})["temperature"] = temperature  # type: ignore[index]

    def _call() -> requests.Response:
        return requests.post(
            f"{base_url.rstrip('/')}/api/chat",
            json=payload,
            timeout=timeout,
        )

    try:
        resp = _retry_request(_call)
    except BoundaryError as exc:
        if exc.__cause__ and isinstance(exc.__cause__, requests.HTTPError):
            status = exc.__cause__.response.status_code if exc.__cause__.response is not None else 0
            if status == 404:
                raise ModelNotFoundError(f"Model '{model}' not found on Ollama server") from exc
        raise

    try:
        data: dict[str, Any] = resp.json()
    except ValueError as exc:
        raise MalformedResponse(f"Ollama returned non-JSON response: {exc}") from exc

    if resp.status_code == 404:
        raise ModelNotFoundError(f"Model '{model}' not found on Ollama server")

    content = data.get("message", {}).get("content", "")
    if not str(content).strip():
        raise MalformedResponse("Ollama returned empty content")
    return str(content).strip()


def test_connection(base_url: str = "http://localhost:11434", timeout: int = 5) -> bool:
    """检查 Ollama 服务是否可达。"""
    try:
        resp = requests.get(f"{base_url.rstrip('/')}", timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False
