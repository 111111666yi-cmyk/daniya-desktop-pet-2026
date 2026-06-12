"""PomodoroSession — a user-started focus timer that warns when distraction
software is running and rewards affinity on completion.

Reuses the psutil background-scan pattern from focus_mode.py. The session only
scans while it is active (user-started), so there is no background behaviour when
idle. Distraction detection is process-name based and fully configurable.
"""
from __future__ import annotations

import threading
import time
from typing import Any, Iterable

from PySide6.QtCore import QObject, QTimer, Signal, Slot

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore


_DEFAULT_DISTRACTIONS = [
    "steam.exe", "epicgameslauncher.exe", "wegame.exe",
    "genshinimpact.exe", "yuanshen.exe", "qqgame.exe",
    "potplayermini64.exe", "potplayer.exe", "vlc.exe",
]


def find_distraction(running_processes: Iterable[str], distraction_list: Iterable[str]) -> str | None:
    """Return the first distraction process found among the running ones, else None."""
    running_lower = {str(p).lower() for p in running_processes}
    for name in distraction_list:
        if str(name).lower() in running_lower:
            return str(name)
    return None


class PomodoroSession(QObject):
    distraction_detected = Signal(str)  # distraction process name
    completed = Signal()                # session finished naturally
    started = Signal(int)               # minutes
    cancelled = Signal()

    def __init__(self, config: dict[str, Any] | None = None, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._active = False
        self._last_warn = 0.0
        self.update_config(config or {})

        self._scan_timer = QTimer(self)
        self._scan_timer.timeout.connect(self._scan)
        self._end_timer = QTimer(self)
        self._end_timer.setSingleShot(True)
        self._end_timer.timeout.connect(self._finish)

    def update_config(self, config: dict[str, Any]) -> None:
        config = config if isinstance(config, dict) else {}
        self._default_minutes = max(1, int(config.get("default_minutes", 25)))
        raw = config.get("distraction_process_list")
        self._distractions = (
            [str(x) for x in raw if str(x).strip()]
            if isinstance(raw, list) else list(_DEFAULT_DISTRACTIONS)
        )
        self._scan_interval_ms = max(5, int(config.get("scan_interval_sec", 30))) * 1000
        self._warn_cooldown = max(0, int(config.get("warn_cooldown_sec", 60)))
        self._reward_affinity = max(0, int(config.get("reward_affinity", 3)))

    @property
    def active(self) -> bool:
        return self._active

    @property
    def reward_affinity(self) -> int:
        return self._reward_affinity

    def start(self, minutes: int | None = None) -> int:
        mins = max(1, int(minutes)) if minutes else self._default_minutes
        self._active = True
        self._last_warn = 0.0
        self._end_timer.start(mins * 60 * 1000)
        self._scan_timer.start(self._scan_interval_ms)
        self.started.emit(mins)
        return mins

    def cancel(self) -> None:
        if not self._active:
            return
        self._stop_timers()
        self._active = False
        self.cancelled.emit()

    def _finish(self) -> None:
        if not self._active:
            return
        self._stop_timers()
        self._active = False
        self.completed.emit()

    def _stop_timers(self) -> None:
        self._scan_timer.stop()
        self._end_timer.stop()

    def _scan(self) -> None:
        if not self._active or not psutil:
            return
        threading.Thread(target=self._scan_bg, daemon=True).start()

    def _scan_bg(self) -> None:
        try:
            running = {
                p.info["name"]
                for p in psutil.process_iter(["name"])
                if p.info and p.info.get("name")
            }
        except Exception:
            return
        hit = find_distraction(running, self._distractions)
        if hit:
            self._report_distraction(hit)

    @Slot(str)
    def _report_distraction(self, name: str) -> None:
        now = time.monotonic()
        if now - self._last_warn < self._warn_cooldown:
            return
        self._last_warn = now
        self.distraction_detected.emit(name)
