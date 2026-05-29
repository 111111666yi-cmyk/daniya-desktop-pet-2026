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
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .daniya_settings_window import DaniyaSettingsDialog
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

        basic = menu.addMenu("基础")
        input_action = basic.addAction("显示输入框" if not self.window.input_box.isVisible() else "隐藏输入框")
        input_action.triggered.connect(self._toggle_input)

        top_action = basic.addAction("取消置顶" if self.window.always_on_top else "保持置顶")
        top_action.triggered.connect(self._toggle_top)

        call_here_action = basic.addAction("召唤到鼠标位置")
        call_here_action.triggered.connect(self._call_pet_to_cursor)

        size_menu = basic.addMenu("大小")
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

        self._add_action_module_menu(basic)
        self._add_pet_feature_menu(basic)

        chat = menu.addMenu("对话")
        history_action = chat.addAction("历史记录")
        history_action.triggered.connect(self.show_history_dialog)
        prompt_action = chat.addAction("人设设置")
        prompt_action.triggered.connect(self.show_prompt_dialog)
        profile_action = chat.addAction("御主档案")
        profile_action.triggered.connect(self.show_profile_dialog)
        daniya_settings_action = chat.addAction("达妮娅设定")
        daniya_settings_action.triggered.connect(self.show_daniya_settings_dialog)
        settings_center_action = chat.addAction("设置中心")
        settings_center_action.triggered.connect(self.controller.open_settings_center)

        companion = menu.addMenu("陪伴")
        note_action = companion.addAction("记一笔")
        note_action.triggered.connect(self.show_note_dialog)
        reminder_action = companion.addAction("日程提醒")
        reminder_action.triggered.connect(self.show_reminder_dialog)

        games = companion.addMenu("小游戏")
        rps = games.addMenu("猜拳")
        for choice in ("石头", "剪刀", "布"):
            action = rps.addAction(choice)
            action.triggered.connect(lambda checked=False, value=choice: self.controller.play_rps(value))
        dice_action = games.addAction("掷骰子")
        dice_action.triggered.connect(self.controller.roll_dice)
        random_action = games.addAction("随机数 1-100")
        random_action.triggered.connect(self.controller.random_100)

        bookmarks = companion.addMenu("传送门")
        for item in self.controller.bookmark_manager.records():
            action = bookmarks.addAction(item["name"])
            action.triggered.connect(lambda checked=False, url=item["url"]: self.controller.open_bookmark(url))

        system = menu.addMenu("系统")
        help_action = system.addAction("帮助")
        help_action.triggered.connect(self.show_help_dialog)
        exit_action = system.addAction("退出")
        exit_action.triggered.connect(self.controller.quit)

        return menu

    def _add_action_module_menu(self, parent: QMenu) -> None:
        module_menu = parent.addMenu("动作模组")
        module_labels = {
            "A_sit_base": "A 坐姿 / 表情",
            "B_stand_base_pack": "B 站姿 / 挥手",
            "C_sleep_base_pack": "C 睡姿",
            "D_special_motion_pack": "D 特殊 / 探头",
        }
        active_module = self.controller.asset_manager.active_action_module()
        for module, label in module_labels.items():
            action = module_menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(module == active_module)
            action.triggered.connect(lambda checked=False, value=module: self.controller.set_action_module(value))

    def _add_pet_feature_menu(self, parent: QMenu) -> None:
        pet_features = parent.addMenu("宠物功能")
        pet_config = self.controller.app_config.get("pet", {})

        hover_action = pet_features.addAction("鼠标悬停动作")
        hover_action.setCheckable(True)
        hover_action.setChecked(bool(pet_config.get("hover_animation_enabled", False)))
        hover_action.triggered.connect(
            lambda checked=False: self.controller.set_pet_feature("hover_animation_enabled", bool(checked))
        )

        edge_action = pet_features.addAction("左右边缘探头")
        edge_action.setCheckable(True)
        edge_action.setChecked(bool(pet_config.get("edge_peek_enabled", True)))
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
        dialog.setWindowTitle("御主档案")
        form = QFormLayout(dialog)
        profile = self.controller.profile_manager.load()
        user_name = QLineEdit(profile["user_name"])
        relationship = QLineEdit(profile["relationship"])
        style = QLineEdit(profile["style"])
        form.addRow("用户称呼", user_name)
        form.addRow("关系设定", relationship)
        form.addRow("期望风格", style)

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
        help_path = resource_path("docs", "help.md")
        if not help_path.exists():
            help_path = resource_path("README.md")
        try:
            content = help_path.read_text(encoding="utf-8")
        except OSError:
            content = "没有找到帮助文档。"

        dialog = QDialog(self.window)
        dialog.setWindowTitle("帮助")
        dialog.resize(700, 520)
        layout = QVBoxLayout(dialog)
        editor = QTextEdit()
        editor.setReadOnly(True)
        editor.setPlainText(content)
        layout.addWidget(editor)
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


class HistoryDialog(QDialog):
    def __init__(self, controller: "AppController", parent: QWidget) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setWindowTitle("历史记录")
        self.resize(720, 520)
        self.layout = QVBoxLayout(self)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.layout.addWidget(self.scroll)
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
            delete_button = QPushButton("删除")
            record_id = str(record.get("id", ""))
            delete_button.clicked.connect(lambda checked=False, rid=record_id: self.delete_record(rid))
            row_layout.addWidget(text, 1)
            row_layout.addWidget(delete_button)
            box.addWidget(row)

        box.addStretch(1)
        self.scroll.setWidget(container)

    def delete_record(self, record_id: str) -> None:
        if not record_id:
            return
        result = QMessageBox.question(self, "删除记录", "确定删除这条记录吗？")
        if result == QMessageBox.StandardButton.Yes:
            self.controller.history_manager.delete(record_id)
            self.refresh()
