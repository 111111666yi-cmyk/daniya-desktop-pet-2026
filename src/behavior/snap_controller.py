from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Any
from PySide6.QtCore import QObject, QPoint, QRect, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget

class SnapController(QObject):
    def __init__(self, window: QWidget, config: Any) -> None:
        super().__init__()
        self.window = window
        self.config = config
        self._anim: QPropertyAnimation | None = None

    def state_file_path(self) -> Path:
        from src.utils import runtime_root
        return runtime_root() / "data" / "window_state.json"

    def snap_and_save(self, global_pos: QPoint) -> None:
        if self._anim and self._anim.state() == QPropertyAnimation.State.Running:
            self._anim.stop()

        pos = self.window.pos()
        bounds = self.get_desktop_bounds()
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

        target_pos = QPoint(target_x, target_y)
        if target_pos != pos and self.config.drag_return_enabled:
            self.animate_to(target_pos)
        else:
            self.window.move(target_pos)
            self.save_window_state(target_pos.x(), target_pos.y(), snap_state)

    def animate_to(self, target_pos: QPoint) -> None:
        self._anim = QPropertyAnimation(self.window, b"pos")
        self._anim.setDuration(300)
        self._anim.setStartValue(self.window.pos())
        self._anim.setEndValue(target_pos)
        self._anim.setEasingCurve(QEasingCurve.Type.OutQuad)

        self._anim.finished.connect(lambda: self.save_window_state(self.window.x(), self.window.y(), self.get_current_snap_state()))
        self._anim.start()

    def get_current_snap_state(self) -> str:
        pos = self.window.pos()
        bounds = self.get_desktop_bounds()
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

    def save_window_state(self, x: int, y: int, snap: str) -> None:
        data = {
            "x": x,
            "y": y,
            "snap": snap,
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        path = self.state_file_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as exc:
            print(f"[SnapController] Failed to save window state: {exc}")

    def load_window_state(self) -> tuple[int, int] | None:
        path = self.state_file_path()
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "x" in data and "y" in data:
                bounds = self.get_desktop_bounds()
                x = int(data["x"])
                y = int(data["y"])
                w = self.window.width()
                h = self.window.height()

                visible_min = 32
                if (x + w < bounds.left() + visible_min or x > bounds.right() + 1 - visible_min or
                    y + h < bounds.top() + visible_min or y > bounds.bottom() + 1 - visible_min):
                    return None
                return x, y
        except Exception as exc:
            print(f"[SnapController] Failed to load window state: {exc}")
            try:
                path.unlink()
            except OSError:
                pass
        return None
