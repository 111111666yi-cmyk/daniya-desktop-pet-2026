from __future__ import annotations
from typing import Any, Callable
from PySide6.QtCore import QObject, QPoint, Signal
from PySide6.QtWidgets import QWidget
from .behavior_config import BehaviorConfig
from .interaction_detector import InteractionDetector
from .drag_controller import DragController
from .snap_controller import SnapController
from .idle_behavior import IdleBehavior

class PetBehaviorEngine(QObject):
    action_requested = Signal(str)
    line_requested = Signal(str)

    def __init__(
        self,
        window: QWidget,
        app_config: dict[str, Any],
        is_allowed_callback: Callable[[], bool],
        is_night_callback: Callable[[], bool],
        speak_callback: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__()
        self.window = window
        self.app_config = app_config
        self.speak_callback = speak_callback

        self.config = BehaviorConfig(app_config)

        self.drag_controller = DragController(window, self._handle_drag_state_change)
        self.snap_controller = SnapController(window, self.config)

        self.detector = InteractionDetector(
            long_press_ms=self.config.long_press_ms,
            on_single_click=self._handle_single_click,
            on_double_click=self._handle_double_click,
            on_long_press=self._handle_long_press,
            on_drag_start=self._handle_drag_start,
            on_drag=self._handle_drag,
            on_drag_finish=self._handle_drag_finish
        )

        self.idle_behavior = IdleBehavior(
            config=self.config,
            is_allowed=is_allowed_callback,
            is_night=is_night_callback
        )
        self.idle_behavior.idle_action_triggered.connect(self._handle_idle_action)
        self.idle_behavior.idle_bubble_triggered.connect(self._handle_idle_bubble)

    def reload_config(self, app_config: dict[str, Any]) -> None:
        self.app_config = app_config
        self.config = BehaviorConfig(app_config)
        self.drag_controller.on_state_changed = self._handle_drag_state_change
        self.snap_controller.config = self.config
        self.detector.long_press_ms = self.config.long_press_ms
        self.idle_behavior.set_config(self.config)

    def mark_activity(self) -> None:
        self.idle_behavior.mark_activity()

    def _handle_drag_state_change(self, state: str) -> None:
        self.action_requested.emit(state)

    def _handle_single_click(self) -> None:
        self.mark_activity()
        if not self.config.behavior_enabled:
            return
        self.action_requested.emit("clicked")
        self.window.pet_clicked.emit()

    def _handle_double_click(self) -> None:
        self.mark_activity()
        if not self.config.behavior_enabled or not self.config.double_click_enabled:
            return
        self.action_requested.emit("happy")
        if self.speak_callback:
            self.speak_callback("……讨厌。别乱点。")
        else:
            getattr(self.window, "speak", lambda s: None)("……讨厌。别乱点。")

    def _handle_long_press(self) -> None:
        self.mark_activity()
        pass

    def _handle_drag_start(self, global_pos: QPoint) -> None:
        self.mark_activity()
        if not self.config.behavior_enabled:
            return
        act_det = getattr(self.window, "activity_detected", None)
        if act_det is not None:
            if hasattr(act_det, "emit"):
                act_det.emit()
            elif callable(act_det):
                act_det()

        cancel_walk = getattr(self.window, "_cancel_walk_move", None)
        if callable(cancel_walk):
            cancel_walk()
        self.window.dock_side = None
        self.window.drag_start_global = global_pos

        anim_mgr = getattr(self.window, "animation_manager", None)
        if anim_mgr:
            anim_mgr.set_dragging(True)

        avatar_lbl = getattr(self.window, "image_label", None)
        if avatar_lbl:
            from PySide6.QtGui import QCursor
            from PySide6.QtCore import Qt
            avatar_lbl.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))

        self.drag_controller.start_drag(global_pos)

    def _handle_drag(self, global_pos: QPoint) -> None:
        if not self.config.behavior_enabled:
            return
        self.drag_controller.drag(global_pos)

    def _handle_drag_finish(self, global_pos: QPoint) -> None:
        self.mark_activity()
        if not self.config.behavior_enabled:
            return

        self.window.drag_start_global = None

        avatar_lbl = getattr(self.window, "image_label", None)
        if avatar_lbl:
            from PySide6.QtGui import QCursor
            from PySide6.QtCore import Qt
            avatar_lbl.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))

        anim_mgr = getattr(self.window, "animation_manager", None)
        if anim_mgr:
            anim_mgr.set_dragging(False)

        final_pos, velocity = self.drag_controller.finish_drag(global_pos)
        self.snap_controller.snap_and_save(global_pos, velocity=velocity)
        self.action_requested.emit("idle")

        pos = self.window.pos()
        self.window.position_changed.emit(pos.x(), pos.y())
        self.window.drag_completed.emit(pos.x(), pos.y())

    def _handle_idle_action(self, action_name: str) -> None:
        if not self.config.behavior_enabled:
            return
        self.action_requested.emit(action_name)

    def _handle_idle_bubble(self, text: str) -> None:
        if not self.config.behavior_enabled:
            return
        if self.speak_callback:
            self.speak_callback(text)
        else:
            getattr(self.window, "speak", lambda s: None)(text)
