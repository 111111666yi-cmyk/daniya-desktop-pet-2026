from __future__ import annotations
from typing import TYPE_CHECKING, Callable
from pathlib import Path
from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QPixmap

from .action_manifest import ActionManifest
from .renderer import Renderer
from .state_manager import StateManager

if TYPE_CHECKING:
    from .asset_manager import AssetManager
    from .pet_window import PetWindow
class AnimationManager(QObject):
    def __init__(self, window: "PetWindow", asset_manager: "AssetManager", renderer: Renderer | None = None) -> None:
        super().__init__(window)
        self.window = window
        self.asset_manager = asset_manager
        self.renderer = renderer
        self.manifest = ActionManifest(self.asset_manager.active_asset_dir())
        self.state_manager = StateManager()

        self.current_action = "idle"
        self.current_frames: list[str] = []
        self.frame_index = 0
        self._in_transition = False
        self._pending_action: str | None = None

        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.next_frame)

        self.pixmap_callback: Callable[[str], None] | None = None
        self.display_callback: Callable[[QPixmap], None] | None = None

    @property
    def current_state(self) -> str:
        return self.state_manager.get_state()

    def set_pixmap_callback(self, callback: Callable[[str], None]) -> None:
        self.pixmap_callback = callback

    def set_display_callback(self, callback: Callable[[QPixmap], None]) -> None:
        self.display_callback = callback

    def reload_manifest(self) -> None:
        self.manifest.load_manifest()

    def play_idle(self) -> None:
        self.state_manager.return_to_idle()
        self.play(self.state_manager.state_to_action("idle"))

    def stop(self) -> None:
        self.animation_timer.stop()

    def play(self, action_name: str) -> None:
        config = self.manifest.get_action_config(action_name)
        if not config:
            action_name = "idle"
            config = self.manifest.get_action_config("idle")

        # Build transition frames: current action's out + new action's in
        transition_frames: list[str] = []
        if not self._in_transition:
            old_config = self.manifest.get_action_config(self.current_action)
            if old_config:
                transition_frames.extend(old_config.get("transition_out", []))
            transition_frames.extend(config.get("transition_in", []))

        if transition_frames and not self._in_transition:
            resolved = self.manifest._verify_frames(transition_frames)
            if resolved:
                self._pending_action = action_name
                self._in_transition = True
                self.current_action = "__transition__"
                self.current_frames = resolved
                self.frame_index = 0
                self.animation_timer.stop()
                self._emit_frame(self.current_frames[0])
                t_dur = config.get("transition_duration_ms", 120)
                self.animation_timer.start(max(60, t_dur))
                return

        self._in_transition = False
        self._pending_action = None
        self.current_action = action_name

        try:
            if hasattr(self.asset_manager, "select_frames_for_state") and callable(self.asset_manager.select_frames_for_state):
                frames = self.asset_manager.select_frames_for_state(action_name)
                self.current_frames = [str(f) for f in frames]
            else:
                self.current_frames = self.manifest.get_frames(action_name)
        except Exception:
            self.current_frames = self.manifest.get_frames(action_name)

        self.frame_index = 0
        self.animation_timer.stop()

        if not self.current_frames:
            self._emit_frame("normal1.png")
            return

        self._emit_frame(self.current_frames[0])

        duration = config.get("duration_ms", 500)
        is_loop = config.get("loop", False)

        if len(self.current_frames) == 1:
            if is_loop:
                return
            else:
                self.animation_timer.start(max(200, duration))
        elif len(self.current_frames) > 1:
            frame_duration = max(80, duration)
            self.animation_timer.start(frame_duration)

    def next_frame(self) -> None:
        if not self.current_frames:
            self.animation_timer.stop()
            self.play_idle()
            return

        self.frame_index += 1

        if self.frame_index >= len(self.current_frames):
            if self._in_transition and self._pending_action:
                self.animation_timer.stop()
                pending = self._pending_action
                self._in_transition = False
                self._pending_action = None
                self.play(pending)
                return

            config = self.manifest.get_action_config(self.current_action)
            is_loop = config.get("loop", False) if config else False

            if is_loop:
                self.frame_index = 0
            else:
                self.animation_timer.stop()
                self.play_idle()
                return

        self._emit_frame(self.current_frames[self.frame_index])

    def _emit_frame(self, frame_name: str) -> None:
        if self.renderer and self.display_callback:
            target_height = self.asset_manager.target_height()
            dpr = self.window._current_device_pixel_ratio()
            pixmap = self.renderer.render_frame(frame_name, target_height, dpr)
            if pixmap:
                self.display_callback(pixmap)
            return

        p = Path(frame_name)
        if p.is_absolute():
            path = p
        else:
            path = self.manifest.base_dir / frame_name

        if self.pixmap_callback:
            self.pixmap_callback(str(path))

    # Compatibility methods for PetWindow
    def set_state(self, state: str) -> None:
        if self.state_manager.set_state(state):
            action = self.state_manager.state_to_action(self.state_manager.get_state())
            self.play(action)

    def set_dragging(self, dragging: bool) -> None:
        if dragging:
            self.set_state("dragging")
        else:
            self.set_state("idle")

    def set_hovered(self, hovered: bool) -> None:
        pass # Optional in v0.41, fallback to idle if not supported natively.

    def set_walking(self, walking: bool) -> None:
        if walking:
            self.set_state("walking")
        else:
            self.set_state("idle")

    def set_edge_peek(self, side: str) -> None:
        if side == "left":
            self.set_state("edge_peek_left")
        elif side == "right":
            self.set_state("edge_peek_right")
        else:
            self.set_state("idle")

    def trigger_clicked(self) -> None:
        self.set_state("clicked")

    def trigger_happy(self) -> None:
        self.set_state("happy")

    def trigger_remind(self) -> None:
        self.set_state("remind")

    def trigger_sleeping(self) -> None:
        self.set_state("sleeping")

    def refresh(self) -> None:
        # Refresh current animation
        state = self.state_manager.get_state()
        self.play(self.state_manager.state_to_action(state))

