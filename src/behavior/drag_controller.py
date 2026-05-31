from __future__ import annotations
import time
from typing import Callable
from PySide6.QtCore import QObject, QPoint
from PySide6.QtWidgets import QWidget

class DragController(QObject):
    def __init__(self, window: QWidget, on_state_changed: Callable[[str], None] | None = None) -> None:
        super().__init__()
        self.window = window
        self.on_state_changed = on_state_changed
        self.drag_start_pos = QPoint()
        self.drag_start_window_pos = QPoint()
        self.last_move_time = 0.0
        self.velocity = 0.0

    def start_drag(self, global_pos: QPoint) -> None:
        self.drag_start_pos = global_pos
        self.drag_start_window_pos = self.window.pos()
        self.last_move_time = time.time()
        self.velocity = 0.0
        if self.on_state_changed:
            self.on_state_changed("drag")

    def drag(self, global_pos: QPoint) -> None:
        now = time.time()
        dt = now - self.last_move_time

        delta = global_pos - self.drag_start_pos
        new_pos = self.drag_start_window_pos + delta

        if dt > 0:
            current_pos = self.window.pos()
            dist = (new_pos - current_pos).manhattanLength()
            self.velocity = dist / dt

        self.last_move_time = now
        self.window.move(new_pos)

    def finish_drag(self, global_pos: QPoint) -> tuple[QPoint, float]:
        return global_pos, self.velocity
