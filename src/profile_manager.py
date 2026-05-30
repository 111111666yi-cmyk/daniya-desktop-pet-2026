from __future__ import annotations

from typing import Any

from .config_manager import ConfigManager


DEFAULT_PROFILE = {
    "user_name": "主人",
    "relationship": "桌宠与主人",
    "style": "温柔、可爱、简短、陪伴感",
}


class ProfileManager:
    def __init__(self, config_manager: ConfigManager) -> None:
        self.config_manager = config_manager
        self.path = self.config_manager.config_dir / "profile.json"
        if not self.path.exists():
            self.save(DEFAULT_PROFILE)

    def load(self) -> dict[str, str]:
        data: dict[str, Any] = self.config_manager.load_json(self.path, DEFAULT_PROFILE)
        if not isinstance(data, dict):
            data = {}
        profile = DEFAULT_PROFILE.copy()
        for key in profile:
            value = data.get(key, profile[key])
            profile[key] = str(value)
        return profile

    def save(self, profile: dict[str, str]) -> None:
        clean = DEFAULT_PROFILE.copy()
        for key in clean:
            clean[key] = str(profile.get(key, clean[key])).strip() or clean[key]
        self.config_manager.save_json(self.path, clean)

    def prompt_prefix(self) -> str:
        profile = self.load()
        return (
            "用户档案：\n"
            f"称呼：{profile['user_name']}\n"
            f"关系：{profile['relationship']}\n"
            f"偏好风格：{profile['style']}\n"
            "请你在对话中记住这些设定。"
        )
