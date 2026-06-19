from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .daniya_settings_window import DaniyaSettingsDialog
from .icon_utils import icon as ic
from .story_landing import StoryLandingWindow
from .ui.liquid_glass import LiquidGlassDialog
from .utils import resource_path

if TYPE_CHECKING:
    from .app import AppController
    from .pet_window import PetWindow


class MenuManager:
    def __init__(self, window: "PetWindow", controller: "AppController") -> None:
        self.window = window
        self.controller = controller

    def create_menu(self) -> QMenu:
        menu = QMenu(self.window)
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect(menu)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 40))
        shadow.setOffset(0, 4)
        menu.setGraphicsEffect(shadow)
        menu.setStyleSheet(
            """
            QMenu {
                background-color: rgba(255, 255, 255, 230);
                border: 1px solid rgba(255, 255, 255, 200);
                border-radius: 12px;
                padding: 6px;
                font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
                color: #2b2b2b;
            }
            QMenu::item {
                padding: 6px 24px 6px 24px;
                border-radius: 4px;
                margin: 2px 4px;
            }
            QMenu::item:selected {
                background-color: rgba(100, 150, 255, 50);
                color: #000000;
            }
            QMenu::separator {
                height: 1px;
                background-color: rgba(200, 200, 200, 150);
                margin: 4px 10px;
            }
            """
        )

        # 1. 输入框开关
        input_action = menu.addAction(
            ic("document"),
            "隐藏输入框" if self.window.input_box.isVisible() else "显示输入框",
        )
        input_action.triggered.connect(self._toggle_input)

        # 2. 功能中心
        hub_action = menu.addAction(ic("chip"), "功能中心")
        hub_action.triggered.connect(self._open_function_center)

        # 3. 设置
        settings_action = menu.addAction(ic("settings"), "设置")
        settings_action.triggered.connect(self.controller.open_settings_center)

        # 4. 召唤
        call_action = menu.addAction(ic("laptop"), "召唤到鼠标")
        call_action.triggered.connect(self._call_pet_to_cursor)

        # 5. 帮助
        help_action = menu.addAction(ic("info"), "帮助")
        help_action.triggered.connect(self.show_help_dialog)

        menu.addSeparator()

        # 6. 更多
        more = menu.addMenu(ic("host"), "更多")

        size_menu = more.addMenu(ic("size"), "大小")
        labels = {
            80: "迷你 80px",
            96: "推荐 96px",
            112: "稍大 112px",
            128: "清晰 128px",
            144: "大号 144px",
            160: "最大 160px",
        }
        current_height = self.controller.asset_manager.target_height()
        for height in self.controller.asset_manager.size_presets():
            action = size_menu.addAction(labels.get(height, f"{height}px"))
            action.setCheckable(True)
            action.setChecked(height == current_height)
            action.triggered.connect(lambda checked=False, value=height: self.controller.save_pet_height(value))

        intensity_menu = more.addMenu(ic("chip"), "行为强度")
        current_intensity = self.controller.app_config.get("behavior_intensity", "lively")
        for key, label in [("quiet", "安静"), ("lively", "活泼"), ("demo", "演示")]:
            act = intensity_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(key == current_intensity)
            act.triggered.connect(lambda checked=False, k=key: self._set_behavior_intensity(k))

        renderer_menu = more.addMenu(ic("chip"), "渲染器")
        current_renderer = self.controller.app_config.get("renderer_type", "png")
        for key, label in [("png", "PNG 帧渲染"), ("morph_blend", "形变混合")]:
            act = renderer_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(key == current_renderer)
            act.triggered.connect(lambda checked=False, k=key: self._set_renderer_type(k))

        top_action = more.addAction(ic("upload"), "取消置顶" if self.window.always_on_top else "保持置顶")
        top_action.triggered.connect(self._toggle_top)

        if self.window.is_minimized_to_tray():
            restore_action = more.addAction(ic("upload"), "恢复显示")
            restore_action.triggered.connect(self.window.restore_from_tray)
        else:
            minimize_action = more.addAction(ic("download"), "最小化到托盘")
            minimize_action.triggered.connect(self.window.minimize_to_tray)

        demo_action = more.addAction(ic("chip"), "演示模式")
        demo_action.triggered.connect(self._start_demo)

        dnd_action = more.addAction(ic("host"), "勿扰模式")
        dnd_action.setCheckable(True)
        dnd_action.setChecked(bool(self.controller.app_config.get("dnd_mode", False)))
        dnd_action.triggered.connect(self._toggle_dnd)

        click_through_action = more.addAction(ic("laptop"), "点击穿透")
        click_through_action.setCheckable(True)
        click_through_action.setChecked(bool(self.controller.app_config.get("click_through", False)))
        click_through_action.triggered.connect(self._toggle_click_through)

        self._add_pet_feature_menu(more)

        menu.addSeparator()

        # 7. 退出
        exit_action = menu.addAction(ic("settings"), "退出")
        exit_action.triggered.connect(self.controller.quit)

        return menu

    def _open_function_center(self) -> None:
        from .function_center import FunctionCenterDialog
        dialog = FunctionCenterDialog(self.controller, self.window)
        dialog.exec()

    def _add_pet_feature_menu(self, parent: QMenu) -> None:
        pet_features = parent.addMenu(ic("info"), "宠物功能")
        pet_config = self.controller.app_config.get("pet", {})

        hover_action = pet_features.addAction("鼠标悬停动作")
        hover_action.setCheckable(True)
        hover_action.setChecked(bool(pet_config.get("hover_animation_enabled", False)))
        hover_action.triggered.connect(
            lambda checked=False: self.controller.set_pet_feature("hover_animation_enabled", bool(checked))
        )

        edge_action = pet_features.addAction("左右边缘探头")
        edge_action.setCheckable(True)
        edge_action.setChecked(bool(pet_config.get("edge_peek_enabled", False)))
        edge_action.triggered.connect(
            lambda checked=False: self.controller.set_pet_feature("edge_peek_enabled", bool(checked))
        )

        call_action = pet_features.addAction("左键点击桌面召唤")
        call_action.setCheckable(True)
        call_action.setChecked(bool(pet_config.get("click_to_call_enabled", False)))
        call_action.triggered.connect(
            lambda checked=False: self.controller.set_pet_feature("click_to_call_enabled", bool(checked))
        )

        modules = pet_config.get("enabled_action_modules", {})
        drag_action = pet_features.addAction("E 拖拽动作系统")
        drag_action.setCheckable(True)
        drag_action.setChecked(not isinstance(modules, dict) or bool(modules.get("E_QQ_pet_drag_system", True)))
        drag_action.triggered.connect(lambda checked=False: self.controller.set_drag_module_enabled(bool(checked)))

    def _toggle_top(self) -> None:
        enabled = not self.window.always_on_top
        self.window.set_always_on_top(enabled)
        self.controller.app_config.setdefault("window", {})["always_on_top"] = enabled
        self.controller.config_manager.save_app_config(self.controller.app_config)
        self.window.set_context_menu(self.create_menu())

    def _toggle_dnd(self, checked: bool) -> None:
        self.controller.app_config["dnd_mode"] = checked
        self.controller.config_manager.save_app_config(self.controller.app_config)
        if hasattr(self.controller, "behavior_engine") and self.controller.behavior_engine:
            self.controller.behavior_engine.reload_config(self.controller.app_config)
        self.window.set_context_menu(self.create_menu())

    def _toggle_click_through(self, checked: bool) -> None:
        self.controller.app_config["click_through"] = checked
        self.controller.config_manager.save_app_config(self.controller.app_config)
        self.window.set_click_through(checked)
        self.window.set_context_menu(self.create_menu())

    def _start_demo(self) -> None:
        from .behavior.demo_mode import DemoMode
        if not hasattr(self, "_demo") or not self._demo.is_running():
            self._demo = DemoMode(self.window)
            self._demo.finished.connect(lambda: self.window.speak("……演示结束。"))
            self._demo.start()

    def _set_renderer_type(self, renderer_type: str) -> None:
        self.controller.app_config["renderer_type"] = renderer_type
        self.controller.config_manager.save_app_config(self.controller.app_config)
        self.window.set_renderer_type(renderer_type)
        self.window.set_context_menu(self.create_menu())

    def _set_behavior_intensity(self, intensity: str) -> None:
        self.controller.app_config["behavior_intensity"] = intensity
        self.controller.config_manager.save_app_config(self.controller.app_config)
        if hasattr(self.controller, "behavior_engine") and self.controller.behavior_engine:
            self.controller.behavior_engine.reload_config(self.controller.app_config)
        self.window.set_context_menu(self.create_menu())

    def _toggle_input(self) -> None:
        self.window.toggle_input()
        self.controller.app_config.setdefault("window", {})["show_input"] = self.window.input_box.isVisible()
        self.controller.config_manager.save_app_config(self.controller.app_config)
        self.window.set_context_menu(self.create_menu())

    def _call_pet_to_cursor(self) -> None:
        self.window.move_near(QCursor.pos())
        self.window.raise_()
        self.window.activateWindow()

    def show_history_dialog(self) -> None:
        dialog = HistoryDialog(self.controller, self.window)
        dialog.exec()

    def show_prompt_dialog(self) -> None:
        dialog = QDialog(self.window)
        dialog.setWindowTitle("人设设置")
        dialog.resize(620, 480)
        layout = QVBoxLayout(dialog)
        editor = QTextEdit()
        editor.setPlainText(self.controller.config_manager.load_system_prompt())
        layout.addWidget(editor)

        buttons = QHBoxLayout()
        save = QPushButton("保存")
        cancel = QPushButton("取消")
        buttons.addStretch(1)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

        def on_save() -> None:
            self.controller.save_system_prompt(editor.toPlainText())
            dialog.accept()

        save.clicked.connect(on_save)
        cancel.clicked.connect(dialog.reject)
        dialog.exec()

    def show_profile_dialog(self) -> None:
        dialog = QDialog(self.window)
        dialog.setWindowTitle("用户档案")
        form = QFormLayout(dialog)
        profile = self.controller.profile_manager.load()
        user_name = QLineEdit(profile["user_name"])
        birthday = QLineEdit(profile.get("birthday", ""))
        birthday.setPlaceholderText("月-日，例如 03-14")
        relationship = QLineEdit(profile["relationship"])
        style = QLineEdit(profile["style"])
        form.addRow("用户称呼", user_name)
        form.addRow("生日（月-日，可留空）", birthday)
        form.addRow("关系设定", relationship)
        form.addRow("期望风格", style)
        privacy_hint = QLabel("生日只保存月和日，不读取系统账户资料，也不要求填写年份。")
        privacy_hint.setWordWrap(True)
        form.addRow("", privacy_hint)

        buttons = QHBoxLayout()
        save = QPushButton("保存")
        cancel = QPushButton("取消")
        buttons.addStretch(1)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        form.addRow(buttons)

        def on_save() -> None:
            self.controller.save_profile(
                {
                    "user_name": user_name.text(),
                    "birthday": birthday.text(),
                    "relationship": relationship.text(),
                    "style": style.text(),
                }
            )
            dialog.accept()

        save.clicked.connect(on_save)
        cancel.clicked.connect(dialog.reject)
        dialog.exec()

    def show_daniya_settings_dialog(self) -> None:
        dialog = DaniyaSettingsDialog(self.controller, self.window)
        dialog.exec()

    def show_story_dialog(self) -> None:
        """剧情阅读：电影式 Liquid Glass 落地页 + 阅读器。"""
        dialog = StoryLandingWindow(self.controller, self.window)
        dialog.exec()

    def show_note_dialog(self) -> None:
        dialog = QDialog(self.window)
        dialog.setWindowTitle("记一笔")
        dialog.resize(360, 220)
        layout = QVBoxLayout(dialog)
        editor = QTextEdit()
        editor.setPlaceholderText("写下想让达妮娅帮你记住的小事...")
        layout.addWidget(editor)
        buttons = QHBoxLayout()
        save = QPushButton("保存")
        cancel = QPushButton("取消")
        buttons.addStretch(1)
        buttons.addWidget(save)
        buttons.addWidget(cancel)
        layout.addLayout(buttons)

        def on_save() -> None:
            self.controller.add_note(editor.toPlainText())
            dialog.accept()

        save.clicked.connect(on_save)
        cancel.clicked.connect(dialog.reject)
        dialog.exec()

    def show_reminder_dialog(self) -> None:
        dialog = QDialog(self.window)
        dialog.setWindowTitle("日程提醒")
        dialog.resize(520, 420)
        layout = QVBoxLayout(dialog)

        form = QFormLayout()
        time_edit = QDateTimeEdit(QDateTime.currentDateTime().addSecs(60))
        time_edit.setDisplayFormat("yyyy-MM-dd HH:mm")
        time_edit.setCalendarPopup(True)
        text_input = QLineEdit()
        text_input.setPlaceholderText("例如：复习电路图")
        form.addRow("时间", time_edit)
        form.addRow("事项", text_input)
        layout.addLayout(form)

        add_button = QPushButton("添加提醒")
        layout.addWidget(add_button, alignment=Qt.AlignmentFlag.AlignRight)
        records_label = QLabel(self._reminder_summary())
        records_label.setWordWrap(True)
        layout.addWidget(records_label)

        close = QPushButton("关闭")
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

        def on_add() -> None:
            ok, message = self.controller.add_reminder(
                time_edit.dateTime().toString("yyyy-MM-dd HH:mm"),
                text_input.text(),
            )
            if ok:
                text_input.clear()
                records_label.setText(self._reminder_summary())
            else:
                QMessageBox.warning(dialog, "提醒没有保存", message)

        add_button.clicked.connect(on_add)
        close.clicked.connect(dialog.accept)
        dialog.exec()

    def show_help_dialog(self) -> None:
        dialog = HelpDialog(self.window)
        dialog.exec()

    def _show_portals_dialog(self) -> None:
        records = self.controller.bookmark_manager.records()
        if not records:
            QMessageBox.information(self.window, "传送门", "还没有添加书签。")
            return
        dialog = QDialog(self.window)
        dialog.setWindowTitle("传送门")
        dialog.resize(360, 300)
        layout = QVBoxLayout(dialog)
        for item in records:
            btn = QPushButton(item["name"])
            url = item["url"]
            btn.clicked.connect(lambda checked=False, u=url: (dialog.accept(), self.controller.open_bookmark(u)))
            layout.addWidget(btn)
        layout.addStretch()
        close = QPushButton("关闭")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def _show_games_dialog(self) -> None:
        dialog = QDialog(self.window)
        dialog.setWindowTitle("小游戏")
        dialog.resize(300, 240)
        layout = QVBoxLayout(dialog)

        rps_label = QLabel("猜拳：")
        layout.addWidget(rps_label)
        rps_layout = QHBoxLayout()
        for choice in ("石头", "剪刀", "布"):
            btn = QPushButton(choice)
            btn.clicked.connect(lambda checked=False, v=choice: (dialog.accept(), self.controller.play_rps(v)))
            rps_layout.addWidget(btn)
        layout.addLayout(rps_layout)

        dice_btn = QPushButton("掷骰子")
        dice_btn.clicked.connect(lambda: (dialog.accept(), self.controller.roll_dice()))
        layout.addWidget(dice_btn)

        rand_btn = QPushButton("随机数 1-100")
        rand_btn.clicked.connect(lambda: (dialog.accept(), self.controller.random_100()))
        layout.addWidget(rand_btn)

        layout.addStretch()
        close = QPushButton("关闭")
        close.clicked.connect(dialog.accept)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        dialog.exec()

    def _reminder_summary(self) -> str:
        records = self.controller.reminder_manager.records()
        pending = [item for item in records if not bool(item.get("done"))]
        if not pending:
            return "当前没有待提醒事项。"
        lines = ["待提醒："]
        for item in pending[-8:]:
            lines.append(f"- {item.get('time', '')}  {item.get('text', '')}")
        return "\n".join(lines)


class HistoryDialog(LiquidGlassDialog):
    def __init__(self, controller: "AppController", parent: QWidget) -> None:
        super().__init__(parent, title="历史记录")
        self.controller = controller
        self.resize(720, 520)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        layout = QVBoxLayout()
        layout.addWidget(self.scroll)
        self.setLayout(layout)
        self.refresh()

    def refresh(self) -> None:
        records = self.controller.history_manager.records()
        container = QWidget()
        box = QVBoxLayout(container)

        if not records:
            box.addWidget(QLabel("还没有聊天记录。"))

        for record in reversed(records):
            row = QWidget()
            row_layout = QHBoxLayout(row)
            text = QLabel(
                f"{record.get('timestamp', '')}  [{record.get('source', '')}]\n"
                f"你：{record.get('user', '')}\n"
                f"达妮娅：{record.get('assistant', '')}"
            )
            text.setWordWrap(True)
            text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

            copy_button = QPushButton("复制")
            record_text = (
                f"你：{record.get('user', '')}\n"
                f"达妮娅：{record.get('assistant', '')}"
            )
            copy_button.clicked.connect(lambda checked=False, txt=record_text: self.copy_text(txt))

            delete_button = QPushButton("删除")
            record_id = str(record.get("id", ""))
            delete_button.clicked.connect(lambda checked=False, rid=record_id: self.delete_record(rid))

            row_layout.addWidget(text, 1)
            row_layout.addWidget(copy_button)
            row_layout.addWidget(delete_button)
            box.addWidget(row)

        box.addStretch(1)
        self.scroll.setWidget(container)

    def copy_text(self, text: str) -> None:
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(text)

    def delete_record(self, record_id: str) -> None:
        if not record_id:
            return
        result = QMessageBox.question(self, "删除记录", "确定删除这条记录吗？")
        if result == QMessageBox.StandardButton.Yes:
            self.controller.history_manager.delete(record_id)
            self.refresh()


class HelpDialog(LiquidGlassDialog):
    """帮助页：玻璃外壳 + 左侧 TOC + 搜索。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, title="帮助")
        self.resize(760, 560)

        content = self._load_content()
        self._headings = self._parse_headings(content)

        body = QVBoxLayout()
        body.setSpacing(6)

        self._search = QLineEdit()
        self._search.setPlaceholderText("搜索帮助内容...")
        self._search.textChanged.connect(self._on_search)
        body.addWidget(self._search)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._toc = QListWidget()
        self._toc.setFixedWidth(160)
        self._toc.setStyleSheet(
            "QListWidget { background: transparent; border: none; font-size: 12px; }"
            "QListWidget::item { padding: 4px 6px; border-radius: 4px; }"
            "QListWidget::item:selected { background: rgba(100, 150, 255, 60); }"
        )
        for heading in self._headings:
            item = QListWidgetItem(heading)
            self._toc.addItem(item)
        self._toc.currentRowChanged.connect(self._on_toc_click)
        splitter.addWidget(self._toc)

        self._editor = QTextEdit()
        self._editor.setReadOnly(True)
        self._editor.setMarkdown(content)
        splitter.addWidget(self._editor)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        body.addWidget(splitter)

        self.setLayout(body)

    @staticmethod
    def _load_content() -> str:
        help_path = resource_path("docs", "help.md")
        if not help_path.exists():
            help_path = resource_path("README.md")
        try:
            return help_path.read_text(encoding="utf-8")
        except OSError:
            return "没有找到帮助文档。"

    @staticmethod
    def _parse_headings(content: str) -> list[str]:
        headings: list[str] = []
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("## "):
                headings.append(stripped.lstrip("# ").strip())
            elif stripped.startswith("### "):
                headings.append("  " + stripped.lstrip("# ").strip())
        return headings

    def _on_toc_click(self, row: int) -> None:
        if row < 0 or row >= len(self._headings):
            return
        heading = self._headings[row].strip()
        self._editor.find(heading)

    def _on_search(self, text: str) -> None:
        if not text:
            cursor = self._editor.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            self._editor.setTextCursor(cursor)
            return
        cursor = self._editor.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        self._editor.setTextCursor(cursor)
        self._editor.find(text)
