from __future__ import annotations

import ctypes
import math
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QMenu, QSizePolicy, QSystemTrayIcon, QVBoxLayout, QWidget

from .animation_manager import AnimationManager
from .asset_manager import AssetManager
from .typewriter import Typewriter

from .ui import ModernBubble, PetAvatar, StatusBadge, InputBar


class WinPoint(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class PetWindow(QWidget):
    message_submitted = Signal(str)
    pet_clicked = Signal()
    position_changed = Signal(int, int)
    drag_completed = Signal(int, int)
    activity_detected = Signal()

    def __init__(self, asset_manager: AssetManager, app_config: dict[str, Any]) -> None:
        super().__init__()
        self.asset_manager = asset_manager
        self.app_config = app_config
        self.context_menu: QMenu | None = None
        self.drag_start_global: QPoint | None = None
        self.drag_start_window: QPoint | None = None
        self.drag_distance = 0
        self._last_left_button_down = False
        self._walk_target: QPoint | None = None
        self._walk_step = 0
        self.dock_side: str | None = None
        self.edge_peek_allowed_callback = lambda: True
        self.always_on_top = bool(app_config.get("window", {}).get("always_on_top", True))
        self._last_render_debug: tuple[Any, ...] | None = None
        self._tray_icon: QSystemTrayIcon | None = None
        self._minimized_to_tray = False
        self._scaled_pixmap_cache: dict[tuple[str, int, float], tuple[QPixmap, int, int]] = {}

        self._setup_tray()
        self._configure_window()
        self._build_ui()
        self.animation_manager = AnimationManager(self, self.asset_manager)
        self.animation_manager.set_pixmap_callback(lambda p: self.render_pet_pixmap(Path(p)))
        self.typewriter = Typewriter(self.bubble, self.set_pet_state, app_config)
        self.bubble.clicked.connect(self.typewriter.click)
        self.set_pet_state(self.asset_manager.state_name("idle"))
        self.update_affinity("")
        self._start_pet_feature_timers()
        print("[Daniya] PetWindow created")

    def _configure_window(self) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        try:
            opacity = int(self.app_config.get("window", {}).get("opacity_percent", 100)) / 100
        except (TypeError, ValueError):
            opacity = 1.0
        self.setWindowOpacity(max(0.3, min(1.0, opacity)))
        self.setWindowTitle("Daniya Summer Desktop Pet")
        icon_path = self.asset_manager.icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _build_ui(self) -> None:
        ui_config = self.app_config.get("ui", {})
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(6, 6, 6, 6)
        self.root_layout.setSpacing(4)

        self.bubble = ModernBubble(max_width=int(ui_config.get("bubble_max_width", 300)))

        bubble_row = QHBoxLayout()
        bubble_row.addStretch(1)
        bubble_row.addWidget(self.bubble)
        bubble_row.addStretch(1)
        self.root_layout.addLayout(bubble_row)

        self.image_label = PetAvatar()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.image_label.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        # Behavior Engine Integration
        from .behavior.behavior_engine import PetBehaviorEngine
        self.behavior_engine = PetBehaviorEngine(
            window=self,
            app_config=self.app_config,
            is_allowed_callback=lambda: True, # Injected by app.py later
            is_night_callback=lambda: False,   # Injected by app.py later
            speak_callback=self.speak
        )
        self.behavior_engine.action_requested.connect(self._handle_behavior_action)

        self.image_label.drag_started.connect(self.behavior_engine.detector.handle_press)
        self.image_label.dragged.connect(self.behavior_engine.detector.handle_move)
        self.image_label.drag_finished.connect(self.behavior_engine.detector.handle_release)
        self.image_label.context_requested.connect(self._show_context_menu)
        self.image_label.hover_changed.connect(self._hover_changed)

        self.affinity_label = StatusBadge()

        self.input_min_width = int(ui_config.get("input_min_width", 180))
        self.input_box = InputBar(min_width=self.input_min_width)
        self.input_box.submitted.connect(self._submit_message)

        # 整体包裹：将宠物立绘置于左侧，控制栏置于右侧
        pet_row = QHBoxLayout()
        # 使用负间距，拉近图标和达妮娅的距离，使其重叠进图片的透明边缘中
        pet_row.setSpacing(-12)
        pet_row.setContentsMargins(0, 0, 0, 0)

        pet_row.addWidget(self.image_label, alignment=Qt.AlignmentFlag.AlignBottom)

        # 右下角控件列
        controls_layout = QVBoxLayout()
        controls_layout.setSpacing(4)
        controls_layout.addStretch(1)  # 压到最下方
        controls_layout.addWidget(self.affinity_label, alignment=Qt.AlignmentFlag.AlignLeft)
        controls_layout.addWidget(self.input_box, alignment=Qt.AlignmentFlag.AlignLeft)

        pet_row.addLayout(controls_layout)
        pet_row.addStretch(1)  # 右侧拉伸，确保整体左对齐

        self.root_layout.addLayout(pet_row)

        if not bool(self.app_config.get("window", {}).get("show_input", True)):
            self.set_input_visible(False, expand=False)
        else:
            self.set_input_visible(True, expand=True)

    def set_context_menu(self, menu: QMenu) -> None:
        self.context_menu = menu

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._stop_pet_feature_timers()
        self._cancel_walk_move()
        # Save position state on close
        self.behavior_engine.snap_controller.save_window_state(
            self.x(),
            self.y(),
            self.behavior_engine.snap_controller.get_current_snap_state()
        )
        if self._tray_icon is not None:
            self._tray_icon.hide()
        super().closeEvent(event)

    def _handle_behavior_action(self, action: str) -> None:
        if action == "clicked":
            self.animation_manager.trigger_clicked()
        elif action == "happy":
            self.animation_manager.trigger_happy()
        elif action == "drag":
            self.set_pet_state("dragging")
        elif action == "sleep":
            self.animation_manager.trigger_sleeping()
        elif action == "idle":
            self.set_pet_state("idle")

    def _setup_tray(self) -> None:
        icon_path = self.asset_manager.icon_path()
        if not icon_path.exists():
            return
        self._tray_icon = QSystemTrayIcon(QIcon(str(icon_path)), self)
        self._tray_icon.setToolTip("Daniya Summer Desktop Pet")
        self._tray_icon.activated.connect(self._on_tray_activated)
        self._tray_icon.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.restore_from_tray()

    def minimize_to_tray(self) -> None:
        self._minimized_to_tray = True
        self.hide()
        self._refresh_context_menu()

    def restore_from_tray(self) -> None:
        self._minimized_to_tray = False
        self.show()
        self.raise_()
        self.activateWindow()
        self._refresh_context_menu()

    def is_minimized_to_tray(self) -> bool:
        return self._minimized_to_tray

    def set_menu_refresh_callback(self, callback: Callable[[], None]) -> None:
        self._menu_refresh_callback = callback

    def _refresh_context_menu(self) -> None:
        if hasattr(self, "_menu_refresh_callback") and self._menu_refresh_callback:
            self._menu_refresh_callback()

    def show_at_config_position(self) -> None:
        saved_pos = self.behavior_engine.snap_controller.load_window_state()
        if saved_pos is not None:
            requested = QPoint(saved_pos[0], saved_pos[1])
        else:
            window_config = self.app_config.get("window", {})
            requested = QPoint(
                _safe_int(window_config.get("start_x"), 1000),
                _safe_int(window_config.get("start_y"), 500),
            )
        self.move(requested)
        self.show()
        self._resize_to_content()
        final_pos = self._safe_start_position(requested)
        self.move(final_pos)

        # Save loaded/fallback position
        self.behavior_engine.snap_controller.save_window_state(
            final_pos.x(),
            final_pos.y(),
            self.behavior_engine.snap_controller.get_current_snap_state()
        )

        print(
            "[Daniya] window geometry "
            f"requested=({requested.x()},{requested.y()}) "
            f"final=({self.x()},{self.y()},{self.width()}x{self.height()}) "
            f"visible={self.isVisible()}"
        )

    def set_pet_state(self, state: str) -> None:
        self.animation_manager.set_state(state)

    def clear_render_cache(self) -> None:
        self._scaled_pixmap_cache.clear()

    def _get_scaled_pixmap(self, path: Path, logical_height: int, dpr: float) -> tuple[QPixmap, int, int]:
        key = (str(path), logical_height, round(dpr, 2))
        cached = self._scaled_pixmap_cache.get(key)
        if cached is not None and not cached[0].isNull():
            return cached
        original = QPixmap(str(path))
        if original.isNull():
            return original, 0, 0
        physical_height = max(1, int(round(logical_height * dpr)))
        physical_width = max(
            1,
            int(round(original.width() * physical_height / max(1, original.height())))
        )
        scaled = original.scaled(
            physical_width,
            physical_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(dpr)
        val = (scaled, original.width(), original.height())
        self._scaled_pixmap_cache[key] = val
        if len(self._scaled_pixmap_cache) > 128:
            self._scaled_pixmap_cache.pop(next(iter(self._scaled_pixmap_cache)))
        return val

    def render_pet_pixmap(self, path: Path, visual_scale: float = 1.0) -> None:
        dpr = self._current_device_pixel_ratio()
        base_height = self.asset_manager.target_height()
        logical_height = max(1, int(round(base_height * max(0.1, visual_scale))))

        scaled, orig_w, orig_h = self._get_scaled_pixmap(path, logical_height, dpr)
        if scaled.isNull():
            return

        logical_width = max(1, int(round(scaled.width() / dpr)))
        logical_display_height = max(1, int(round(scaled.height() / dpr)))

        # FIX: Force a STRICT, square container size based on target_height to completely prevent layout jumping!
        # The QPixmap will be automatically centered inside it by QLabel.
        container_size = int(max(logical_height, logical_width))
        self.image_label.setFixedSize(container_size, container_size)
        self.image_label.setPixmap(scaled)

        class MockOriginal:
            def __init__(self, w: int, h: int) -> None:
                self._w = w
                self._h = h
            def width(self) -> int: return self._w
            def height(self) -> int: return self._h

        self._print_render_debug(path, MockOriginal(orig_w, orig_h), base_height, dpr, scaled, logical_width, logical_display_height)
        # Remove resize_to_content() to prevent micro-jumping
        if self.isVisible():
            self.move(self._clamped_position(self.pos()))

    def speak(self, text: str) -> None:
        self.typewriter.speak(text)

    def show_message(self, text: str) -> None:
        self.bubble.show_message(text)
        self._resize_to_content()
        self.move(self._clamped_position(self.pos()))

    def set_thinking_state(self, is_thinking: bool) -> None:
        """[MODERN UI] Sets a visual thinking state (e.g. while waiting for LLM)"""
        self.bubble.set_thinking_state(is_thinking)
        self._resize_to_content()

    def set_input_enabled(self, enabled: bool) -> None:
        self.input_box.setEnabled(enabled)
        if enabled and self.input_box.isVisible():
            self.input_box.setFocus()

    def toggle_input(self) -> None:
        if not self.input_box.isVisible():
            self.set_input_visible(True, expand=True)
        else:
            self.set_input_visible(False)
        self._resize_to_content()
        self.move(self._clamped_position(self.pos()))

    def set_input_visible(self, visible: bool, expand: bool = True) -> None:
        if visible:
            self.input_box.always_expanded = True
            self.input_box.show()
            if expand:
                self.input_box.expand_input()
            else:
                self.input_box.collapse_input()
        else:
            self.input_box.always_expanded = False
            self.input_box.collapse_input()
            self.input_box.hide()
        self._resize_to_content()
        self.move(self._clamped_position(self.pos()))

    def set_always_on_top(self, enabled: bool) -> None:
        self.always_on_top = enabled
        flags = self.windowFlags()
        if enabled:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.show()

    def set_pet_height(self, height: int) -> int:
        self.clear_render_cache()
        actual = self.asset_manager.set_target_height(height)
        self.animation_manager.refresh()
        self._resize_to_content()
        self.move(self._clamped_position(self.pos()))
        return actual

    def update_affinity(self, text: str) -> None:
        self.affinity_label.update_badge(text)

    def can_show_idle_message(self) -> bool:
        if self.typewriter.is_typing:
            return False
        if self.input_box.isVisible() and self.input_box.hasFocus() and self.input_box.text().strip():
            return False
        return True

    def _submit_message(self, text: str) -> None:
        self.activity_detected.emit()
        self.message_submitted.emit(text)

    def _start_drag(self, global_pos: QPoint) -> None:
        if self.input_box.line_edit.isVisible():
            self.input_box.collapse_input()

        self.activity_detected.emit()
        self._cancel_walk_move()
        self.dock_side = None
        self.animation_manager.set_dragging(True)
        self.image_label.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
        self.drag_start_global = global_pos
        self.drag_start_window = self.pos()
        self.drag_distance = 0

    def _drag(self, global_pos: QPoint) -> None:
        if self.drag_start_global is None or self.drag_start_window is None:
            return
        delta = global_pos - self.drag_start_global
        self.drag_distance = max(self.drag_distance, abs(delta.x()) + abs(delta.y()))
        self.move(self._clamped_position(self.drag_start_window + delta))

    def _finish_drag(self, global_pos: QPoint) -> None:
        try:
            self.image_label.releaseMouse()
        except Exception:
            pass
        self.image_label.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        self.animation_manager.set_dragging(False)
        if self.drag_distance < 8:
            self.pet_clicked.emit()
        else:
            self._dock_if_near_edge()
            pos = self.pos()
            self.position_changed.emit(pos.x(), pos.y())
            self.drag_completed.emit(pos.x(), pos.y())
        self.drag_start_global = None
        self.drag_start_window = None
        self.drag_distance = 0

    def _hover_changed(self, hovered: bool) -> None:
        self.animation_manager.set_hovered(hovered)

    def _start_pet_feature_timers(self) -> None:
        self.edge_timer = QTimer(self)
        self.edge_timer.timeout.connect(self._tick_edge_peek)
        self.edge_timer.start(500)

        self.global_click_timer = QTimer(self)
        self.global_click_timer.timeout.connect(self._tick_global_click)
        self.global_click_timer.start(80)

        self.walk_move_timer = QTimer(self)
        self.walk_move_timer.timeout.connect(self._tick_walk_move)
        self.walk_move_timer.start(80)

    def _stop_pet_feature_timers(self) -> None:
        for name in ("edge_timer", "global_click_timer", "walk_move_timer"):
            timer = getattr(self, name, None)
            if timer is not None:
                timer.stop()

    def _tick_edge_peek(self) -> None:
        pet_config = self.app_config.get("pet", {})
        if not self.edge_peek_allowed_callback():
            self.dock_side = None
            return
        if not bool(pet_config.get("edge_peek_enabled", False)):
            self.dock_side = None
            return

        # Prevent snapping if dragging, mouse is pressed down on pet, context menu is open, or a snapping animation is running
        is_user_interacting = (
            self.drag_start_global is not None
            or (hasattr(self, "behavior_engine") and (
                self.behavior_engine.detector.is_dragging
                or getattr(self.behavior_engine.detector, "is_pressed", False)
                or (self.behavior_engine.snap_controller._anim is not None and
                    self.behavior_engine.snap_controller._anim.state() == self.behavior_engine.snap_controller._anim.State.Running)
            ))
            or (self.context_menu is not None and self.context_menu.isVisible())
        )
        if is_user_interacting:
            return

        if self.dock_side is None:
            self.dock_side = self._nearest_edge_side(8)
        if self.dock_side is None:
            return
        self.move(self._docked_position(self.dock_side, self._dock_visible_px_for_cursor()))
        if self.dock_side in {"left", "right"}:
            self.animation_manager.set_edge_peek(self.dock_side)

    def _tick_global_click(self) -> None:
        pet_config = self.app_config.get("pet", {})
        if not bool(pet_config.get("click_to_call_enabled", False)):
            self._last_left_button_down = False
            return
        key_state = ctypes.windll.user32.GetAsyncKeyState(0x01)
        left_down = bool(key_state & 0x8000)
        left_pressed = bool(key_state & 0x0001) or (left_down and not self._last_left_button_down)
        if left_pressed:
            cursor = QCursor.pos()
            if self._should_call_to(cursor):
                self.move_near(cursor)
        self._last_left_button_down = left_down

    def _should_call_to(self, point: QPoint) -> bool:
        if self.geometry().contains(point):
            return False
        if self._walk_target is not None:
            return True
        return self._is_desktop_point(point)

    def _is_desktop_point(self, point: QPoint) -> bool:
        user32 = ctypes.windll.user32
        user32.WindowFromPoint.argtypes = [WinPoint]
        user32.WindowFromPoint.restype = ctypes.c_void_p
        user32.GetParent.argtypes = [ctypes.c_void_p]
        user32.GetParent.restype = ctypes.c_void_p
        user32.GetAncestor.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        user32.GetAncestor.restype = ctypes.c_void_p
        user32.GetShellWindow.restype = ctypes.c_void_p

        hwnd = user32.WindowFromPoint(WinPoint(point.x(), point.y()))
        if not hwnd:
            return False

        desktop_roots = {"Progman", "WorkerW"}
        desktop_children = {"SHELLDLL_DefView", "SysListView32"}

        def class_name(handle: int) -> str:
            name = ctypes.create_unicode_buffer(256)
            user32.GetClassNameW(ctypes.c_void_p(handle), name, 256)
            return name.value

        shell_window = user32.GetShellWindow()
        root = user32.GetAncestor(ctypes.c_void_p(hwnd), 2)
        if root and (root == shell_window or class_name(root) in desktop_roots):
            return True

        seen_classes: list[str] = []
        current = hwnd
        for _ in range(12):
            if not current:
                break
            current_class = class_name(current)
            seen_classes.append(current_class)
            if current_class in desktop_roots:
                return True
            parent = user32.GetParent(ctypes.c_void_p(current))
            if not parent or parent == current:
                break
            current = parent
        return any(name in desktop_children for name in seen_classes)

    def move_near(self, global_pos: QPoint) -> None:
        was_walking = self._walk_target is not None
        self._cancel_walk_move()
        self.dock_side = None
        self.animation_manager.set_walking(True)
        target = QPoint(global_pos.x() - self.width() // 2, global_pos.y() - self.height() + 12)
        self._walk_target = self._clamped_position(target)
        if not was_walking:
            self._walk_step = 0

    def _cancel_walk_move(self) -> None:
        if self._walk_target is not None:
            self._walk_target = None
            self._walk_step = 0
            self.animation_manager.set_walking(False)

    def _finish_walk_move(self) -> None:
        self._walk_target = None
        self._walk_step = 0
        self.animation_manager.set_walking(False)
        self.position_changed.emit(self.x(), self.y())

    def _movement_duration_ms(self, start: QPoint, end: QPoint) -> int:
        distance = ((end.x() - start.x()) ** 2 + (end.y() - start.y()) ** 2) ** 0.5
        speed_px_per_second = 110.0
        return max(1800, min(16000, int(distance / speed_px_per_second * 1000)))

    def _tick_walk_move(self) -> None:
        if self._walk_target is None:
            return
        current = self.pos()
        dx = self._walk_target.x() - current.x()
        dy = self._walk_target.y() - current.y()
        distance = math.hypot(dx, dy)
        if distance <= 4:
            self.move(self._walk_target)
            self._finish_walk_move()
            return

        step = min(4.0, distance)
        nx = current.x() + int(round(dx / distance * step))
        ny = current.y() + int(round(dy / distance * step))
        self._walk_step += 1
        bob = int(round(math.sin(self._walk_step * math.pi / 4) * 1))
        self.move(self._clamped_position(QPoint(nx, ny + bob)))

    def _dock_if_near_edge(self) -> None:
        pet_config = self.app_config.get("pet", {})
        if not self.edge_peek_allowed_callback():
            self.dock_side = None
            return
        if not bool(pet_config.get("edge_peek_enabled", False)):
            self.dock_side = None
            return
        self.dock_side = self._nearest_edge_side(56)
        if self.dock_side is not None:
            self.move(self._docked_position(self.dock_side, self._dock_visible_px_for_cursor()))
            if self.dock_side in {"left", "right"}:
                self.animation_manager.set_edge_peek(self.dock_side)

    def _nearest_edge_side(self, threshold: int) -> str | None:
        bounds = self._desktop_bounds()
        right_edge = bounds.right() + 1
        bottom_edge = bounds.bottom() + 1
        distances = {
            "left": abs(self.x() - bounds.left()),
            "right": abs(right_edge - (self.x() + self.width())),
            "top": abs(self.y() - bounds.top()),
            "bottom": abs(bottom_edge - (self.y() + self.height())),
        }
        side, distance = min(distances.items(), key=lambda item: item[1])
        return side if distance <= threshold else None

    def _dock_visible_px_for_cursor(self) -> int:
        pet_config = self.app_config.get("pet", {})
        try:
            normal_visible = int(pet_config.get("edge_dock_visible_px", 56))
        except (TypeError, ValueError):
            normal_visible = 56
        try:
            hover_visible = int(pet_config.get("edge_dock_hover_visible_px", 82))
        except (TypeError, ValueError):
            hover_visible = 82
        cursor = QCursor.pos()
        bounds = self._desktop_bounds()
        near_edge = (
            cursor.x() <= bounds.left() + 84
            or cursor.x() >= bounds.right() - 84
            or cursor.y() <= bounds.top() + 84
            or cursor.y() >= bounds.bottom() - 84
        )
        return max(normal_visible, hover_visible) if near_edge else normal_visible

    def _docked_position(self, side: str, visible: int | None = None) -> QPoint:
        bounds = self._desktop_bounds()
        if visible is None:
            visible = self._dock_visible_px_for_cursor()
        current = self.pos()
        width = max(1, self.width())
        height = max(1, self.height())
        max_x = max(bounds.left(), bounds.right() - width + 1)
        max_y = max(bounds.top(), bounds.bottom() - height + 1)
        current_x = max(bounds.left(), min(max_x, current.x()))
        current_y = max(bounds.top(), min(max_y, current.y()))
        if side == "left":
            return QPoint(bounds.left() - width + visible, current_y)
        if side == "right":
            return QPoint(bounds.right() + 1 - visible, current_y)
        if side == "top":
            return QPoint(current_x, bounds.top())
        if side == "bottom":
            return QPoint(current_x, max_y)
        return self._clamped_position(current)

    def _show_context_menu(self, global_pos: QPoint) -> None:
        self.activity_detected.emit()
        if self.context_menu is not None:
            self.context_menu.exec(global_pos)

    def _clamped_position(self, position: QPoint) -> QPoint:
        bounds = self._desktop_bounds()
        width = max(1, self.width())
        height = max(1, self.height())
        min_x = bounds.left()
        max_x = max(min_x, bounds.right() - width + 1)
        min_y = bounds.top()
        max_y = max(min_y, bounds.bottom() - height + 1)
        return QPoint(
            max(min_x, min(max_x, position.x())),
            max(min_y, min(max_y, position.y())),
        )

    def _safe_start_position(self, requested: QPoint) -> QPoint:
        clamped = self._clamped_position(requested)
        if self._is_mostly_visible(clamped):
            return clamped
        return self._default_right_position()

    def _default_right_position(self) -> QPoint:
        bounds = self._desktop_bounds()
        margin = 48
        x = bounds.right() - self.width() - margin
        y = bounds.center().y() - self.height() // 2
        return self._clamped_position(QPoint(x, y))

    def _is_mostly_visible(self, position: QPoint) -> bool:
        bounds = self._desktop_bounds()
        width = max(1, self.width())
        height = max(1, self.height())
        rect = QRect(position, self.size())
        visible = rect.intersected(bounds)
        if visible.isNull():
            return False
        visible_area = visible.width() * visible.height()
        total_area = width * height
        return visible_area >= int(total_area * 0.85)

    def _desktop_bounds(self) -> QRect:
        screens = QGuiApplication.screens()
        if not screens:
            return QRect(0, 0, 1920, 1080)
        bounds = screens[0].availableGeometry()
        for screen in screens[1:]:
            bounds = bounds.united(screen.availableGeometry())
        return bounds

    def _resize_to_content(self) -> None:
        # FIX 错位：记录宠物立绘在屏幕上的绝对全局坐标
        old_avatar_pos = self.image_label.mapToGlobal(QPoint(0, 0)) if hasattr(self, "image_label") else None

        self.adjustSize()
        hint = self.sizeHint()
        if hint.isValid():
            self.resize(hint)

        # FIX 错位：在调整窗口大小后，微调窗口位置，确保宠物在屏幕上的绝对位置保持不变
        if old_avatar_pos is not None:
            new_avatar_pos = self.image_label.mapToGlobal(QPoint(0, 0))
            delta = old_avatar_pos - new_avatar_pos
            self.move(self.pos() + delta)

    def _current_device_pixel_ratio(self) -> float:
        screen = self.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return 1.0
        dpr = float(screen.devicePixelRatio())
        return max(1.0, dpr)

    def _print_render_debug(
        self,
        path: Path,
        original: QPixmap,
        target_height: int,
        dpr: float,
        rendered: QPixmap,
        label_width: int,
        label_height: int,
    ) -> None:
        key = (
            str(path),
            original.width(),
            original.height(),
            target_height,
            round(dpr, 2),
            rendered.width(),
            rendered.height(),
            label_width,
            label_height,
        )
        if key == self._last_render_debug:
            return
        self._last_render_debug = key
        print(
            "[Daniya] render "
            f"asset={path.name} original={original.width()}x{original.height()} "
            f"pet_height={target_height} dpr={dpr:.2f} "
            f"pixmap={rendered.width()}x{rendered.height()} "
            f"label={label_width}x{label_height}"
        )

    def contextMenuEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._show_context_menu(event.globalPos())

    def icon_path(self) -> Path:
        return self.asset_manager.icon_path()


def _safe_int(value: object, fallback: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return fallback
