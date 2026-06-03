from __future__ import annotations

import random
from datetime import datetime, timedelta
from typing import Any, Callable

from PySide6.QtCore import QObject, QTimer, Signal


IDLE_LINES = [
    "……还在忙？别忘了眨眼。",
    "……累了就歇会儿，我又不会催你。",
    "……爱待待着，反正我也闲着。",
]


class IdleManager(QObject):
    idle_message = Signal(str)

    def __init__(self, app_config: dict[str, Any], can_speak: Callable[[], bool]) -> None:
        super().__init__()
        self.app_config = app_config
        self.can_speak = can_speak
        self.last_activity = datetime.now()
        self.last_emit = datetime.min
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_idle)
        self.timer.start(30_000)

    def mark_activity(self) -> None:
        self.last_activity = datetime.now()

    def check_idle(self) -> None:
        if not bool(self.app_config.get("idle_chat_enabled", False)):
            return
        minutes = max(1, int(self.app_config.get("idle_chat_minutes", 10)))
        now = datetime.now()
        threshold = timedelta(minutes=minutes)
        if now - self.last_activity < threshold:
            return
        if now - self.last_emit < threshold:
            return
        if not self.can_speak():
            return
        self.last_emit = now
        self.last_activity = now
        self.idle_message.emit(random.choice(IDLE_LINES))
