from __future__ import annotations

from datetime import datetime

from .config_manager import ConfigManager


class NotesManager:
    def __init__(self, config_manager: ConfigManager) -> None:
        self.path = config_manager.data_dir / "notes.txt"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def append(self, text: str) -> bool:
        content = text.strip()
        if not content:
            return False
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self.path.open("a", encoding="utf-8") as file:
            file.write(f"[{timestamp}] {content}\n")
        return True
