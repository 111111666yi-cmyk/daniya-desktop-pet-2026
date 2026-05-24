from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer

if TYPE_CHECKING:
    from .asset_manager import AssetManager
    from .pet_window import PetWindow


class AnimationManager(QObject):
    def __init__(self, window: "PetWindow", asset_manager: "AssetManager") -> None:
        super().__init__(window)
        self.window = window
        self.asset_manager = asset_manager
        self.current_state = "idle"
        self.frame_index = 0
        self.is_dragging = False
        self.is_talking = False
        self.hovered = False
        self._idle_scale_up = False

        self.idle_timer = QTimer(self)
        self.idle_timer.timeout.connect(self._tick_idle)
        self.idle_timer.start(900)

    def set_state(self, state: str) -> None:
        if state == "normal1":
            state = "idle"
        elif state == "normal2":
            state = "talking"

        self.current_state = state
        self.is_talking = state == "talking"
        if state == "talking":
            self._render_next_frame("talking")
            return
        if state == "idle":
            self._render_idle()
            return
        self._render_next_frame(state)

    def set_hovered(self, hovered: bool) -> None:
        self.hovered = hovered
        if self.is_dragging or self.is_talking:
            return
        if hovered:
            self.current_state = "hover"
            self._render_first_frame("hover", scale=1.03)
        else:
            self.set_state("idle")

    def set_dragging(self, dragging: bool) -> None:
        self.is_dragging = dragging
        if dragging:
            self.current_state = "dragging"
            self._render_first_frame("dragging", scale=1.02)
        else:
            self.set_state("hover" if self.hovered else "idle")

    def trigger_clicked(self) -> None:
        if self.is_dragging or self.is_talking:
            return
        self.current_state = "clicked"
        self._render_first_frame("clicked", scale=1.08)
        QTimer.singleShot(140, lambda: self._render_first_frame("clicked", scale=0.98))
        QTimer.singleShot(280, lambda: self.set_state("hover" if self.hovered else "idle"))

    def trigger_happy(self) -> None:
        if self.is_dragging or self.is_talking:
            return
        self.current_state = "happy"
        self._render_first_frame("happy", scale=1.06)
        QTimer.singleShot(360, lambda: self.set_state("hover" if self.hovered else "idle"))

    def trigger_remind(self) -> None:
        if self.is_dragging:
            return
        self.current_state = "remind"
        self._render_first_frame("remind", scale=1.04)

    def trigger_sleeping(self) -> None:
        if self.is_dragging or self.is_talking:
            return
        self.current_state = "sleeping"
        self._render_first_frame("sleeping", scale=1.0)

    def refresh(self) -> None:
        state = self.current_state or "idle"
        self.set_state(state)

    def _tick_idle(self) -> None:
        if self.current_state != "idle" or self.is_dragging or self.is_talking:
            return
        self._idle_scale_up = not self._idle_scale_up
        self._render_idle()

    def _render_idle(self) -> None:
        self._render_first_frame("idle", scale=1.0)

    def _render_next_frame(self, state: str) -> None:
        frames = self.asset_manager.frames_for_state(state)
        if not frames:
            return
        path = frames[self.frame_index % len(frames)]
        self.frame_index += 1
        self.window.render_pet_pixmap(path)

    def _render_first_frame(self, state: str, scale: float = 1.0) -> None:
        frames = self.asset_manager.frames_for_state(state)
        if not frames:
            return
        self.window.render_pet_pixmap(Path(frames[0]), visual_scale=scale)
