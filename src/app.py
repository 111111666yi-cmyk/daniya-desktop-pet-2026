from __future__ import annotations

import sys

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

from .affinity_manager import AffinityManager
from .asset_manager import AssetManager
from .bookmark_manager import BookmarkManager
from .chat_client import ChatClient
from .config_manager import ConfigManager
from .day_night_manager import DayNightManager
from .history_manager import HistoryManager
from .idle_manager import IdleManager
from .menu_manager import MenuManager
from .mini_games import MiniGames
from .notes_manager import NotesManager
from .pet_window import PetWindow
from .profile_manager import ProfileManager
from .reminder_manager import ReminderManager
from .time_event_manager import TimeEventManager


class ChatWorker(QThread):
    reply_ready = Signal(str, str)

    def __init__(self, chat_client: ChatClient, user_text: str) -> None:
        super().__init__()
        self.chat_client = chat_client
        self.user_text = user_text

    def run(self) -> None:
        reply, source = self.chat_client.reply(self.user_text)
        self.reply_ready.emit(reply, source)


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

        self.window = PetWindow(self.asset_manager, self.app_config)
        self.idle_manager = IdleManager(self.app_config, self.window.can_show_idle_message)
        self.menu_manager = MenuManager(self.window, self)
        self.window.set_context_menu(self.menu_manager.create_menu())

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

    def show(self) -> None:
        self.window.show_at_config_position()

    def send_message(self, user_text: str) -> None:
        self.idle_manager.mark_activity()
        if self.worker is not None and self.worker.isRunning():
            self.window.speak("等我把上一句话想完哦。")
            return
        self.window.set_input_enabled(False)
        self.window.show_message("达妮娅正在想...")
        self.worker = ChatWorker(self.chat_client, user_text)
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

    def save_window_position(self, x: int, y: int) -> None:
        self.app_config.setdefault("window", {})["start_x"] = x
        self.app_config.setdefault("window", {})["start_y"] = y
        self.config_manager.save_app_config(self.app_config)

    def save_pet_height(self, height: int) -> None:
        actual = self.window.set_pet_height(height)
        self.app_config.setdefault("pet", {})["pet_height"] = actual
        self.app_config.setdefault("pet", {})["target_height"] = actual
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

    def quit(self) -> None:
        self.qapp.quit()


def run() -> None:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    controller = AppController(app)
    controller.show()
    sys.exit(app.exec())
