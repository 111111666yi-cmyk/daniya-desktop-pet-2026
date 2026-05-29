"""DeepSeek API 边界模块 — 薄封装层。

DeepSeek 使用与 OpenAI 完全兼容的 /chat/completions 端点。
此模块现在是 openai_api.py 的 re-export，保持向后兼容。

所有实现位于 openai_api.py，调用方无需更改 import 路径。
"""

from __future__ import annotations

from .openai_api import chat, test_connection

__all__ = ["chat", "test_connection"]
