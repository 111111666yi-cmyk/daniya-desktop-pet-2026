from __future__ import annotations

import math
import time

from PySide6.QtCore import QObject, QTimer, Signal

DIMENSIONS = ("neutral", "happy", "sleepy", "annoyed", "lonely", "focused")

HALF_LIFE_SECONDS = 30 * 60  # 30 minutes
DECAY_INTERVAL_MS = 60_000   # check decay every 60s


class MoodManager(QObject):
    mood_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._values: dict[str, float] = {d: 0.0 for d in DIMENSIONS}
        self._values["neutral"] = 0.3
        self._last_update = time.monotonic()

        self._decay_timer = QTimer(self)
        self._decay_timer.timeout.connect(self._apply_decay)
        self._decay_timer.start(DECAY_INTERVAL_MS)

    @property
    def current_mood(self) -> str:
        self._apply_decay()
        return max(self._values, key=self._values.__getitem__)

    @property
    def values(self) -> dict[str, float]:
        self._apply_decay()
        return dict(self._values)

    def boost(self, dimension: str, amount: float) -> None:
        if dimension not in self._values:
            return
        self._apply_decay()
        self._values[dimension] = min(1.0, self._values[dimension] + amount)
        self._last_update = time.monotonic()
        self._emit_if_changed()

    def update_from_interaction(self, event: str) -> None:
        deltas = _EVENT_MAP.get(event)
        if not deltas:
            return
        self._apply_decay()
        for dim, amount in deltas.items():
            if dim in self._values:
                self._values[dim] = max(0.0, min(1.0, self._values[dim] + amount))
        self._last_update = time.monotonic()
        self._emit_if_changed()

    def _apply_decay(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_update
        if elapsed < 1.0:
            return
        factor = math.pow(0.5, elapsed / HALF_LIFE_SECONDS)
        for dim in DIMENSIONS:
            if dim == "neutral":
                continue
            self._values[dim] *= factor
        # neutral slowly rises as others decay
        non_neutral = sum(v for d, v in self._values.items() if d != "neutral")
        self._values["neutral"] = max(0.1, min(1.0, 0.3 + (1.0 - non_neutral) * 0.3))
        self._last_update = now

    def _emit_if_changed(self) -> None:
        mood = max(self._values, key=self._values.__getitem__)
        self.mood_changed.emit(mood)


_EVENT_MAP: dict[str, dict[str, float]] = {
    "click":        {"happy": 0.15, "lonely": -0.1},
    "chat":         {"happy": 0.10, "lonely": -0.15},
    "drag":         {"annoyed": 0.05, "happy": 0.05},
    "idle_long":    {"lonely": 0.10, "sleepy": 0.05},
    "night":        {"sleepy": 0.25},
    "pomodoro_start": {"focused": 0.30},
    "pomodoro_end": {"focused": -0.15, "happy": 0.10},
}
