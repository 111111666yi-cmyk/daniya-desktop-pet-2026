from PySide6.QtCore import Qt, QPoint, QSize
from PySide6.QtGui import QMouseEvent, QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QDialog,
    QSizeGrip,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
    QGraphicsDropShadowEffect,
)

class LiquidGlassDialog(QDialog):
    """
    A modern, frameless, translucent dialog with a custom title bar
    and a glassmorphic background effect.
    """
    def __init__(self, parent=None, title="", resizable=True):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._base_layout = QVBoxLayout(self)
        self._base_layout.setContentsMargins(15, 15, 15, 15)

        self.glass_frame = QWidget(self)
        self.glass_frame.setObjectName("liquidGlassFrame")
        self.glass_frame.setStyleSheet(
            """
            QWidget#liquidGlassFrame {
                background-color: rgba(255, 255, 255, 220);
                border: 1px solid rgba(255, 255, 255, 200);
                border-radius: 12px;
            }
            """
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(25)
        shadow.setColor(QColor(0, 0, 0, 50))
        shadow.setOffset(0, 5)
        self.glass_frame.setGraphicsEffect(shadow)

        self._base_layout.addWidget(self.glass_frame)

        self.frame_layout = QVBoxLayout(self.glass_frame)
        self.frame_layout.setContentsMargins(10, 10, 10, 10)
        self.frame_layout.setSpacing(6)

        # Title bar
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(30)
        self.title_layout = QHBoxLayout(self.title_bar)
        self.title_layout.setContentsMargins(5, 0, 5, 0)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #2b2b2b; font-family: 'Segoe UI', sans-serif;")

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(26, 26)
        self.close_btn.setStyleSheet(
            """
            QPushButton {
                background: transparent;
                border: none;
                font-size: 14px;
                color: #666;
            }
            QPushButton:hover {
                background: rgba(255, 60, 60, 200);
                color: white;
                border-radius: 13px;
            }
            """
        )
        self.close_btn.clicked.connect(self.reject)

        self.title_layout.addWidget(self.title_label)
        self.title_layout.addStretch()
        self.title_layout.addWidget(self.close_btn)

        self.frame_layout.addWidget(self.title_bar)

        # Global stylesheet for child components to inherit transparency
        self.setStyleSheet(
            """
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QTabWidget::pane {
                border: 1px solid rgba(200, 200, 200, 100);
                background: transparent;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: rgba(240, 240, 240, 150);
                border: 1px solid rgba(200, 200, 200, 100);
                padding: 6px 12px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: rgba(255, 255, 255, 200);
                border-bottom-color: transparent;
            }
            QGroupBox {
                border: 1px solid rgba(200, 200, 200, 120);
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 3px;
                left: 10px;
                color: #555;
            }
            QLineEdit, QTextEdit, QComboBox {
                background: rgba(255, 255, 255, 180);
                border: 1px solid rgba(200, 200, 200, 150);
                border-radius: 4px;
                padding: 4px;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
                border: 1px solid rgba(100, 150, 255, 200);
            }
            QPushButton {
                background: rgba(245, 245, 245, 180);
                border: 1px solid rgba(200, 200, 200, 150);
                border-radius: 4px;
                padding: 5px 12px;
                color: #333;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 220);
                border: 1px solid rgba(150, 150, 150, 150);
            }
            """
        )

        if resizable:
            grip = QSizeGrip(self)
            grip.setFixedSize(16, 16)
            grip.setStyleSheet("background: transparent;")
            grip_row = QHBoxLayout()
            grip_row.addStretch()
            grip_row.addWidget(grip)
            self.frame_layout.addLayout(grip_row)

        self._drag_pos = None

    def setLayout(self, layout):
        """Override setLayout to inject user layouts into our glass frame."""
        self.frame_layout.addLayout(layout)

    def setWindowTitle(self, title: str):
        self.title_label.setText(title)
        super().setWindowTitle(title)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.title_bar.geometry().contains(event.pos()):
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)
