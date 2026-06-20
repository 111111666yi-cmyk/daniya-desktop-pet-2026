from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

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
        self._cached_idle_frames: list[str] | None = None
        self._last_emitted_frame: str | None = None

        self._drag_active = False
        self._locomotion_active = False
        self._locomotion_profile = self.asset_manager.locomotion_profile()
        self._locomotion_distance_px = 0.0

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
        self.manifest.load_manifest(self.asset_manager.active_asset_dir())

    def play_idle(self) -> None:
        self._drag_active = False
        self._locomotion_active = False
        self.state_manager.return_to_idle()
        self.play("idle")

    def stop(self) -> None:
        self.animation_timer.stop()

    def play(self, action_name: str) -> None:
        config = self._action_config(action_name)
        if not config:
            action_name = "idle"
            config = self._action_config("idle") or {}

        if action_name == "walking" and self._locomotion_active:
            if self.current_action != "walking":
                self._enter_walking_loop()
            return

        if action_name == self.current_action and not self._in_transition and self.animation_timer.isActive():
            return

        transition_frames: list[str] = []
        if not self._in_transition:
            old_config = self._action_config(self.current_action) or {}
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
                self._emit_frame(self.current_frames[0], config=config)
                t_dur = int(config.get("transition_duration_ms", 120))
                self.animation_timer.start(max(40, t_dur))
                return

        if action_name != "idle":
            self._cached_idle_frames = None

        self._in_transition = False
        self._pending_action = None
        self.current_action = action_name
        self.current_frames = self._frames_for_action(action_name)
        self.frame_index = 0
        self.animation_timer.stop()

        if action_name == "idle" and self.current_frames:
            self._cached_idle_frames = self.current_frames[:]

        if not self.current_frames:
            self._emit_frame("normal1.png", config=config)
            return

        self._emit_frame(self.current_frames[0], config=config)

        if action_name == "walking":
            return

        duration = int(config.get("duration_ms", 500))
        is_loop = bool(config.get("loop", False))
        if len(self.current_frames) == 1:
            if is_loop:
                return
            self.animation_timer.start(max(120, duration))
            return
        self.animation_timer.start(max(40, duration))

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

            if self.current_action == "drag_pickup":
                self.animation_timer.stop()
                self.play("drag_hold" if self._drag_active else "drag_drop")
                return
            if self.current_action == "drag_drop":
                self.animation_timer.stop()
                self.play_idle()
                return
            if self.current_action == "walk_start":
                if self._locomotion_active:
                    self._enter_walking_loop()
                else:
                    self.play("walk_stop")
                return
            if self.current_action == "walk_stop":
                self.animation_timer.stop()
                self.play_idle()
                return

            config = self._action_config(self.current_action)
            is_loop = bool(config.get("loop", False)) if config else False
            if is_loop:
                self.frame_index = 0
            else:
                self.animation_timer.stop()
                self.play_idle()
                return

        if self.current_frames:
            self._emit_frame(
                self.current_frames[self.frame_index],
                config=self._action_config(self.current_action),
            )

    def start_locomotion(self) -> None:
        self._locomotion_profile = self.asset_manager.locomotion_profile()
        self._locomotion_distance_px = 0.0
        self._locomotion_active = True
        self.state_manager.set_state("walking")
        self.play("walk_start")

    def update_locomotion(
        self,
        *,
        step_distance_px: float,
        cumulative_distance_px: float,
        speed_px_per_s: float,
    ) -> None:
        if not self._locomotion_active:
            return
        self._locomotion_distance_px = max(0.0, cumulative_distance_px)
        if self.current_action == "walk_start" and cumulative_distance_px >= self._locomotion_profile.start_distance_px:
            self._enter_walking_loop()
        if self.current_action != "walking" or not self.current_frames:
            return
        phase = (self._locomotion_distance_px / max(1.0, self._locomotion_profile.cycle_distance_px)) % 1.0
        next_index = min(len(self.current_frames) - 1, int(phase * len(self.current_frames)))
        if next_index != self.frame_index:
            self.frame_index = next_index
            self._emit_frame(
                self.current_frames[self.frame_index],
                config=self._action_config("walking"),
            )
        elif self._last_emitted_frame is None and self.current_frames:
            self._emit_frame(self.current_frames[self.frame_index], config=self._action_config("walking"))

    def stop_locomotion(self, *, immediate: bool) -> None:
        if immediate:
            self._locomotion_active = False
            if self.current_action in {"walk_start", "walking", "walk_stop"}:
                self.play_idle()
            return
        if self.current_action in {"walk_start", "walking"}:
            self._locomotion_active = False
            self.play("walk_stop")
        else:
            self._locomotion_active = False

    def _enter_walking_loop(self) -> None:
        self.current_action = "walking"
        self.current_frames = self._frames_for_action("walking")
        self.frame_index = 0
        self.animation_timer.stop()
        if self.current_frames:
            self._emit_frame(self.current_frames[0], config=self._action_config("walking"))

    def _emit_frame(self, frame_name: str, *, config: dict[str, Any] | None = None) -> None:
        self._last_emitted_frame = frame_name
        if self.renderer and self.display_callback:
            if hasattr(self.renderer, "set_motion_context"):
                try:
                    binding = (config or {}).get("renderer_binding", {})
                    self.renderer.set_motion_context(self.current_action, binding if isinstance(binding, dict) else None)  # type: ignore[attr-defined]
                except Exception:
                    pass
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

    def set_state(self, state: str) -> None:
        if state in {"drag", "dragging", "drag_pickup", "drag_hold"}:
            self.set_dragging(True)
            return
        if state == "drag_drop":
            self.set_dragging(False)
            return
        if state in {"walking", "walk_start"}:
            self.start_locomotion()
            return
        if state == "walk_stop":
            self.stop_locomotion(immediate=False)
            return

        if self.state_manager.set_state(state):
            action = self.state_manager.state_to_action(self.state_manager.get_state())
            self.play(action)

    def set_dragging(self, dragging: bool) -> None:
        if dragging:
            self._drag_active = True
            self.state_manager.set_state("dragging")
            if self.current_action not in {"drag_pickup", "drag_hold"}:
                self.play("drag_pickup")
            return
        self._drag_active = False
        if self.current_action == "drag_hold":
            self.play("drag_drop")
        elif self.current_action not in {"drag_pickup", "drag_drop"}:
            self.play_idle()

    def set_hovered(self, hovered: bool) -> None:
        if hovered and self.current_state == "idle":
            self.play("idle")

    def set_walking(self, walking: bool) -> None:
        if walking:
            self.start_locomotion()
        else:
            self.stop_locomotion(immediate=False)

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
        self.set_state("reminding")

    def trigger_sleeping(self) -> None:
        self.set_state("sleeping")

    def refresh(self) -> None:
        self.reload_manifest()
        if self._drag_active and self.current_action in {"drag_pickup", "drag_hold"}:
            self.play("drag_hold")
            return
        if self._locomotion_active:
            self._enter_walking_loop()
            return
        state = self.state_manager.get_state()
        self.play(self.state_manager.state_to_action(state))

    def _action_config(self, action_name: str) -> dict[str, Any] | None:
        if hasattr(self.asset_manager, "action_config"):
            try:
                config = self.asset_manager.action_config(action_name)
                if isinstance(config, dict):
                    return config
            except Exception:
                pass
        return self.manifest.get_action_config(action_name)

    def _frames_for_action(self, action_name: str) -> list[str]:
        if action_name == "idle" and self._cached_idle_frames:
            return self._cached_idle_frames[:]
        try:
            if hasattr(self.asset_manager, "select_frames_for_state") and callable(self.asset_manager.select_frames_for_state):
                frames = self.asset_manager.select_frames_for_state(action_name)
                if isinstance(frames, list):
                    values = [str(frame) for frame in frames]
                    if values:
                        return values
        except Exception:
            pass
        return self.manifest.get_frames(action_name)
