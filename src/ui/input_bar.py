from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QColor, QCursor
from PySide6.QtWidgets import (
    QWidget,
    QLineEdit,
    QPushButton,
    QHBoxLayout,
    QGraphicsDropShadowEffect,
    QSizePolicy
)

class CustomLineEdit(QLineEdit):
    focus_lost = Signal()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.focus_lost.emit()

class InputBar(QWidget):
    submitted = Signal(str)

    def __init__(self, min_width: int = 180, parent=None):
        super().__init__(parent)
        self._stored_min_width = min_width
        self.always_expanded = False

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(4)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # Chat Icon Button
        self.icon_btn = QPushButton("💬")
        self.icon_btn.setFixedSize(28, 28)
        self.icon_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.icon_btn.clicked.connect(self._on_icon_clicked)
        self.icon_btn.setStyleSheet(
            """
            QPushButton {
                background-color: rgba(255, 255, 255, 200);
                border: 1px solid rgba(200, 200, 200, 150);
                border-radius: 14px;
                font-size: 14px;
                padding: 0px;
                margin: 0px;
                font-family: "Segoe UI Emoji", "Apple Color Emoji", sans-serif;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 240);
                border: 1px solid rgba(100, 150, 255, 150);
            }
            """
        )

        shadow1 = QGraphicsDropShadowEffect(self.icon_btn)
        shadow1.setBlurRadius(4)
        shadow1.setColor(QColor(0, 0, 0, 50))
        shadow1.setOffset(0, 2)
        self.icon_btn.setGraphicsEffect(shadow1)

        # Line Edit
        self.line_edit = CustomLineEdit()
        self.line_edit.setPlaceholderText("和达妮娅说点什么...")
        self.line_edit.setMinimumWidth(min_width)
        self.line_edit.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.line_edit.setStyleSheet(
            """
            QLineEdit {
                color: #2b2b2b;
                background-color: rgba(255, 255, 255, 220);
                border: 1px solid rgba(200, 200, 200, 150);
                border-radius: 15px;
                padding: 6px 12px;
                font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
            }
            QLineEdit:focus {
                border: 1px solid rgba(100, 150, 255, 200);
                background-color: rgba(255, 255, 255, 240);
            }
            """
        )

        shadow2 = QGraphicsDropShadowEffect(self.line_edit)
        shadow2.setBlurRadius(10)
        shadow2.setColor(QColor(0, 0, 0, 30))
        shadow2.setOffset(0, 2)
        self.line_edit.setGraphicsEffect(shadow2)

        self.line_edit.returnPressed.connect(self._on_return_pressed)

        # Debounce focus lost to allow clicks on submit buttons if any
        self.line_edit.focus_lost.connect(self._on_focus_lost)

        self.layout.addWidget(self.icon_btn)
        self.layout.addWidget(self.line_edit)

        self.line_edit.hide()

    def _on_icon_clicked(self) -> None:
        if self.line_edit.isVisible():
            self.collapse_input()
        else:
            self.expand_input()

    def expand_input(self) -> None:
        self.icon_btn.setText("✕")
        self.line_edit.show()
        self.line_edit.setFocus()
        self.setMinimumWidth(self._stored_min_width + 32)
        self.setMaximumWidth(16777215)
        if self.parentWidget():
            self.parentWidget().adjustSize()

    def collapse_input(self) -> None:
        self.line_edit.hide()
        self.line_edit.clear()
        self.icon_btn.setText("💬")
        self.setMinimumWidth(0)
        self.setMaximumWidth(28)
        if self.parentWidget():
            self.parentWidget().adjustSize()

    def _on_focus_lost(self) -> None:
        # Delay collapsing slightly in case the app is just switching windows
        QTimer.singleShot(100, self._check_focus_and_collapse)

    def _check_focus_and_collapse(self) -> None:
        if self.always_expanded:
            return
        if not self.line_edit.hasFocus():
            self.collapse_input()

    def _on_return_pressed(self) -> None:
        text = self.line_edit.text().strip()
        if text:
            self.line_edit.clear()
            self.submitted.emit(text)
        if not self.always_expanded:
            self.collapse_input()

    def setEnabled(self, enabled: bool) -> None:
        self.icon_btn.setEnabled(enabled)
        self.line_edit.setEnabled(enabled)
        super().setEnabled(enabled)

    def toggle_visibility(self) -> bool:
        """Called by shortcut key to open input"""
        if self.line_edit.isVisible():
            self.collapse_input()
            return False
        else:
            self.expand_input()
            return True
