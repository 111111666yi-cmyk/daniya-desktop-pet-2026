from __future__ import annotations
import random
import time
from typing import Any, Callable
from PySide6.QtCore import QObject, QPoint, QTimer, Signal

IDLE_BUBBLES = [
    "你还在吗？",
    "我没有睡着。",
    "……只是发了一会儿呆。",
    "……盯着屏幕太久，眼睛不累吗？",
    "……又在敲什么奇奇怪怪的代码。"
]

class IdleBehavior(QObject):
    idle_action_triggered = Signal(str)
    idle_bubble_triggered = Signal(str)
    wander_requested = Signal(QPoint)

    def __init__(
        self,
        config: Any,
        is_allowed: Callable[[], bool],
        is_night: Callable[[], bool],
        get_position: Callable[[], QPoint] | None = None,
        get_screen_bounds: Callable[[], tuple[int, int, int, int]] | None = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.is_allowed = is_allowed
        self.is_night = is_night
        self._get_position = get_position
        self._get_screen_bounds = get_screen_bounds

        self.last_activity_time = time.time()
        self.last_behavior_time = 0.0

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_idle)
        self.timer.setInterval(2000)
        self.set_enabled(bool(self.config.idle_behavior_enabled))

    def mark_activity(self) -> None:
        self.last_activity_time = time.time()

    def _check_idle(self) -> None:
        if not self.config.idle_behavior_enabled:
            return

        now = time.time()
        idle_threshold = self.config.idle_behavior_seconds

        if now - self.last_activity_time < idle_threshold:
            return

        if now - self.last_behavior_time < max(60, idle_threshold):
            return

        if not self.is_allowed():
            return

        self.last_behavior_time = now

        if self.is_night():
            self.idle_action_triggered.emit("sleep")
            return

        if random.random() < 0.4 and self._get_position and self._get_screen_bounds:
            self._try_wander()
            return

        self.idle_action_triggered.emit("idle")

        if random.random() < 0.3:
            bubble = random.choice(IDLE_BUBBLES)
            self.idle_bubble_triggered.emit(bubble)

    def _try_wander(self) -> None:
        pos = self._get_position()
        bx, by, bw, bh = self._get_screen_bounds()
        margin = 60
        dx = random.randint(-220, 220)
        dy = random.randint(-40, 40)
        tx = max(bx + margin, min(bx + bw - margin, pos.x() + dx))
        ty = max(by + margin, min(bx + bh - margin, pos.y() + dy))
        self.wander_requested.emit(QPoint(tx, ty))

    def set_config(self, config: Any) -> None:
        self.config = config
        self.set_enabled(bool(self.config.idle_behavior_enabled))

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()
