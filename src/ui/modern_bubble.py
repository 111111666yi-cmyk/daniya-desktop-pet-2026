from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtGui import QColor, QMouseEvent
from PySide6.QtWidgets import QLabel, QGraphicsDropShadowEffect

class ModernBubble(QLabel):
    clicked = Signal()

    def __init__(self, max_width: int = 300, parent=None):
        super().__init__(parent)
        self.setWordWrap(True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.setMaximumWidth(max_width)


        self.normal_style = """
            QLabel {
                color: #2b2b2b;
                background-color: rgba(255, 255, 255, 220);
                border: 1px solid rgba(255, 255, 255, 180);
                border-radius: 12px;
                padding: 10px 14px;
                font-size: 13px;
                font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
            }
        """

        self.thinking_style = """
            QLabel {
                color: #4a6fa5;
                background-color: rgba(240, 248, 255, 230);
                border: 1px solid rgba(100, 150, 255, 200);
                border-radius: 12px;
                padding: 10px 14px;
                font-size: 13px;
                font-style: italic;
                font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
            }
        """

        self.setStyleSheet(self.normal_style)

        # Drop shadow for depth
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(15)
        self.shadow.setColor(QColor(0, 0, 0, 40))
        self.shadow.setOffset(0, 4)
        self.setGraphicsEffect(self.shadow)

        self.hide()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            from PySide6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(self.text())
        super().mouseDoubleClickEvent(event)


    def show_message(self, text: str) -> None:
        self.setText(text)
        if not self.isVisible():
            self.show()

    def setText(self, text: str) -> None:
        super().setText(text)
        # Trigger parent layout resize when text changes
        parent = self.parentWidget()
        while parent:
            if hasattr(parent, "_resize_to_content"):
                parent._resize_to_content()
                break
            parent = parent.parentWidget()

    def set_thinking_state(self, is_thinking: bool) -> None:
        if is_thinking:
            self.setText("✨ 思考中...")
            self.setStyleSheet(self.thinking_style)
            if not self.isVisible():
                self.show()
        else:
            self.setStyleSheet(self.normal_style)
