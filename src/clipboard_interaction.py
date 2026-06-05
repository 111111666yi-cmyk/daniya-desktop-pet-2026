from __future__ import annotations

import re
from typing import Any, Callable
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
        self.message_lookup: Callable[..., str] | None = None

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
                        "message": self._message(
                            "clipboard_sensitive",
                            "这段内容可能包含隐私或凭据，我不会显示、保存或发送它。",
                        ),
                        "clean_text": ""
                    }

        # 2. Check length
        if len(text) > self.max_chars:
            return {
                "ok": True,
                "status": "too_long",
                "message": self._message(
                    "clipboard_too_long",
                    "这段文字有 {length} 个字。需要你确认后才能继续处理。",
                    length=len(text),
                ),
                "clean_text": text[:self.max_chars] if self.show_preview else ""
            }

        clean_text = text if self.show_preview else ""
        return {
            "ok": True,
            "status": "safe",
            "message": self._message(
                "clipboard_safe",
                "剪贴板里有一段新文字。需要我处理时再确认。",
                length=len(text),
            ),
            "clean_text": clean_text
        }

    def _message(self, key: str, fallback: str, **values: Any) -> str:
        if self.message_lookup is not None:
            try:
                return self.message_lookup(key, **values)
            except Exception:
                pass
        return fallback.format(**values)

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
