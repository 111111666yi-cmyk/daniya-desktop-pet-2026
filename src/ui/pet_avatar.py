from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QLabel

class PetAvatar(QLabel):
    drag_started = Signal(QPoint)
    dragged = Signal(QPoint)
    drag_finished = Signal(QPoint)
    context_requested = Signal(QPoint)
    hover_changed = Signal(bool)

    def enterEvent(self, event) -> None:
        self.hover_changed.emit(True)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self.hover_changed.emit(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.grabMouse()
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
            try:
                self.releaseMouse()
            except Exception:
                pass
            self.drag_finished.emit(event.globalPosition().toPoint())
        super().mouseReleaseEvent(event)
