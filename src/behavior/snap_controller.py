from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from PySide6.QtCore import QObject, QPoint, QRect, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget
from src.atomic_io import atomic_write_json

class SnapController(QObject):
    def __init__(self, window: QWidget, config: Any) -> None:
        super().__init__()
        self.window = window
        self.config = config
        self._anim: QPropertyAnimation | None = None

    def state_file_path(self) -> Path:
        from src.utils import runtime_root
        return runtime_root() / "data" / "window_state.json"

    def snap_and_save(self, global_pos: QPoint, velocity: float = 0.0) -> None:
        if self._anim and self._anim.state() == QPropertyAnimation.State.Running:
            self._anim.stop()

        pos = self.window.pos()
        bounds = self.get_screen_bounds(pos)
        margin = self.config.snap_margin_px
        snap_to_edge = self.config.snap_to_edge_enabled
        keep_on_screen = self.config.keep_on_screen_enabled

        target_x = pos.x()
        target_y = pos.y()
        snap_state = "none"

        w = self.window.width()
        h = self.window.height()

        if snap_to_edge:
            if abs(pos.x() - bounds.left()) <= margin:
                target_x = bounds.left()
                snap_state = "left"
            elif abs((pos.x() + w) - (bounds.right() + 1)) <= margin:
                target_x = bounds.right() + 1 - w
                snap_state = "right"

            if abs((pos.y() + h) - (bounds.bottom() + 1)) <= margin:
                target_y = bounds.bottom() + 1 - h
                if snap_state == "none":
                    snap_state = "bottom"
                else:
                    snap_state += "_bottom"

        if keep_on_screen:
            visible_min = 32
            min_x = bounds.left() - w + visible_min
            max_x = bounds.right() + 1 - visible_min
            min_y = bounds.top() - h + visible_min
            max_y = bounds.bottom() + 1 - visible_min

            target_x = max(min_x, min(max_x, target_x))
            target_y = max(min_y, min(max_y, target_y))

        pet_config = getattr(self.window, "app_config", {}).get("pet", {})
        edge_peek_allowed = getattr(self.window, "edge_peek_allowed_callback", None)
        can_edge_peek = not callable(edge_peek_allowed) or bool(edge_peek_allowed())
        if bool(pet_config.get("edge_peek_enabled", False)) and can_edge_peek:
            edge_side = None
            if snap_state.startswith("left"):
                edge_side = "left"
            elif snap_state.startswith("right"):
                edge_side = "right"
            docked_position = getattr(self.window, "_docked_position", None)
            if edge_side and callable(docked_position):
                docked = docked_position(edge_side)
                target_x = docked.x()
                target_y = docked.y()
                self.window.dock_side = edge_side
        elif hasattr(self.window, "dock_side"):
            self.window.dock_side = None

        target_pos = QPoint(target_x, target_y)
        if target_pos != pos and self.config.drag_return_enabled:
            self.animate_to(target_pos, velocity=velocity)
        else:
            self.window.move(target_pos)
            self.save_window_state(target_pos.x(), target_pos.y(), snap_state)

    def animate_to(self, target_pos: QPoint, velocity: float = 0.0) -> None:
        self._anim = QPropertyAnimation(self.window, b"pos")
        speed = max(0.0, min(float(velocity), 3000.0))
        self._anim.setDuration(max(140, min(300, int(300 - speed / 20))))
        self._anim.setStartValue(self.window.pos())
        self._anim.setEndValue(target_pos)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuad)

        self._anim.finished.connect(lambda: self.save_window_state(self.window.x(), self.window.y(), self.get_current_snap_state()))
        self._anim.start()

    def get_current_snap_state(self) -> str:
        pos = self.window.pos()
        dock_side = getattr(self.window, "dock_side", None)
        if dock_side in {"left", "right"}:
            return dock_side
        bounds = self.get_screen_bounds(pos)
        w = self.window.width()
        h = self.window.height()

        left = pos.x() == bounds.left()
        right = pos.x() + w == bounds.right() + 1
        bottom = pos.y() + h == bounds.bottom() + 1

        if left and bottom: return "left_bottom"
        if right and bottom: return "right_bottom"
        if left: return "left"
        if right: return "right"
        if bottom: return "bottom"
        return "none"

    def get_desktop_bounds(self) -> QRect:
        screens = QGuiApplication.screens()
        if not screens:
            return QRect(0, 0, 1920, 1080)
        bounds = screens[0].availableGeometry()
        for screen in screens[1:]:
            bounds = bounds.united(screen.availableGeometry())
        return bounds

    def get_screen_bounds(self, position: QPoint | None = None) -> QRect:
        resolver = getattr(self.window, "_screen_bounds_for_position", None)
        if callable(resolver):
            return QRect(resolver(position or self.window.pos()))
        return self.get_desktop_bounds()

    def save_window_state(self, x: int, y: int, snap: str, behavior_state: str | None = None) -> None:
        data = {
            "x": x,
            "y": y,
            "snap": snap,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        if behavior_state:
            data["last_behavior"] = behavior_state
        path = self.state_file_path()
        if not atomic_write_json(path, data):
            print("[SnapController] Failed to save window state.")

    def load_window_state(self) -> tuple[int, int] | None:
        path = self.state_file_path()
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "x" in data and "y" in data:
                x = int(data["x"])
                y = int(data["y"])
                repair = getattr(self.window, "_safe_start_position", None)
                if callable(repair):
                    safe = repair(QPoint(x, y))
                    return safe.x(), safe.y()
                bounds = self.get_desktop_bounds()
                width = max(1, int(self.window.width()))
                height = max(1, int(self.window.height()))
                visible_min = 32
                if (
                    x + width < bounds.left() + visible_min
                    or x > bounds.right() + 1 - visible_min
                    or y + height < bounds.top() + visible_min
                    or y > bounds.bottom() + 1 - visible_min
                ):
                    return None
                return x, y
        except Exception as exc:
            print(f"[SnapController] Failed to load window state: {exc}")
            try:
                path.unlink()
            except OSError:
                pass
        return None
