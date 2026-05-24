from __future__ import annotations

import random
from datetime import datetime
from typing import Any


NIGHT_LINES = [
    "这么晚啦，要不要睡觉呀？",
    "Zzz……啊，御主还醒着？",
    "夜深啦，我会小声陪着你的。",
]

DAY_LINES = [
    "嘿嘿，我在这里。",
    "御主叫我了吗？",
    "今天也一起加油吧。",
]


class DayNightManager:
    def __init__(self, app_config: dict[str, Any]) -> None:
        self.app_config = app_config

    def is_night(self) -> bool:
        if not bool(self.app_config.get("day_night_enabled", True)):
            return False
        hour = datetime.now().hour
        start = int(self.app_config.get("night_start_hour", 23))
        end = int(self.app_config.get("night_end_hour", 7))
        if start == end:
            return False
        if start < end:
            return start <= hour < end
        return hour >= start or hour < end

    def click_line(self) -> str:
        return random.choice(NIGHT_LINES if self.is_night() else DAY_LINES)
