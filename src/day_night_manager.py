from __future__ import annotations

import random
from datetime import datetime
from typing import Any


NIGHT_LINES = [
    "……都这么晚了。还不去睡吗。",
    "……唔。你精神真好，我困了。",
    "……知道了。声音小一点就是了。",
]

DAY_LINES = [
    "……干嘛。别乱戳。",
    "……嗯，听到了。有事？",
    "……今天也留在这了。随便晃晃。",
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
