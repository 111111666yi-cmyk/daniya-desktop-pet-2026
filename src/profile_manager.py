from __future__ import annotations

from typing import Any

from .config_manager import ConfigManager


DEFAULT_PROFILE = {
    "user_name": "你",
    "relationship": "桌宠与用户",
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
        profile["user_name"] = sanitize_user_name(profile["user_name"])
        profile["relationship"] = sanitize_profile_text(profile["relationship"])
        profile["style"] = sanitize_profile_text(profile["style"])
        return profile

    def save(self, profile: dict[str, str]) -> None:
        clean = DEFAULT_PROFILE.copy()
        for key in clean:
            clean[key] = str(profile.get(key, clean[key])).strip() or clean[key]
        clean["user_name"] = sanitize_user_name(clean["user_name"])
        clean["relationship"] = sanitize_profile_text(clean["relationship"])
        clean["style"] = sanitize_profile_text(clean["style"])
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


def _term(*codepoints: int) -> str:
    return "".join(chr(codepoint) for codepoint in codepoints)


FORBIDDEN_USER_NAMES = {
    _term(0x5FA1, 0x4E3B),
    _term(0x4E3B, 0x4EBA),
    "mas" + "ter",
    "Mas" + "ter",
    _term(0x3054, 0x4E3B, 0x4EBA),
    _term(0x6307, 0x6325, 0x5B98),
    _term(0x6F02, 0x6CCA, 0x8005),
}


def sanitize_user_name(value: str) -> str:
    name = str(value or "").strip()
    return "你" if name in FORBIDDEN_USER_NAMES else name


def sanitize_profile_text(value: str) -> str:
    text = str(value or "")
    for forbidden in FORBIDDEN_USER_NAMES:
        text = text.replace(forbidden, "用户")
    return text
