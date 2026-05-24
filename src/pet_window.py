from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QCursor, QGuiApplication, QIcon, QMouseEvent, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QMenu, QSizePolicy, QVBoxLayout, QWidget

from .animation_manager import AnimationManager
from .asset_manager import AssetManager
from .typewriter import Typewriter


class ClickableLabel(QLabel):
    drag_started = Signal(QPoint)
    dragged = Signal(QPoint)
    drag_finished = Signal(QPoint)
    context_requested = Signal(QPoint)
    hover_changed = Signal(bool)

    def enterEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.hover_changed.emit(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self.hover_changed.emit(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_started.emit(event.globalPosition().toPoint())
        elif event.button() == Qt.MouseButton.RightButton:
            self.context_requested.emit(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.dragged.emit(event.globalPosition().toPoint())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_finished.emit(event.globalPosition().toPoint())
        super().mouseReleaseEvent(event)


class BubbleLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class PetWindow(QWidget):
    message_submitted = Signal(str)
    pet_clicked = Signal()
    position_changed = Signal(int, int)
    activity_detected = Signal()

    def __init__(self, asset_manager: AssetManager, app_config: dict[str, Any]) -> None:
        super().__init__()
        self.asset_manager = asset_manager
        self.app_config = app_config
        self.context_menu: QMenu | None = None
        self.drag_start_global: QPoint | None = None
        self.drag_start_window: QPoint | None = None
        self.drag_distance = 0
        self.always_on_top = bool(app_config.get("window", {}).get("always_on_top", True))
        self._last_render_debug: tuple[Any, ...] | None = None

        self._configure_window()
        self._build_ui()
        self.animation_manager = AnimationManager(self, self.asset_manager)
        self.typewriter = Typewriter(self.bubble, self.set_pet_state, app_config)
        self.bubble.clicked.connect(self.typewriter.click)
        self.set_pet_state(self.asset_manager.state_name("idle"))
        self.update_affinity("")

    def _configure_window(self) -> None:
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
        if self.always_on_top:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setWindowTitle("Daniya Summer Desktop Pet")
        icon_path = self.asset_manager.icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _build_ui(self) -> None:
        ui_config = self.app_config.get("ui", {})
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(6, 6, 6, 6)
        self.root_layout.setSpacing(4)

        self.bubble = BubbleLabel()
        self.bubble.setWordWrap(True)
        self.bubble.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.bubble.setMaximumWidth(int(ui_config.get("bubble_max_width", 300)))
        self.bubble.setStyleSheet(
            """
            QLabel {
                color: #43233a;
                background: rgba(255, 247, 252, 235);
                border: 1px solid rgba(235, 130, 180, 210);
                border-radius: 8px;
                padding: 7px 9px;
                font-size: 12px;
            }
            """
        )
        self.bubble.hide()

        bubble_row = QHBoxLayout()
        bubble_row.addStretch(1)
        bubble_row.addWidget(self.bubble)
        bubble_row.addStretch(1)
        self.root_layout.addLayout(bubble_row)

        self.image_label = ClickableLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.image_label.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        self.image_label.drag_started.connect(self._start_drag)
        self.image_label.dragged.connect(self._drag)
        self.image_label.drag_finished.connect(self._finish_drag)
        self.image_label.context_requested.connect(self._show_context_menu)
        self.image_label.hover_changed.connect(self._hover_changed)
        self.root_layout.addWidget(self.image_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.affinity_label = QLabel()
        self.affinity_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.affinity_label.setStyleSheet(
            """
            QLabel {
                color: #7a3a63;
                background: rgba(255, 255, 255, 130);
                border: 1px solid rgba(235, 130, 180, 95);
                border-radius: 7px;
                padding: 0 5px;
                font-size: 10px;
            }
            """
        )
        self.root_layout.addWidget(self.affinity_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.input_min_width = int(ui_config.get("input_min_width", 180))
        self.input_box = QLineEdit()
        self.input_box.setPlaceholderText("和达妮娅说点什么...")
        self.input_box.setMinimumWidth(self.input_min_width)
        self.input_box.setStyleSheet(
            """
            QLineEdit {
                color: #392033;
                background: rgba(255, 255, 255, 235);
                border: 1px solid rgba(235, 130, 180, 210);
                border-radius: 8px;
                padding: 6px 9px;
            }
            """
        )
        self.input_box.returnPressed.connect(self._submit_message)
        self.root_layout.addWidget(self.input_box, alignment=Qt.AlignmentFlag.AlignCenter)

        if not bool(self.app_config.get("window", {}).get("show_input", True)):
            self.input_box.setMinimumWidth(0)
            self.input_box.hide()

    def set_context_menu(self, menu: QMenu) -> None:
        self.context_menu = menu

    def show_at_config_position(self) -> None:
        window_config = self.app_config.get("window", {})
        self.move(int(window_config.get("start_x", 1000)), int(window_config.get("start_y", 500)))
        self.show()
        self.move(self._clamped_position(self.pos()))

    def set_pet_state(self, state: str) -> None:
        self.animation_manager.set_state(state)

    def render_pet_pixmap(self, path: Path, visual_scale: float = 1.0) -> None:
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            return

        target_height = self.asset_manager.target_height()
        logical_height = max(1, int(round(target_height * visual_scale)))
        dpr = self._current_device_pixel_ratio()
        physical_height = max(1, int(round(logical_height * dpr)))
        physical_width = max(1, int(round(pixmap.width() * physical_height / max(1, pixmap.height()))))
        scaled = pixmap.scaled(
            physical_width,
            physical_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(dpr)

        logical_width = max(1, int(round(scaled.width() / dpr)))
        logical_display_height = max(1, int(round(scaled.height() / dpr)))
        self.image_label.setPixmap(scaled)
        self.image_label.setFixedSize(logical_width, logical_display_height)
        self._print_render_debug(path, pixmap, target_height, dpr, scaled, logical_width, logical_display_height)
        self._resize_to_content()
        if self.isVisible():
            self.move(self._clamped_position(self.pos()))

    def speak(self, text: str) -> None:
        self.typewriter.speak(text)

    def show_message(self, text: str) -> None:
        self.bubble.setText(text)
        self.bubble.show()
        self._resize_to_content()
        self.move(self._clamped_position(self.pos()))

    def set_input_enabled(self, enabled: bool) -> None:
        self.input_box.setEnabled(enabled)
        if enabled and self.input_box.isVisible():
            self.input_box.setFocus()

    def toggle_input(self) -> None:
        should_show = not self.input_box.isVisible()
        self.input_box.setMinimumWidth(self.input_min_width if should_show else 0)
        self.input_box.setVisible(should_show)
        if should_show:
            self.input_box.setFocus()
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
        actual = self.asset_manager.set_target_height(height)
        self.animation_manager.refresh()
        self._resize_to_content()
        self.move(self._clamped_position(self.pos()))
        return actual

    def update_affinity(self, text: str) -> None:
        self.affinity_label.setText(text)
        self.affinity_label.setVisible(bool(text))

    def can_show_idle_message(self) -> bool:
        if self.typewriter.is_typing:
            return False
        if self.input_box.isVisible() and self.input_box.hasFocus() and self.input_box.text().strip():
            return False
        return True

    def _submit_message(self) -> None:
        text = self.input_box.text().strip()
        if not text:
            return
        self.input_box.clear()
        self.activity_detected.emit()
        self.message_submitted.emit(text)

    def _start_drag(self, global_pos: QPoint) -> None:
        self.activity_detected.emit()
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
        self.image_label.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        self.animation_manager.set_dragging(False)
        if self.drag_distance < 8:
            self.pet_clicked.emit()
        else:
            pos = self.pos()
            self.position_changed.emit(pos.x(), pos.y())
        self.drag_start_global = None
        self.drag_start_window = None
        self.drag_distance = 0

    def _hover_changed(self, hovered: bool) -> None:
        self.animation_manager.set_hovered(hovered)

    def _show_context_menu(self, global_pos: QPoint) -> None:
        self.activity_detected.emit()
        if self.context_menu is not None:
            self.context_menu.exec(global_pos)

    def _clamped_position(self, position: QPoint) -> QPoint:
        bounds = self._desktop_bounds()
        keep_visible = 56
        min_x = bounds.left() - max(0, self.width() - keep_visible)
        max_x = bounds.right() - keep_visible
        min_y = bounds.top() - max(0, self.height() - keep_visible)
        max_y = bounds.bottom() - keep_visible
        return QPoint(
            max(min_x, min(max_x, position.x())),
            max(min_y, min(max_y, position.y())),
        )

    def _desktop_bounds(self) -> QRect:
        screens = QGuiApplication.screens()
        if not screens:
            return QRect(0, 0, 1920, 1080)
        bounds = screens[0].availableGeometry()
        for screen in screens[1:]:
            bounds = bounds.united(screen.availableGeometry())
        return bounds

    def _resize_to_content(self) -> None:
        self.adjustSize()
        hint = self.sizeHint()
        if hint.isValid():
            self.resize(hint)

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
