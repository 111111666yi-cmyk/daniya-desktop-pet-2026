from __future__ import annotations
import time
from typing import Callable
from PySide6.QtCore import QObject, QPoint, QTimer

class InteractionDetector(QObject):
    def __init__(
        self,
        long_press_ms: int = 600,
        drag_threshold: int = 8,
        on_single_click: Callable[[], None] | None = None,
        on_double_click: Callable[[], None] | None = None,
        on_long_press: Callable[[], None] | None = None,
        on_drag_start: Callable[[QPoint], None] | None = None,
        on_drag: Callable[[QPoint], None] | None = None,
        on_drag_finish: Callable[[QPoint], None] | None = None,
    ) -> None:
        super().__init__()
        self.long_press_ms = long_press_ms
        self.drag_threshold = drag_threshold

        self.on_single_click = on_single_click
        self.on_double_click = on_double_click
        self.on_long_press = on_long_press
        self.on_drag_start = on_drag_start
        self.on_drag = on_drag
        self.on_drag_finish = on_drag_finish

        self.press_pos = QPoint()
        self.press_time = 0.0
        self.last_release_time = 0.0

        self.is_pressed = False
        self.is_dragging = False
        self.long_press_triggered = False

        self.long_press_timer = QTimer(self)
        self.long_press_timer.setSingleShot(True)
        self.long_press_timer.timeout.connect(self._handle_long_press_timeout)

        self.click_delay_timer = QTimer(self)
        self.click_delay_timer.setSingleShot(True)
        self.click_delay_timer.timeout.connect(self._handle_single_click_timeout)

    def handle_press(self, global_pos: QPoint) -> None:
        self.press_pos = global_pos
        self.press_time = time.time()
        self.is_pressed = True
        self.is_dragging = False
        self.long_press_triggered = False

        self.long_press_timer.start(self.long_press_ms)

    def handle_move(self, global_pos: QPoint) -> None:
        if self.is_dragging:
            if self.on_drag:
                self.on_drag(global_pos)
            return

        delta = global_pos - self.press_pos
        if abs(delta.x()) + abs(delta.y()) >= self.drag_threshold:
            self.long_press_timer.stop()
            self.click_delay_timer.stop()

            self.is_dragging = True
            if self.on_drag_start:
                self.on_drag_start(self.press_pos)
            if self.on_drag:
                self.on_drag(global_pos)

    def handle_release(self, global_pos: QPoint) -> None:
        self.long_press_timer.stop()
        self.is_pressed = False

        if self.is_dragging:
            self.is_dragging = False
            if self.on_drag_finish:
                self.on_drag_finish(global_pos)
            return

        if self.long_press_triggered:
            self.long_press_triggered = False
            return

        if self.click_delay_timer.isActive():
            self.click_delay_timer.stop()
            if self.on_double_click:
                self.on_double_click()
        else:
            self.click_delay_timer.start(300)

    def _handle_long_press_timeout(self) -> None:
        self.long_press_triggered = True
        if self.on_long_press:
            self.on_long_press()

    def _handle_single_click_timeout(self) -> None:
        if self.on_single_click:
            self.on_single_click()
