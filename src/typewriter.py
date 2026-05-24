from __future__ import annotations

import re
import time
from collections import deque
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QLabel


class Typewriter(QObject):
    sequence_finished = Signal()

    def __init__(
        self,
        label: QLabel,
        set_pet_state: Callable[[str], None],
        config: dict[str, Any],
    ) -> None:
        super().__init__()
        self.label = label
        self.set_pet_state = set_pet_state
        type_config = config.get("typewriter", {})
        self.char_interval_ms = int(type_config.get("char_interval_ms", 35))
        self.mouth_interval_ms = int(type_config.get("mouth_interval_ms", 180))
        self.click_cooldown_ms = int(type_config.get("click_cooldown_ms", 500))
        self.auto_next_ms = int(type_config.get("auto_next_ms", 2000))
        self.auto_hide_ms = int(type_config.get("auto_hide_ms", 3000))
        states = config.get("pet", {}).get("states", {})
        self.idle_state = str(states.get("idle", "idle")) if isinstance(states, dict) else "idle"
        self.speaking_state = str(states.get("speaking", "talking")) if isinstance(states, dict) else "talking"

        self.queue: deque[str] = deque()
        self.current_text = ""
        self.index = 0
        self.is_typing = False
        self.mouth_open = False
        self.cooldown_until = 0.0

        self.char_timer = QTimer(self)
        self.char_timer.timeout.connect(self._tick_char)
        self.mouth_timer = QTimer(self)
        self.mouth_timer.timeout.connect(self._tick_mouth)
        self.auto_timer = QTimer(self)
        self.auto_timer.setSingleShot(True)
        self.auto_timer.timeout.connect(self._auto_continue)

    def speak(self, text: str) -> None:
        self.stop()
        parts = [part.strip() for part in split_sentences(text) if part.strip()]
        self.queue = deque(parts or [text.strip()])
        self.label.show()
        self._start_next()

    def click(self) -> None:
        now = time.monotonic()
        if self.is_typing:
            self._show_full_current()
            return
        if now < self.cooldown_until:
            return
        if self.queue:
            self._start_next()
        else:
            self.hide()

    def stop(self) -> None:
        self.char_timer.stop()
        self.mouth_timer.stop()
        self.auto_timer.stop()
        self.is_typing = False
        self.set_pet_state(self.idle_state)

    def hide(self) -> None:
        self.stop()
        self.label.hide()
        self.sequence_finished.emit()

    def _start_next(self) -> None:
        if not self.queue:
            self.hide()
            return
        self.auto_timer.stop()
        self.current_text = self.queue.popleft()
        self.index = 0
        self.is_typing = True
        self.label.setText("")
        self.label.show()
        self.mouth_open = False
        self.char_timer.start(self.char_interval_ms)
        self.mouth_timer.start(self.mouth_interval_ms)

    def _tick_char(self) -> None:
        if self.index >= len(self.current_text):
            self._finish_current()
            return
        self.index += 1
        self.label.setText(self.current_text[: self.index])

    def _tick_mouth(self) -> None:
        self.mouth_open = not self.mouth_open
        self.set_pet_state(self.speaking_state if self.mouth_open else self.idle_state)

    def _show_full_current(self) -> None:
        self.label.setText(self.current_text)
        self.index = len(self.current_text)
        self._finish_current()

    def _finish_current(self) -> None:
        self.char_timer.stop()
        self.mouth_timer.stop()
        self.is_typing = False
        self.cooldown_until = time.monotonic() + self.click_cooldown_ms / 1000
        self.set_pet_state(self.idle_state)
        self.auto_timer.start(self.auto_next_ms if self.queue else self.auto_hide_ms)

    def _auto_continue(self) -> None:
        if self.queue:
            self._start_next()
        else:
            self.hide()


def split_sentences(text: str) -> list[str]:
    stripped = text.strip()
    if not stripped:
        return []
    parts = re.split(r"(?<=[。！？!?；;])\s*", stripped)
    return [part for part in parts if part]
