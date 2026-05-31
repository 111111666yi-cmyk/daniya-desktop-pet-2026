from __future__ import annotations

import webbrowser
from typing import Any
from urllib.parse import urlparse

from .config_manager import ConfigManager, DEFAULT_BOOKMARKS


class BookmarkManager:
    def __init__(self, config_manager: ConfigManager) -> None:
        self.config_manager = config_manager
        self.path = config_manager.config_dir / "bookmarks.json"
        if not self.path.exists():
            self.config_manager.save_json(self.path, DEFAULT_BOOKMARKS)

    def records(self) -> list[dict[str, str]]:
        data = self.config_manager.load_json(self.path, DEFAULT_BOOKMARKS)
        if not isinstance(data, list):
            data = DEFAULT_BOOKMARKS
        output: list[dict[str, str]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name", "")).strip()
            url = str(item.get("url", "")).strip()
            if name and url:
                output.append({"name": name, "url": url})
        return output or DEFAULT_BOOKMARKS.copy()

    def open(self, url: str) -> tuple[bool, str]:
        clean = url.strip()
        parsed = urlparse(clean)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False, "……这个地址怪怪的，打不开。"
        try:
            webbrowser.open(clean)
        except webbrowser.Error:
            return False, "……浏览器没反应。你是不是没装好？"
        return True, "……打开了。自己看吧。"
