from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal


class TimeEventManager(QObject):
    hourly_chime = Signal(str)

    def __init__(self, app_config: dict[str, Any]) -> None:
        super().__init__()
        self.app_config = app_config
        self.last_chime_key = ""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_time)
        self.timer.setInterval(60_000)
        self.set_enabled(bool(self.app_config.get("hourly_chime_enabled", False)))

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            if not self.timer.isActive():
                self.timer.start()
                QTimer.singleShot(2_000, self.check_time)
        else:
            self.timer.stop()

    def check_time(self) -> None:
        if not bool(self.app_config.get("hourly_chime_enabled", False)):
            return
        now = datetime.now()
        if now.minute != 0:
            return
        key = now.strftime("%Y-%m-%d %H")
        if key == self.last_chime_key:
            return
        self.last_chime_key = key
        if 23 <= now.hour or now.hour < 7:
            msg = f"……都 {now.hour} 点了。你到底睡不睡。"
        else:
            msg = f"……已经 {now.hour} 点了。别一直盯着屏幕。"
        self.hourly_chime.emit(msg)
