from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QPoint, QTimer, Signal

if TYPE_CHECKING:
    from ..pet_window import PetWindow


class DemoMode(QObject):
    finished = Signal()

    def __init__(self, window: "PetWindow") -> None:
        super().__init__()
        self._window = window
        self._running = False
        self._steps: list[tuple[int, str]] = []
        self._step_index = 0

    def is_running(self) -> bool:
        return self._running

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._step_index = 0
        bounds = self._window._screen_bounds_for_position(self._window.pos())
        cx = bounds.x() + bounds.width() // 2 - self._window.width() // 2
        cy = bounds.y() + bounds.height() - self._window.height()
        right_x = bounds.x() + bounds.width() - self._window.width() - 40
        left_x = bounds.x() + 10

        self._steps = [
            (0, "idle"),
            (1500, f"walk:{cx},{cy}"),
            (4000, "happy"),
            (2000, f"walk:{right_x},{cy}"),
            (5000, "edge_peek_right"),
            (2500, f"walk:{cx},{cy}"),
            (4000, "taskbar_sit"),
            (3000, f"walk:{left_x},{cy}"),
            (4500, "edge_peek_left"),
            (2500, f"walk:{cx},{cy}"),
            (4000, "idle"),
            (2000, "done"),
        ]
        self._run_next()

    def stop(self) -> None:
        self._running = False
        self._step_index = len(self._steps)

    def _run_next(self) -> None:
        if not self._running or self._step_index >= len(self._steps):
            self._running = False
            self.finished.emit()
            return

        delay, cmd = self._steps[self._step_index]
        self._step_index += 1
        QTimer.singleShot(delay, self._execute_step_factory(cmd))

    def _execute_step_factory(self, cmd: str):
        def execute():
            if not self._running:
                return
            self._execute(cmd)
            self._run_next()
        return execute

    def _execute(self, cmd: str) -> None:
        if cmd == "done":
            self._running = False
            return
        if cmd.startswith("walk:"):
            parts = cmd[5:].split(",")
            x, y = int(parts[0]), int(parts[1])
            self._window.move_near(QPoint(x + self._window.width() // 2, y + self._window.height() - 12))
        elif cmd in ("idle", "happy", "taskbar_sit", "edge_peek_left", "edge_peek_right", "sleep"):
            anim = self._window.animation_manager
            if cmd == "idle":
                anim.set_walking(False)
                anim.set_state("idle")
            elif cmd == "happy":
                anim.trigger_happy()
            elif cmd == "taskbar_sit":
                anim.set_state("taskbar_sit")
            elif cmd.startswith("edge_peek_"):
                side = cmd.split("_")[-1]
                anim.set_edge_peek(side)
            elif cmd == "sleep":
                anim.set_state("sleep")
