from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QHBoxLayout,
    QGraphicsDropShadowEffect,
    QPushButton,
    QSizePolicy
)

class StatusBadge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_expanded = False
        self._text = ""

        # Layout
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Star Icon Button
        self.icon_btn = QPushButton("✨")
        self.icon_btn.setFixedSize(16, 16)
        self.icon_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.icon_btn.clicked.connect(self.toggle_expansion)
        self.icon_btn.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(255, 255, 255, 200);
                border: 1px solid rgba(200, 200, 200, 150);
                border-radius: 8px;
                font-size: 10px;
                padding: 0px;
                margin: 0px;
                font-family: "Segoe UI Emoji", "Apple Color Emoji", sans-serif;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 240);
                border: 1px solid rgba(150, 150, 255, 150);
            }
            """
        )

        # Drop shadow for the icon
        shadow1 = QGraphicsDropShadowEffect(self.icon_btn)
        shadow1.setBlurRadius(4)
        shadow1.setColor(QColor(0, 0, 0, 50))
        shadow1.setOffset(0, 2)
        self.icon_btn.setGraphicsEffect(shadow1)

        # Text Label
        self.text_label = QLabel()
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_label.setStyleSheet(
            """
            QLabel {
                color: #ffffff;
                background-color: rgba(50, 50, 50, 200);
                border: 1px solid rgba(255, 255, 255, 50);
                border-radius: 8px;
                padding: 4px 8px;
                font-size: 11px;
                font-family: "Segoe UI", sans-serif;
                font-weight: bold;
            }
            """
        )
        # Drop shadow for the text
        shadow2 = QGraphicsDropShadowEffect(self.text_label)
        shadow2.setBlurRadius(8)
        shadow2.setColor(QColor(0, 0, 0, 80))
        shadow2.setOffset(0, 2)
        self.text_label.setGraphicsEffect(shadow2)

        self.layout.addWidget(self.icon_btn)
        self.layout.addWidget(self.text_label)
        self.text_label.hide()
        self.hide()

    def toggle_expansion(self) -> None:
        if not self._text:
            return
        self.is_expanded = not self.is_expanded
        self.text_label.setVisible(self.is_expanded)
        # Optional: trigger parent layout update or resize
        if self.parentWidget():
            self.parentWidget().adjustSize()

    def update_badge(self, text: str) -> None:
        self._text = text
        if text:
            self.text_label.setText(text)
            self.show()
        else:
            self.hide()
            self.is_expanded = False
            self.text_label.hide()
