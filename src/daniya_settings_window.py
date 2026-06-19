from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QTextEdit, QVBoxLayout, QWidget

from core.daniya_status import build_daniya_status, render_daniya_status_text
from .ui.liquid_glass import LiquidGlassDialog

if TYPE_CHECKING:
    from .app import AppController


class DaniyaSettingsDialog(LiquidGlassDialog):
    def __init__(self, controller: "AppController", parent: QWidget | None = None) -> None:
        super().__init__(parent, title="达妮娅设定")
        self.controller = controller
        self.resize(760, 560)

        layout = QVBoxLayout()
        self.editor = QTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.editor.setPlainText(self._build_text())
        layout.addWidget(self.editor)

        close = QPushButton("关闭")
        close.clicked.connect(self.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        self.setLayout(layout)

    def _build_text(self) -> str:
        available_actions = _available_actions(self.controller)
        status = build_daniya_status("daniya", available_actions=available_actions)
        return render_daniya_status_text(status)


def _available_actions(controller: "AppController") -> set[str]:
    asset_manager = getattr(controller, "asset_manager", None)
    if asset_manager is None:
        return set()
    try:
        animations = asset_manager.manifest().get("animations", {})
    except Exception:
        return set()
    if not isinstance(animations, dict):
        return set()
    return {str(key) for key in animations.keys()}
