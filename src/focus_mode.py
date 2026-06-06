from __future__ import annotations

import threading
from typing import Any
from PySide6.QtCore import QObject, QTimer, Signal, Slot

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore

class FocusModeManager(QObject):
    focus_state_changed = Signal(bool)  # Emits True when entering, False when exiting

    def __init__(self, sample_interval_ms: int = 300_000, process_whitelist: list[str] | None = None) -> None:
        super().__init__()
        self.is_active = False
        self.auto_focus_active = False
        self.auto_detect = False
        default_whitelist = {"game.exe", "eldenring.exe", "lol.exe", "valorant.exe"}
        if process_whitelist is None:
            self.game_whitelist = default_whitelist
        else:
            self.game_whitelist = {item.strip().lower() for item in process_whitelist if str(item).strip()}

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.scan_processes)
        self.timer.setInterval(max(1000, int(sample_interval_ms)))

    def set_auto_detect(self, val: bool) -> None:
        self.auto_detect = val
        if val:
            if not self.timer.isActive():
                self.timer.start()
        else:
            self.timer.stop()

    def enter_focus_mode(self) -> None:
        if not self.is_active:
            self.is_active = True
            self.focus_state_changed.emit(True)

    def exit_focus_mode(self) -> None:
        if self.is_active:
            self.is_active = False
            self.auto_focus_active = False
            self.focus_state_changed.emit(False)

    def should_suppress_notifications(self) -> bool:
        # Return True if normal random bubbles/reminders should be silenced
        return self.is_active

    def scan_processes(self) -> None:
        if not self.auto_detect or not psutil:
            return
        threading.Thread(target=self._scan_processes_bg, daemon=True).start()

    def _scan_processes_bg(self) -> None:
        try:
            current_processes = {p.info["name"].lower() for p in psutil.process_iter(["name"]) if p.info and p.info.get("name")}
            game_running = any(g.lower() in current_processes for g in self.game_whitelist)
        except Exception:
            return
        self._apply_scan_result(game_running)

    @Slot()
    def _apply_scan_result(self, game_running: bool) -> None:
        if game_running:
            if not self.is_active:
                self.auto_focus_active = True
                self.enter_focus_mode()
        else:
            if self.is_active and self.auto_focus_active:
                self.exit_focus_mode()
