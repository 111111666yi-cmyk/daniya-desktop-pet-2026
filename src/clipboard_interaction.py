from __future__ import annotations

import re
from typing import Any
from PySide6.QtCore import QObject, Signal

# Sensitive patterns with lookaround assertions to support Unicode and Chinese boundary contexts
SENSITIVE_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}", re.IGNORECASE),
    re.compile(r"Bearer\s+[A-Za-z0-9_.-]+", re.IGNORECASE),
    re.compile(r"(?:api[_-]?key|secret|token|password|passwd|密钥|密码)\s*[:=/\s-]\s*[A-Za-z0-9_.-]{8,}", re.IGNORECASE),
    re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)"),  # ID Card
    re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)"),   # Mobile
    re.compile(r"(?<!\d)\d{16,19}(?!\d)"),     # Bank Card
]

class ClipboardInteraction(QObject):
    clipboard_alert = Signal(dict)  # Emits result dictionary

    def __init__(
        self,
        clipboard_obj: Any = None,
        max_chars: int = 1000,
        show_preview: bool = False,
        sensitive_block_enabled: bool = True,
    ) -> None:
        super().__init__()
        self.clipboard = clipboard_obj
        self.enabled = False
        self.last_text = ""
        self.max_chars = max(100, int(max_chars))
        self.show_preview = bool(show_preview)
        self.sensitive_block_enabled = bool(sensitive_block_enabled)

        if self.clipboard:
            self.clipboard.dataChanged.connect(self.on_clipboard_change)

    def set_enabled(self, val: bool) -> None:
        self.enabled = val

    def check_text(self, text: str) -> dict[str, Any]:
        text = text.strip()
        if not text:
            return {"ok": False, "status": "empty", "message": "剪贴板为空", "clean_text": ""}

        # 1. Check sensitive info
        if self.sensitive_block_enabled:
            for p in SENSITIVE_PATTERNS:
                if p.search(text):
                    return {
                        "ok": False,
                        "status": "sensitive",
                        "message": "检测到疑似敏感或隐私内容（如密钥/密码/身份信息），已自动忽略。",
                        "clean_text": ""
                    }

        # 2. Check length
        if len(text) > self.max_chars:
            return {
                "ok": True,
                "status": "too_long",
                "message": f"剪贴板文本过长（已复制 {len(text)} 字），需要你确认后才能分析。",
                "clean_text": text[:self.max_chars] if self.show_preview else ""
            }

        clean_text = text if self.show_preview else ""
        return {
            "ok": True,
            "status": "safe",
            "message": f"检测到剪贴板有新文本（{len(text)} 字）。需要帮你分析一下吗？",
            "clean_text": clean_text
        }

    def on_clipboard_change(self) -> None:
        if not self.enabled or not self.clipboard:
            return

        try:
            text = self.clipboard.text()
        except Exception:
            return

        if not text or text == self.last_text:
            return

        self.last_text = text
        res = self.check_text(text)
        self.clipboard_alert.emit(res)
