from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .ui.liquid_glass import LiquidGlassDialog

if TYPE_CHECKING:
    from .app import AppController


class _FeatureCard(QPushButton):
    """A clickable card representing a feature in the Function Center."""

    def __init__(self, emoji: str, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(130, 90)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setText(f"{emoji}\n{title}")
        self.setStyleSheet(
            """
            QPushButton {
                background: rgba(255, 255, 255, 160);
                border: 1px solid rgba(200, 200, 200, 120);
                border-radius: 10px;
                font-size: 13px;
                color: #333;
                padding: 8px;
            }
            QPushButton:hover {
                background: rgba(255, 255, 255, 220);
                border: 1px solid rgba(150, 170, 255, 180);
            }
            QPushButton:pressed {
                background: rgba(230, 240, 255, 200);
            }
            """
        )


class FunctionCenterDialog(LiquidGlassDialog):
    """Hub panel that collects all companion / utility features."""

    def __init__(self, controller: "AppController", parent: QWidget | None = None) -> None:
        super().__init__(parent, title="功能中心")
        self.controller = controller
        self.resize(480, 420)

        body = QVBoxLayout()
        body.setSpacing(12)

        hint = QLabel("选择一个功能开始")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet("color: #888; font-size: 12px;")
        body.addWidget(hint)

        grid = QGridLayout()
        grid.setSpacing(12)

        cards = [
            ("📖", "剧情", self._open_story),
            ("🌱", "养成中心", self._open_growth),
            ("🍅", "番茄钟", self._open_pomodoro),
            ("⏰", "日程提醒", self._open_reminder),
            ("📂", "文件整理", self._open_file_organizer),
            ("🔗", "传送门", self._open_portals),
            ("📝", "记一笔", self._open_note),
            ("🎮", "小游戏", self._open_games),
            ("💬", "历史记录", self._open_history),
        ]

        for i, (emoji, title, callback) in enumerate(cards):
            card = _FeatureCard(emoji, title)
            card.clicked.connect(callback)
            grid.addWidget(card, i // 3, i % 3, Qt.AlignmentFlag.AlignCenter)

        body.addLayout(grid)
        body.addStretch()
        self.setLayout(body)

    def _open_story(self) -> None:
        self.accept()
        from .menu_manager import MenuManager
        mm = MenuManager(self.controller.window, self.controller)
        mm.show_story_dialog()

    def _open_growth(self) -> None:
        self.accept()
        self.controller.open_growth_center()

    def _open_pomodoro(self) -> None:
        self.accept()
        if getattr(self.controller, "pomodoro", None) is not None and self.controller.pomodoro.active:
            self.controller.cancel_pomodoro()
        else:
            self.controller.start_pomodoro(25)

    def _open_reminder(self) -> None:
        self.accept()
        from .menu_manager import MenuManager
        mm = MenuManager(self.controller.window, self.controller)
        mm.show_reminder_dialog()

    def _open_file_organizer(self) -> None:
        self.accept()
        self.controller.open_file_organizer()

    def _open_portals(self) -> None:
        self.accept()
        from .menu_manager import MenuManager
        mm = MenuManager(self.controller.window, self.controller)
        mm._show_portals_dialog()

    def _open_note(self) -> None:
        self.accept()
        from .menu_manager import MenuManager
        mm = MenuManager(self.controller.window, self.controller)
        mm.show_note_dialog()

    def _open_games(self) -> None:
        self.accept()
        from .menu_manager import MenuManager
        mm = MenuManager(self.controller.window, self.controller)
        mm._show_games_dialog()

    def _open_history(self) -> None:
        self.accept()
        from .menu_manager import MenuManager
        mm = MenuManager(self.controller.window, self.controller)
        mm.show_history_dialog()
