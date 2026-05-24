from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .config_manager import ConfigManager


DEFAULT_AFFINITY = {
    "value": 0,
    "last_click_at": None,
}


class AffinityManager:
    def __init__(self, config_manager: ConfigManager, cooldown_seconds: int) -> None:
        self.config_manager = config_manager
        self.path = self.config_manager.data_dir / "affinity.json"
        self.cooldown = timedelta(seconds=max(1, cooldown_seconds))
        if not self.path.exists():
            self._save(DEFAULT_AFFINITY.copy())

    def value(self) -> int:
        return int(self._load().get("value", 0))

    def label(self) -> str:
        return f"好感度 {self.value()} · {self.level_name()}"

    def level_name(self) -> str:
        value = self.value()
        if value <= 30:
            return "初识"
        if value <= 70:
            return "熟悉"
        if value <= 120:
            return "亲近"
        return "很依赖"

    def badge(self) -> str:
        marks = {
            "初识": "♡",
            "熟悉": "♥",
            "亲近": "✦",
            "很依赖": "✧",
        }
        level = self.level_name()
        return f"{marks.get(level, '♡')} {level}"

    def add_chat(self) -> None:
        self.add_value(1)

    def add_value(self, amount: int) -> None:
        data = self._load()
        data["value"] = max(0, int(data.get("value", 0)) + amount)
        self._save(data)

    def add_click(self) -> bool:
        data = self._load()
        now = datetime.now()
        last_click_raw = data.get("last_click_at")
        if last_click_raw:
            try:
                last_click = datetime.fromisoformat(str(last_click_raw))
                if now - last_click < self.cooldown:
                    return False
            except ValueError:
                pass
        data["value"] = int(data.get("value", 0)) + 1
        data["last_click_at"] = now.isoformat(timespec="seconds")
        self._save(data)
        return True

    def _load(self) -> dict[str, Any]:
        data = self.config_manager.load_json(self.path, DEFAULT_AFFINITY)
        if not isinstance(data, dict):
            return DEFAULT_AFFINITY.copy()
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.config_manager.save_json(self.path, data)
