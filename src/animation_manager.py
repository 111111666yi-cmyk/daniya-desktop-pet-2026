from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer

if TYPE_CHECKING:
    from .asset_manager import AssetManager
    from .pet_window import PetWindow


V041_STATE_FALLBACKS = {
    "soft_idle": "idle",
    "close_idle": "happy",
    "bubble": "happy",
    "look_away": "idle",
    "drag": "dragging",
}


class AnimationManager(QObject):
    def __init__(self, window: "PetWindow", asset_manager: "AssetManager") -> None:
        super().__init__(window)
        self.window = window
        self.asset_manager = asset_manager
        self.current_state = "idle"
        self.frame_indices: dict[str, int] = {}
        self.sequence_frames: dict[str, list[Path]] = {}
        self.is_dragging = False
        self.is_talking = False
        self.hovered = False
        self._last_frame_debug: tuple[str, str] | None = None

        self.idle_timer = QTimer(self)
        self.idle_timer.timeout.connect(self._tick_idle)
        pet_config = getattr(window, "app_config", {}).get("pet", {})
        idle_interval_ms = int(pet_config.get("idle_animation_interval_ms", 10000))
        self.idle_timer.start(max(10000, idle_interval_ms))

        self.drag_hold_timer = QTimer(self)
        self.drag_hold_timer.timeout.connect(self._tick_drag_hold)
        self.drag_hold_timer.setInterval(220)

        self.walk_timer = QTimer(self)
        self.walk_timer.timeout.connect(self._tick_walk)
        self.walk_timer.setInterval(120)

    def set_state(self, state: str) -> None:
        requested_state = state
        if state == "normal1":
            state = "idle"
        elif state in {"normal2", "talk", "speaking"}:
            state = "talking"
        state = V041_STATE_FALLBACKS.get(state, state)
        if requested_state != state:
            print(f"[Daniya] action fallback requested={requested_state} state={state}")

        previous_state = self.current_state
        self.current_state = state
        self.is_talking = state == "talking"
        if previous_state != state:
            self._reset_sequence(state)
        if state != "dragging":
            self.drag_hold_timer.stop()
        if state != "walking":
            self.walk_timer.stop()
        if state == "talking":
            self._render_next_frame("talking")
            return
        if state == "idle":
            self._render_idle()
            return
        self._render_next_frame(state)

    def set_hovered(self, hovered: bool) -> None:
        self.hovered = hovered
        pet_config = getattr(self.window, "app_config", {}).get("pet", {})
        if not bool(pet_config.get("hover_animation_enabled", False)):
            return
        if self.is_dragging or self.is_talking:
            return
        if hovered:
            self.current_state = "hover"
            self._render_first_frame("hover")
        else:
            self.set_state("idle")

    def set_dragging(self, dragging: bool) -> None:
        pet_config = getattr(self.window, "app_config", {}).get("pet", {})
        enabled_modules = pet_config.get("enabled_action_modules", {})
        drag_enabled = not isinstance(enabled_modules, dict) or bool(enabled_modules.get("E_QQ_pet_drag_system", True))
        self.is_dragging = dragging
        if dragging:
            self.current_state = "dragging"
            self.drag_hold_timer.stop()
            if not drag_enabled:
                self._render_first_frame("idle")
                return
            self._reset_sequence("drag_pickup")
            self._reset_sequence("drag_hold")
            self._render_first_frame("drag_pickup")
            QTimer.singleShot(120, lambda: self._render_if_current("dragging", 1, frame_state="drag_pickup"))
            QTimer.singleShot(240, self._start_drag_hold_if_current)
        else:
            self.drag_hold_timer.stop()
            self.current_state = "drag_drop"
            self._reset_sequence("drag_drop")
            self._render_first_frame("drag_drop")
            QTimer.singleShot(130, lambda: self._render_if_current("drag_drop", 1, frame_state="drag_drop"))
            QTimer.singleShot(270, self._restore_after_drag_drop)

    def trigger_clicked(self) -> None:
        if self.is_dragging or self.is_talking:
            return
        self.current_state = "clicked"
        self._render_first_frame("clicked")
        QTimer.singleShot(140, lambda: self._render_if_current("clicked", 1))
        QTimer.singleShot(280, lambda: self.set_state("idle"))

    def trigger_happy(self) -> None:
        if self.is_dragging or self.is_talking:
            return
        self.current_state = "happy"
        self._render_first_frame("happy")
        QTimer.singleShot(180, lambda: self._render_if_current("happy", 1))
        QTimer.singleShot(520, lambda: self.set_state("idle"))

    def trigger_remind(self) -> None:
        if self.is_dragging:
            return
        self.current_state = "remind"
        self._render_first_frame("remind")
        QTimer.singleShot(180, lambda: self._render_if_current("remind", 1))
        QTimer.singleShot(360, lambda: self._render_if_current("remind", 2))

    def trigger_sleeping(self) -> None:
        if self.is_dragging or self.is_talking:
            return
        self.current_state = "sleeping"
        self._reset_sequence("sleeping")
        self._render_first_frame("sleeping")
        frames = self._frames_for_sequence("sleeping")
        for index in range(1, min(len(frames), 5)):
            QTimer.singleShot(260 * index, lambda i=index: self._render_if_current("sleeping", i))

    def refresh(self) -> None:
        state = self.current_state or "idle"
        self.set_state(state)

    def _tick_idle(self) -> None:
        if self.current_state != "idle" or self.is_dragging or self.is_talking:
            return
        self._render_idle()

    def _render_idle(self) -> None:
        self._render_next_frame("idle")

    def _start_drag_hold_if_current(self) -> None:
        if self.current_state != "dragging":
            return
        self._tick_drag_hold()
        self.drag_hold_timer.start()

    def _tick_drag_hold(self) -> None:
        if self.current_state == "dragging":
            self._render_next_frame("drag_hold")

    def _tick_walk(self) -> None:
        if self.current_state == "walking":
            self._render_next_frame("walking")

    def _restore_after_drag_drop(self) -> None:
        if self.current_state == "drag_drop":
            self.set_state("idle")

    def set_action_module(self, module: str) -> str:
        active = self.asset_manager.set_active_action_module(module)
        self.frame_indices.clear()
        self.sequence_frames.clear()
        self.set_state("idle")
        return active

    def set_edge_peek(self, side: str) -> None:
        if self.is_dragging or self.is_talking or self.current_state == "walking":
            return
        if self.current_state != "idle":
            self.current_state = "idle"
            self._reset_sequence("idle")
        self._render_first_frame("idle")

    def set_walking(self, walking: bool) -> None:
        if walking:
            self.current_state = "walking"
            self._reset_sequence("walking")
            self._tick_walk()
            self.walk_timer.start()
        else:
            self.walk_timer.stop()
            if self.current_state == "walking":
                self.set_state("idle")

    def _render_next_frame(self, state: str, scale: float = 1.0) -> None:
        frames = self._frames_for_sequence(state)
        if not frames:
            print(f"[Daniya] selected frame path state={state} path=<none> pixmap_candidate=false")
            return
        index = self.frame_indices.get(state, 0)
        path = frames[index % len(frames)]
        self._print_frame_debug(state, path)
        next_index = (index + 1) % len(frames)
        self.frame_indices[state] = next_index
        if next_index == 0:
            self.sequence_frames.pop(state, None)
        self.window.render_pet_pixmap(path, visual_scale=scale)

    def _render_first_frame(self, state: str, scale: float = 1.0) -> None:
        self._render_frame(state, 0, scale)

    def _render_if_current(
        self,
        state: str,
        index: int,
        scale: float = 1.0,
        frame_state: str | None = None,
    ) -> None:
        if self.current_state == state:
            self._render_frame(frame_state or state, index, scale)

    def _render_frame(self, state: str, index: int, scale: float = 1.0) -> None:
        frames = self._frames_for_sequence(state)
        if not frames:
            print(f"[Daniya] selected frame path state={state} path=<none> pixmap_candidate=false")
            return
        path = Path(frames[index % len(frames)])
        self._print_frame_debug(state, path)
        self.window.render_pet_pixmap(path, visual_scale=scale)

    def _frames_for_sequence(self, state: str) -> list[Path]:
        frames = self.sequence_frames.get(state)
        if frames:
            return frames
        frames = self.asset_manager.select_frames_for_state(state)
        self.sequence_frames[state] = frames
        return frames

    def _reset_sequence(self, state: str) -> None:
        self.frame_indices.pop(state, None)
        self.sequence_frames.pop(state, None)

    def _print_frame_debug(self, state: str, path: Path) -> None:
        key = (state, str(path))
        if key == self._last_frame_debug:
            return
        self._last_frame_debug = key
        print(f"[Daniya] selected frame path state={state} path={path} exists={path.exists()}")
