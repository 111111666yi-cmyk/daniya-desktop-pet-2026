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
        blocks = [
            "用户档案：\n"
            f"称呼：{profile['user_name']}\n"
            f"关系：{profile['relationship']}\n"
            f"偏好风格：{profile['style']}\n"
            "请你在对话中记住这些设定。"
        ]
        memory_block = self._memory_prompt_block()
        if memory_block:
            blocks.append(memory_block)
        return "\n\n".join(blocks)

    def _memory_prompt_block(self) -> str:
        lines: list[str] = []
        try:
            from core.memory_engine import load_user_memory

            memory = load_user_memory()
        except Exception:
            memory = {}

        preferences = memory.get("user_preferences")
        if isinstance(preferences, dict) and preferences:
            lines.append("用户记忆偏好：")
            for key, value in sorted(preferences.items()):
                lines.append(f"- {key}: {value}")

        phrases = memory.get("important_user_phrases")
        if isinstance(phrases, list) and phrases:
            lines.append("用户重要表达：")
            lines.extend(f"- {item}" for item in phrases[-8:])

        unlocked_lore = memory.get("unlocked_lore")
        if isinstance(unlocked_lore, list) and unlocked_lore:
            lines.append("已解锁剧情记忆：")
            lines.extend(f"- {item}" for item in unlocked_lore[-8:])

        notes = _recent_notes(self.config_manager.data_dir / "notes.txt", limit=8)
        if notes:
            lines.append("达妮娅记忆备忘录：")
            lines.extend(f"- {note}" for note in notes)

        return "\n".join(lines)


def _recent_notes(path, limit: int) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    cleaned = [line.strip() for line in lines if line.strip()]
    return cleaned[-limit:]
