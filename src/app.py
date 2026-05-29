from __future__ import annotations

import sys

from PySide6.QtCore import QObject, QThread, QTimer, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

from .affinity_manager import AffinityManager
from .asset_manager import AssetManager
from .bookmark_manager import BookmarkManager
from .chat_client import ChatClient
from .config_manager import ConfigManager
from .daniya_engine_adapter import DaniyaEngineAdapter  # [CHANGE-001] v0.415 引擎接入
from .day_night_manager import DayNightManager
from .history_manager import HistoryManager
from .idle_manager import IdleManager
from .menu_manager import MenuManager
from .mini_games import MiniGames
from .notes_manager import NotesManager
from .pet_window import PetWindow
from .profile_manager import ProfileManager
from .reminder_manager import ReminderManager
from .settings_window import SettingsWindow
from .time_event_manager import TimeEventManager


class ChatWorker(QThread):
    """后台线程：通过 DaniyaEngineAdapter 处理用户消息，避免阻塞 GUI。

    [CHANGE-002] 原始版本直接调用 chat_client.reply()，现改为走完整引擎管线。
    还原方法：恢复 reply_ready = Signal(str, str)，__init__ 接收 ChatClient，
    run() 调用 self.chat_client.reply(self.user_text)。
    """
    reply_ready = Signal(str, str)  # (response_text, source)

    def __init__(self, adapter: DaniyaEngineAdapter, user_text: str) -> None:
        super().__init__()
        self.adapter = adapter
        self.user_text = user_text
        # [LEGACY] 原签名: def __init__(self, chat_client: ChatClient, user_text: str)

    def run(self) -> None:
        try:
            result = self.adapter.handle_user_text(self.user_text)
            self.reply_ready.emit(result.response, result.source)
        except Exception as exc:
            # 引擎异常时 fallback 到安全回复，不让线程崩溃
            print(f"[Daniya] Engine error in ChatWorker: {exc.__class__.__name__}: {exc}")
            self.reply_ready.emit("……达妮娅刚刚走神了。", "engine_error")
        # [LEGACY] 原逻辑: reply, source = self.chat_client.reply(self.user_text)
        #                   self.reply_ready.emit(reply, source)


class PhysicalEventWorker(QThread):
    """后台线程：处理物理事件的引擎调用，避免阻塞 GUI。

    [CHANGE-005] 物理事件（点击/拖拽/提醒）涉及文件 I/O
    (relationship_state.json 读写)，必须在后台执行。
    """

    def __init__(self, adapter: DaniyaEngineAdapter, event_name: str) -> None:
        super().__init__()
        self.adapter = adapter
        self.event_name = event_name

    def run(self) -> None:
        try:
            self.adapter.handle_physical_event(self.event_name)
        except Exception as exc:
            print(f"[Daniya] Engine physical event error ({self.event_name}): {exc}")


class AppController(QObject):
    def __init__(self, qapp: QApplication) -> None:
        super().__init__()
        self.qapp = qapp
        self.config_manager = ConfigManager()
        self.app_config = self.config_manager.load_app_config()
        self.config_manager.save_app_config(self.app_config)

        self.history_manager = HistoryManager(self.config_manager)
        self.profile_manager = ProfileManager(self.config_manager)
        self.affinity_manager = AffinityManager(
            self.config_manager,
            int(self.app_config.get("affinity", {}).get("click_cooldown_seconds", 5)),
        )
        self.asset_manager = AssetManager(self.app_config)
        self.chat_client = ChatClient(self.config_manager, self.history_manager, self.profile_manager)
        self.notes_manager = NotesManager(self.config_manager)
        self.reminder_manager = ReminderManager(self.config_manager)
        self.time_event_manager = TimeEventManager(self.app_config)
        self.day_night_manager = DayNightManager(self.app_config)
        self.mini_games = MiniGames()
        self.bookmark_manager = BookmarkManager(self.config_manager)

        # [CHANGE-001] v0.415 引擎适配器初始化
        # 将 chat_client 作为 model_client 传入，适配器内部通过 _wrap_model_client
        # 自动包装其 .reply() 方法为 DialogueEngine 所需的接口。
        # animation_manager 和 state_manager 在 PetWindow 创建后再绑定。
        self.daniya_adapter = DaniyaEngineAdapter(
            model_client=self.chat_client,
        )

        self.window = PetWindow(self.asset_manager, self.app_config)
        self.idle_manager = IdleManager(self.app_config, self.window.can_show_idle_message)
        self.menu_manager = MenuManager(self.window, self)
        self.window.set_context_menu(self.menu_manager.create_menu())

        # [CHANGE-001] 延迟绑定适配器的 animation_manager（PetWindow 必须先创建）
        self.daniya_adapter.animation_manager = self.window.animation_manager
        self.daniya_adapter.state_manager = self.window

        self.window.message_submitted.connect(self.send_message)
        self.window.pet_clicked.connect(self.on_pet_clicked)
        self.window.position_changed.connect(self.save_window_position)
        self.window.activity_detected.connect(self.idle_manager.mark_activity)
        self.reminder_manager.reminder_due.connect(self.on_reminder_due)
        self.time_event_manager.hourly_chime.connect(self.speak_remind)
        self.idle_manager.idle_message.connect(self.speak_happy)
        self.window.update_affinity(self.affinity_manager.badge())
        self.worker: ChatWorker | None = None
        self.reminder_boxes: list[QMessageBox] = []
        self.settings_window: SettingsWindow | None = None
        # [CHANGE-005] 物理事件后台线程引用 + 拖拽防抖定时器
        self._phys_workers: list[PhysicalEventWorker] = []
        self._drag_debounce = QTimer(self)
        self._drag_debounce.setSingleShot(True)
        self._drag_debounce.setInterval(500)  # 500ms 防抖
        self._drag_debounce.timeout.connect(self._fire_drag_event)

    def show(self) -> None:
        self.window.show_at_config_position()
        self.config_manager.save_app_config(self.app_config)

    def send_message(self, user_text: str) -> None:
        self.idle_manager.mark_activity()
        if self.worker is not None and self.worker.isRunning():
            self.window.speak("等我把上一句话想完哦。")
            return
        self.window.set_input_enabled(False)
        self.window.show_message("达妮娅正在想...")
        # [CHANGE-002] 使用适配器代替直连 chat_client
        self.worker = ChatWorker(self.daniya_adapter, user_text)
        # [LEGACY] 原: self.worker = ChatWorker(self.chat_client, user_text)
        self.worker.reply_ready.connect(lambda reply, source: self._handle_reply(user_text, reply, source))
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _handle_reply(self, user_text: str, reply: str, source: str) -> None:
        print(f"[Daniya] chat saved source={source}")
        self.history_manager.append(user_text, reply, source)
        self.affinity_manager.add_chat()
        self.window.update_affinity(self.affinity_manager.badge())
        self.window.set_input_enabled(True)
        self.window.speak(reply)
        self.worker = None

    def on_pet_clicked(self) -> None:
        self.idle_manager.mark_activity()
        if self.affinity_manager.add_click():
            self.window.update_affinity(self.affinity_manager.badge())
        if self.day_night_manager.is_night():
            self.window.animation_manager.trigger_sleeping()
        else:
            self.window.animation_manager.trigger_clicked()
        self.window.speak(self.day_night_manager.click_line())
        # [CHANGE-003+005] 物理点击事件流入引擎（后台线程，不阻塞 GUI）
        self._fire_physical_event("user_click")

    def save_window_position(self, x: int, y: int) -> None:
        self.app_config.setdefault("window", {})["start_x"] = x
        self.app_config.setdefault("window", {})["start_y"] = y
        self.config_manager.save_app_config(self.app_config)
        # [CHANGE-003+005] 拖拽事件防抖：500ms 内不重复触发，拖拽结束才执行一次
        self._drag_debounce.start()

    def save_pet_height(self, height: int) -> None:
        actual = self.window.set_pet_height(height)
        self.app_config.setdefault("pet", {})["pet_height"] = actual
        self.app_config.setdefault("pet", {})["target_height"] = actual
        self.config_manager.save_app_config(self.app_config)
        self.window.set_context_menu(self.menu_manager.create_menu())

    def set_action_module(self, module: str) -> None:
        active = self.window.animation_manager.set_action_module(module)
        self.app_config.setdefault("pet", {})["active_action_module"] = active
        self.config_manager.save_app_config(self.app_config)
        self.window.set_context_menu(self.menu_manager.create_menu())

    def set_pet_feature(self, key: str, enabled: bool) -> None:
        if key not in {"hover_animation_enabled", "edge_peek_enabled", "click_to_call_enabled"}:
            return
        self.app_config.setdefault("pet", {})[key] = bool(enabled)
        self.config_manager.save_app_config(self.app_config)
        self.window.set_context_menu(self.menu_manager.create_menu())

    def set_drag_module_enabled(self, enabled: bool) -> None:
        modules = self.app_config.setdefault("pet", {}).setdefault("enabled_action_modules", {})
        if isinstance(modules, dict):
            modules["E_QQ_pet_drag_system"] = bool(enabled)
        self.config_manager.save_app_config(self.app_config)
        self.window.set_context_menu(self.menu_manager.create_menu())

    def save_system_prompt(self, text: str) -> None:
        self.config_manager.save_system_prompt(text)
        self.history_manager.clear_short_context()
        self.chat_client.reload()
        self.window.speak("人设已经更新啦。")

    def save_profile(self, profile: dict[str, str]) -> None:
        self.profile_manager.save(profile)
        self.chat_client.reload()
        self.window.speak("御主档案保存好了。")

    def add_note(self, text: str) -> None:
        self.idle_manager.mark_activity()
        if self.notes_manager.append(text):
            self.window.speak("记好啦，御主～")
        else:
            self.window.speak("空白的东西我就不记啦。")

    def add_reminder(self, time_text: str, text: str) -> tuple[bool, str]:
        self.idle_manager.mark_activity()
        ok, message = self.reminder_manager.add(time_text, text)
        self.window.speak(message)
        return ok, message

    def on_reminder_due(self, reminder_id: str, text: str) -> None:
        self.window.set_always_on_top(True)
        self.window.animation_manager.trigger_remind()
        self.window.speak(f"提醒时间到啦：{text}")
        # [CHANGE-003+005] 提醒到期事件流入引擎（后台线程）
        self._fire_physical_event("reminder_due")
        box = QMessageBox(self.window)
        box.setWindowTitle("达妮娅提醒")
        box.setText(f"提醒时间到啦：{text}")
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        ok_button = box.button(QMessageBox.StandardButton.Ok)
        if ok_button is not None:
            ok_button.setText("知道了")
        box.finished.connect(lambda _result, rid=reminder_id, b=box: self._finish_reminder(rid, b))
        self.reminder_boxes.append(box)
        box.show()

    def _finish_reminder(self, reminder_id: str, box: QMessageBox) -> None:
        self.reminder_manager.mark_done(reminder_id)
        if box in self.reminder_boxes:
            self.reminder_boxes.remove(box)

    def speak_remind(self, text: str) -> None:
        if not self.window.can_show_idle_message():
            return
        self.window.animation_manager.trigger_remind()
        self.window.speak(text)

    def speak_happy(self, text: str) -> None:
        self.window.animation_manager.trigger_happy()
        self.window.speak(text)

    def play_rps(self, choice: str) -> None:
        self.idle_manager.mark_activity()
        message, user_wins = self.mini_games.play_rps(choice)
        if user_wins:
            self.affinity_manager.add_value(1)
            self.window.update_affinity(self.affinity_manager.badge())
        self.window.speak(message)

    def roll_dice(self) -> None:
        self.idle_manager.mark_activity()
        self.window.speak(self.mini_games.roll_dice())

    def random_100(self) -> None:
        self.idle_manager.mark_activity()
        self.window.speak(self.mini_games.random_100())

    def open_bookmark(self, url: str) -> None:
        self.idle_manager.mark_activity()
        ok, message = self.bookmark_manager.open(url)
        if ok:
            self.window.animation_manager.trigger_happy()
        self.window.speak(message)

    def open_settings_center(self) -> None:
        try:
            if self.settings_window is not None and self.settings_window.isVisible():
                self.settings_window.raise_()
                self.settings_window.activateWindow()
                return
            self.settings_window = SettingsWindow(self, self.window)
            self.settings_window.finished.connect(lambda _result: setattr(self, "settings_window", None))
            self.settings_window.show()
        except Exception as exc:
            QMessageBox.warning(self.window, "设置中心", f"设置中心打开失败：{exc.__class__.__name__}")

    def quit(self) -> None:
        self.qapp.quit()


    # -- [CHANGE-005] 物理事件后台调度 --

    def _fire_physical_event(self, event_name: str) -> None:
        """在后台线程中触发物理事件，避免阻塞 GUI 主线程。"""
        w = PhysicalEventWorker(self.daniya_adapter, event_name)
        self._phys_workers.append(w)
        w.finished.connect(lambda: self._cleanup_phys_worker(w))
        w.start()

    def _fire_drag_event(self) -> None:
        """拖拽防抖定时器到期后触发一次拖拽事件。"""
        self._fire_physical_event("user_drag")

    def _cleanup_phys_worker(self, w: PhysicalEventWorker) -> None:
        if w in self._phys_workers:
            self._phys_workers.remove(w)
        w.deleteLater()

def run() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    controller = AppController(app)
    controller.show()
    sys.exit(app.exec())
