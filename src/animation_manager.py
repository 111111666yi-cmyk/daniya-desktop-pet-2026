from __future__ import annotations
from typing import TYPE_CHECKING, Callable
from pathlib import Path
from PySide6.QtCore import QObject, QTimer

from .action_manifest import ActionManifest
from .state_manager import StateManager

if TYPE_CHECKING:
    from .asset_manager import AssetManager
    from .pet_window import PetWindow

class AnimationManager(QObject):
    def __init__(self, window: "PetWindow", asset_manager: "AssetManager") -> None:
        super().__init__(window)
        self.window = window
        self.asset_manager = asset_manager
        
        self.manifest = ActionManifest()
        self.state_manager = StateManager()
        
        self.current_action = "idle"
        self.current_frames: list[str] = []
        self.frame_index = 0
        
        self.animation_timer = QTimer(self)
        self.animation_timer.timeout.connect(self.next_frame)
        
        self.pixmap_callback: Callable[[str], None] | None = None

    @property
    def current_state(self) -> str:
        return self.state_manager.get_state()

    def set_pixmap_callback(self, callback: Callable[[str], None]) -> None:
        self.pixmap_callback = callback

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
            
        self.current_action = action_name
        self.current_frames = self.manifest.get_frames(action_name)
        self.frame_index = 0
        
        # Stop previous timer
        self.animation_timer.stop()
        
        if not self.current_frames:
            # Absolute fallback
            self._emit_frame("normal1.png")
            return
            
        self._emit_frame(self.current_frames[0])
        
        duration = config.get("duration_ms", 500)
        if len(self.current_frames) > 1 or config.get("loop", False):
            # QTimer fires every (duration / len(frames)) approximately
            frame_duration = max(50, int(duration / max(1, len(self.current_frames))))
            self.animation_timer.start(frame_duration)
        else:
            # Single frame non-looping. Just wait duration and then end.
            self.animation_timer.start(duration)

    def next_frame(self) -> None:
        if not self.current_frames:
            self.animation_timer.stop()
            self.play_idle()
            return
            
        self.frame_index += 1
        
        if self.frame_index >= len(self.current_frames):
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
        # Resolve full path using manifest's base_dir
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
