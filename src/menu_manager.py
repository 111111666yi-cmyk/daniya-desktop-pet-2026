from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import yaml

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
from .icon_utils import icon as ic
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
        # [MODERN UI] Apply modern QSS to context menu
        menu.setStyleSheet(
            """
            QMenu {
                background-color: rgba(255, 255, 255, 240);
                border: 1px solid rgba(200, 200, 200, 150);
                border-radius: 8px;
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

        basic = menu.addMenu(ic("settings"), "基础")
        input_action = basic.addAction(ic("document"), "显示输入框" if not self.window.input_box.isVisible() else "隐藏输入框")
        input_action.triggered.connect(self._toggle_input)

        top_action = basic.addAction(ic("upload"), "取消置顶" if self.window.always_on_top else "保持置顶")
        top_action.triggered.connect(self._toggle_top)

        call_here_action = basic.addAction(ic("laptop"), "召唤到鼠标位置")
        call_here_action.triggered.connect(self._call_pet_to_cursor)

        if self.window.is_minimized_to_tray():
            restore_action = basic.addAction(ic("upload"), "恢复显示")
            restore_action.triggered.connect(self.window.restore_from_tray)
        else:
            minimize_action = basic.addAction(ic("download"), "最小化到托盘")
            minimize_action.triggered.connect(self.window.minimize_to_tray)

        size_menu = basic.addMenu(ic("size"), "大小")
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

        chat = menu.addMenu(ic("internet"), "对话")
        history_action = chat.addAction(ic("document"), "历史记录")
        history_action.triggered.connect(self.show_history_dialog)
        prompt_action = chat.addAction(ic("settings"), "人设设置")
        prompt_action.triggered.connect(self.show_prompt_dialog)
        profile_action = chat.addAction(ic("info"), "用户档案")
        profile_action.triggered.connect(self.show_profile_dialog)
        daniya_settings_action = chat.addAction(ic("protect"), "达妮娅设定")
        daniya_settings_action.triggered.connect(self.show_daniya_settings_dialog)
        settings_center_action = chat.addAction(ic("chip"), "设置中心")
        settings_center_action.triggered.connect(self.controller.open_settings_center)
        story_action = chat.addAction(ic("protect"), "剧情")
        story_action.triggered.connect(self.show_story_dialog)

        companion = menu.addMenu(ic("protect"), "陪伴")
        note_action = companion.addAction(ic("save"), "记一笔")
        note_action.triggered.connect(self.show_note_dialog)
        reminder_action = companion.addAction(ic("refresh"), "日程提醒")
        reminder_action.triggered.connect(self.show_reminder_dialog)

        games = companion.addMenu(ic("chip"), "小游戏")
        rps = games.addMenu(ic("protect"), "猜拳")
        for choice in ("石头", "剪刀", "布"):
            action = rps.addAction(choice)
            action.triggered.connect(lambda checked=False, value=choice: self.controller.play_rps(value))
        dice_action = games.addAction(ic("download"), "掷骰子")
        dice_action.triggered.connect(self.controller.roll_dice)
        random_action = games.addAction(ic("info"), "随机数 1-100")
        random_action.triggered.connect(self.controller.random_100)

        bookmarks = companion.addMenu(ic("cloud"), "传送门")
        for item in self.controller.bookmark_manager.records():
            action = bookmarks.addAction(item["name"])
            action.triggered.connect(lambda checked=False, url=item["url"]: self.controller.open_bookmark(url))

        system = menu.addMenu(ic("host"), "系统")
        help_action = system.addAction(ic("info"), "帮助")
        help_action.triggered.connect(self.show_help_dialog)
        exit_action = system.addAction(ic("settings"), "退出")
        exit_action.triggered.connect(self.controller.quit)

        return menu

    def _add_action_module_menu(self, parent: QMenu) -> None:
        module_menu = parent.addMenu(ic("chip"), "动作模组")
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

    # ── 剧情阅读：章节从角色包 story.yaml 加载。
    _STORY_CHAPTERS: list[tuple[int, str, str, str, str | None]] = [
        (0, "剧情未配置", "当前角色包没有可用的 story.yaml。", "", None),
    ]

    def _story_yaml_path(self) -> Path:
        pack = getattr(getattr(self.controller, "daniya_adapter", None), "character_pack", None)
        root = getattr(pack, "root", None)
        if root:
            return Path(root) / "story.yaml"
        return resource_path("characters", "daniya", "story.yaml")

    def _load_story_chapters(self) -> list[tuple[int, str, str, str, str | None]]:
        path = self._story_yaml_path()
        if path.exists():
            try:
                loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                chapters = []
                for index, item in enumerate(loaded.get("chapters", [])):
                    if not isinstance(item, dict):
                        continue
                    body = str(item.get("body") or "").strip()
                    if not body:
                        continue
                    action = item.get("action")
                    chapters.append(
                        (
                            int(item.get("id", index)),
                            str(item.get("title") or f"第 {index + 1} 章"),
                            body,
                            str(item.get("prompt") or ""),
                            str(action) if action else None,
                        )
                    )
                if chapters:
                    return chapters
            except (OSError, ValueError, TypeError, yaml.YAMLError):
                pass
        return self._STORY_CHAPTERS

    def show_story_dialog(self) -> None:
        """剧情阅读：用户逐章阅读达妮娅的完整过去。"""
        dialog = QDialog(self.window)
        dialog.setWindowTitle("剧情 — 达妮娅的完整故事")
        dialog.resize(650, 530)
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
        layout = QVBoxLayout(dialog)

        # 进度条
        progress = QLabel()
        progress.setStyleSheet("color: #6c757d; font-size: 11px; margin-bottom: 4px;")
        layout.addWidget(progress)

        # 标题
        title_label = QLabel()
        title_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #1a1a2e; margin-bottom: 6px;")
        title_label.setWordWrap(True)
        layout.addWidget(title_label)

        # 内容
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        narrative = QLabel()
        narrative.setWordWrap(True)
        narrative.setStyleSheet(
            "font-size: 13px; color: #2d3436; line-height: 1.6; "
            "background: #fafbfc; border: 1px solid #e1e4e8; border-radius: 8px; padding: 16px;"
        )
        content_layout.addWidget(narrative)

        # 发给达妮娅的提问区
        question_frame = QWidget()
        question_frame.setStyleSheet(
            "background: #fff3cd; border: 1px solid #ffeeba; border-radius: 6px; padding: 10px; margin-top: 8px;"
        )
        qf_layout = QHBoxLayout(question_frame); qf_layout.setContentsMargins(10, 8, 10, 8)

        question_label = QLabel("发给达妮娅：")
        question_label.setStyleSheet("font-size: 12px; color: #856404; font-weight: bold;")
        question_text = QLabel()
        question_text.setWordWrap(True)
        question_text.setStyleSheet("font-size: 12px; color: #856404;")
        qf_layout.addWidget(question_label)
        qf_layout.addWidget(question_text, 1)
        content_layout.addWidget(question_frame)

        content_layout.addStretch(1)
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        # 按钮行
        btn_row = QHBoxLayout()
        prev_btn = QPushButton("◀ 上一章")
        prev_btn.setStyleSheet("font-size: 12px; padding: 6px 14px;")
        next_btn = QPushButton("下一章 ▶")
        next_btn.setStyleSheet("font-size: 12px; padding: 6px 14px; font-weight: bold;")
        send_btn = QPushButton("把这句话发给达妮娅")
        send_btn.setStyleSheet("font-size: 12px; padding: 6px 14px; color: #0366d6; font-weight: bold;")
        close_btn = QPushButton("关闭")
        btn_row.addWidget(prev_btn)
        btn_row.addWidget(next_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(send_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        # 状态
        chapters = self._load_story_chapters()
        total = len(chapters)
        idx = [0]  # mutable box

        def _show_chapter():
            i = idx[0]
            num, title, body, talk, _ = chapters[i]
            progress.setText(f"剧情进度：{i + 1} / {total}")
            title_label.setText(title)
            narrative.setText(body)
            question_text.setText(f"「 {talk} 」")

            # button states
            prev_btn.setEnabled(i > 0)
            is_last = i >= total - 1
            next_btn.setText("已完成" if is_last else "下一章 ▶")
            next_btn.setEnabled(not is_last)
            send_btn.setVisible(bool(talk))
            if not talk:
                question_frame.setVisible(False)
            else:
                question_frame.setVisible(True)

        def _go_next():
            if idx[0] < total - 1:
                idx[0] += 1
                _show_chapter()

        def _go_prev():
            if idx[0] > 0:
                idx[0] -= 1
                _show_chapter()

        def _do_send():
            _, _, _, talk, _ = chapters[idx[0]]
            if talk:
                self.controller.send_message(talk)
        def _do_send_and_next():
            _do_send()
            if idx[0] < total - 1:
                idx[0] += 1
                _show_chapter()

        next_btn.clicked.connect(_go_next)
        prev_btn.clicked.connect(_go_prev)
        send_btn.clicked.connect(_do_send_and_next)
        close_btn.clicked.connect(dialog.accept)

        _show_chapter()
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
        self.setWindowFlags(self.windowFlags() | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint)
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
