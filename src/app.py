from __future__ import annotations

import sys
import traceback

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

from .affinity_manager import AffinityManager
from .asset_manager import AssetManager
from .bookmark_manager import BookmarkManager
from .chat_client import ChatClient
from .config_manager import ConfigManager
from .daniya_engine_adapter import DaniyaEngineAdapter, DaniyaEngineAdapterConfig  # [CHANGE-001] v0.415 引擎接入
from .day_night_manager import DayNightManager
from .history_manager import HistoryManager
from .idle_manager import IdleManager
from .menu_manager import MenuManager
from .mini_games import MiniGames
from .notes_manager import NotesManager
from .pet_window import PetWindow
from .profile_manager import ProfileManager
from .reminder_manager import ReminderManager
from .natural_reminder_service import NaturalReminderService
from .settings_window import SettingsWindow
from .time_event_manager import TimeEventManager


class ThreadSafeAnimationManager(QObject):
    """
    [CHANGE-005-FIX] 线程安全的动画管理器包装器。
    将后台线程（ChatWorker / PhysicalEventWorker）中的动画调用
    通过 Signal 安全地转发到主 GUI 线程，避免 Qt 的线程安全冲突导致的界面冻结。
    """
    state_requested = Signal(str)
    click_requested = Signal()
    happy_requested = Signal()
    remind_requested = Signal()
    sleep_requested = Signal()

    def __init__(self, real_manager: Any) -> None:
        super().__init__()
        self.real_manager = real_manager
        self.state_requested.connect(self.real_manager.set_state)
        self.click_requested.connect(self.real_manager.trigger_clicked)
        self.happy_requested.connect(self.real_manager.trigger_happy)
        self.remind_requested.connect(self.real_manager.trigger_remind)
        self.sleep_requested.connect(self.real_manager.trigger_sleeping)

    def set_state(self, action: str) -> None:
        self.state_requested.emit(action)

    def trigger_clicked(self) -> None:
        self.click_requested.emit()

    def trigger_happy(self) -> None:
        self.happy_requested.emit()

    def trigger_remind(self) -> None:
        self.remind_requested.emit()

    def trigger_sleeping(self) -> None:
        self.sleep_requested.emit()


class ChatWorker(QThread):
    """后台线程：通过 DaniyaEngineAdapter 处理用户消息，避免阻塞 GUI。

    [CHANGE-002] 原始版本直接调用 chat_client.reply()，现改为走完整引擎管线。
    还原方法：恢复 reply_ready = Signal(str, str)，__init__ 接收 ChatClient，
    run() 调用 self.chat_client.reply(self.user_text)。
    """
    reply_ready = Signal(str, str)  # (response_text, source)

    def __init__(self, adapter: DaniyaEngineAdapter, user_text: str, context: dict[str, Any] | None = None) -> None:
        super().__init__()
        self.adapter = adapter
        self.user_text = user_text
        self.context = context or {}
        # [LEGACY] 原签名: def __init__(self, chat_client: ChatClient, user_text: str)

    def run(self) -> None:
        try:
            result = self.adapter.handle_user_text(self.user_text, context=self.context)
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
        self.chat_client = ChatClient(self.config_manager, self.history_manager, self.profile_manager)
        self.notes_manager = NotesManager(self.config_manager)
        self.reminder_manager = ReminderManager(self.config_manager)
        self.natural_reminder_service = NaturalReminderService(self.reminder_manager)
        self.pending_reminder_result = None
        self.time_event_manager = TimeEventManager(self.app_config)
        self.day_night_manager = DayNightManager(self.app_config)
        self.mini_games = MiniGames()
        self.bookmark_manager = BookmarkManager(self.config_manager)

        # [CHANGE-001] v0.415 引擎适配器初始化
        # 将 chat_client 作为 model_client 传入，适配器内部通过 _wrap_model_client
        # 自动包装其 .reply() 方法为 DialogueEngine 所需的接口。
        # animation_manager 和 state_manager 在 PetWindow 创建后再绑定。
        char_id = self.app_config.get("current_character", "daniya")
        self.daniya_adapter = DaniyaEngineAdapter(
            model_client=self.chat_client,
            config=DaniyaEngineAdapterConfig(character_id=char_id)
        )
        resolved_char_id = self.daniya_adapter.character_pack.character_id
        self.asset_manager = AssetManager(self.app_config, resolved_char_id)

        self.window = PetWindow(self.asset_manager, self.app_config)
        # Inject behavior engine checkers
        self.window.behavior_engine.idle_behavior.is_allowed = self.is_idle_behavior_allowed
        self.window.behavior_engine.idle_behavior.is_night = self.is_night_behavior

        self.idle_manager = IdleManager(self.app_config, self.window.can_show_idle_message)
        self.menu_manager = MenuManager(self.window, self)
        self.window.set_context_menu(self.menu_manager.create_menu())
        self.window.set_menu_refresh_callback(lambda: self.window.set_context_menu(self.menu_manager.create_menu()))

        # [CHANGE-001] 延迟绑定适配器的 animation_manager（PetWindow 必须先创建）
        # [CHANGE-005-FIX] 使用线程安全的动画管理器包装，防止后台线程崩溃 GUI
        self.thread_safe_anim_manager = ThreadSafeAnimationManager(self.window.animation_manager)
        self.daniya_adapter.animation_manager = self.thread_safe_anim_manager
        self.daniya_adapter.state_manager = self.window

        self.window.message_submitted.connect(self.send_message)
        self.window.pet_clicked.connect(self.on_pet_clicked)
        self.window.position_changed.connect(self.save_window_position)
        self.window.drag_completed.connect(self.on_drag_completed)
        self.window.activity_detected.connect(self.idle_manager.mark_activity)
        self.window.activity_detected.connect(self.window.behavior_engine.mark_activity)
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

    def send_message(self, user_text: str, base_time: datetime | None = None) -> None:
        self.idle_manager.mark_activity()
        if self.worker is not None and self.worker.isRunning():
            self.window.speak("……等一下，我还在想刚才那句呢。")
            return

        # 1. Process pending reminder confirmation
        if not self.app_config.get("natural_reminder_enabled", True):
            self.pending_reminder_result = None
        else:
            clean_text = user_text.strip().lower()
            confirm_keywords = {"确认", "确定", "好", "对", "没问题", "ok", "yes", "行", "确定是"}
            cancel_keywords = {"取消", "不", "不要", "算了", "no", "cancel"}

            if self.pending_reminder_result is not None:
                if clean_text in confirm_keywords:
                    result = self.pending_reminder_result
                    self.pending_reminder_result = None
                    if result.scheduled_at:
                        time_str = result.scheduled_at.strftime("%Y-%m-%d %H:%M")
                        success, msg = self.reminder_manager.add(time_str, result.reminder_text)
                        if success:
                            self.window.speak(f"……记下了。会在【{time_str}】提醒你【{result.reminder_text}】。到时候别装作看不见。")
                        else:
                            self.window.speak(msg)
                    else:
                        self.window.speak("……时间还是不明确哦。什么时候叫你？比如说“十分钟后”。")
                        self.pending_reminder_result = result
                    return
                elif clean_text in cancel_keywords:
                    self.pending_reminder_result = None
                    self.window.speak("……好吧，那我就不记下了。")
                    return
                else:
                    # Try parsing as a new reminder to see if user provides the missing time
                    from .natural_reminder_parser import parse_natural_reminder
                    trigger_words = {"提醒我", "叫我", "记得", "提醒", "到时叫"}
                    temp_text = user_text if any(w in user_text for w in trigger_words) else f"提醒我{user_text}"
                    new_res = parse_natural_reminder(temp_text, base_time=base_time)
                    if new_res.ok and new_res.scheduled_at:
                        has_new_trigger = any(w in user_text for w in trigger_words)
                        r_text = self.pending_reminder_result.reminder_text if not has_new_trigger else (new_res.reminder_text or self.pending_reminder_result.reminder_text)
                        new_res.reminder_text = r_text

                        if not new_res.need_confirm:
                            self.pending_reminder_result = None
                            time_str = new_res.scheduled_at.strftime("%Y-%m-%d %H:%M")
                            success, msg = self.reminder_manager.add(time_str, r_text)
                            if success:
                                self.window.speak(f"……记下了。会在【{time_str}】提醒你【{r_text}】。到时候别装作看不见。")
                            else:
                                self.window.speak(msg)
                            return
                        else:
                            self.pending_reminder_result = new_res
                            time_str = new_res.scheduled_at.strftime("%Y-%m-%d %H:%M")
                            self.window.speak(f"……时间还是有点模糊。确定要在【{time_str}】提醒你【{r_text}】吗？确认的话跟我说“确认”哦。")
                            return
                    else:
                        # Cancel pending reminder and fall through to normal chat
                        self.pending_reminder_result = None

        # 2. Check for new natural reminder
        if self.app_config.get("natural_reminder_enabled", True):
            is_rem, reply, parse_res = self.natural_reminder_service.process_chat_message(user_text, base_time=base_time)
            if is_rem:
                if parse_res and parse_res.need_confirm:
                    self.pending_reminder_result = parse_res
                self.window.speak(reply)
                return

        # 3. Normal LLM Chat
        self.window.set_input_enabled(False)
        self.window.set_thinking_state(True)
        # [CHANGE-002] 使用适配器代替直连 chat_client
        recent_messages = self.history_manager.recent_messages(self.chat_client.context_limit)
        context = {"recent_messages": recent_messages}
        self.worker = ChatWorker(self.daniya_adapter, user_text, context=context)
        # [LEGACY] 原: self.worker = ChatWorker(self.chat_client, user_text)
        self.worker.reply_ready.connect(lambda reply, source: self._handle_reply(user_text, reply, source))
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _handle_reply(self, user_text: str, reply: str, source: str) -> None:
        print(f"[Daniya] chat saved source={source}")
        self.history_manager.append(user_text, reply, source)
        upgraded = self.affinity_manager.add_chat()
        self.window.update_affinity(self.affinity_manager.badge())
        self.window.set_input_enabled(True)
        self.window.set_thinking_state(False)
        self.window.speak(reply)
        self.worker = None
        if upgraded:
            QTimer.singleShot(2500, lambda: self._check_affinity_upgrade(upgraded))

    def is_idle_behavior_allowed(self) -> bool:
        if self.worker is not None and self.worker.isRunning():
            return False
        if self.window.typewriter.is_typing:
            return False
        if self.window.input_box.isVisible() and self.window.input_box.hasFocus() and self.window.input_box.text().strip():
            return False
        if self.settings_window is not None and self.settings_window.isVisible():
            return False
        if self.reminder_boxes:
            return False
        return True

    def is_night_behavior(self) -> bool:
        return self.day_night_manager.is_night()

    def on_pet_clicked(self) -> None:
        self.idle_manager.mark_activity()
        success, upgraded = self.affinity_manager.add_click()
        if success:
            self.window.update_affinity(self.affinity_manager.badge())
        if self.day_night_manager.is_night():
            self.window.animation_manager.trigger_sleeping()
        else:
            self.window.animation_manager.trigger_clicked()
        self.window.speak(self.day_night_manager.click_line())
        # [CHANGE-003+005] 物理点击事件流入引擎（后台线程，不阻塞 GUI）
        self._fire_physical_event("user_click")
        if upgraded:
            QTimer.singleShot(2000, lambda: self._check_affinity_upgrade(upgraded))

    def save_window_position(self, x: int, y: int) -> None:
        self.window.behavior_engine.snap_controller.save_window_state(
            x,
            y,
            self.window.behavior_engine.snap_controller.get_current_snap_state(),
        )

    def on_drag_completed(self, x: int, y: int) -> None:
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

    def reload_character(self, character_id: str | None = None) -> bool:
        from .character_pack_editor import CharacterPackEditor
        if character_id is not None:
            self.app_config["current_character"] = character_id
            self.config_manager.save_app_config(self.app_config)
        else:
            character_id = self.app_config.get("current_character", "daniya")

        # 1. Re-initialize DaniyaEngineAdapter
        self.daniya_adapter = DaniyaEngineAdapter(
            model_client=self.chat_client,
            config=DaniyaEngineAdapterConfig(character_id=character_id)
        )
        resolved_char_id = self.daniya_adapter.character_pack.character_id

        # 2. Re-initialize AssetManager
        self.asset_manager = AssetManager(self.app_config, resolved_char_id)

        # 3. Bind animation and state managers
        self.daniya_adapter.animation_manager = self.thread_safe_anim_manager
        self.daniya_adapter.state_manager = self.window

        # 4. Update window references and reload manifest/assets
        self.window.asset_manager = self.asset_manager
        self.window.animation_manager.asset_manager = self.asset_manager
        self.window.animation_manager.reload_manifest()
        self.window.animation_manager.refresh()

        # Reload behavior config and checkers
        self.window.behavior_engine.reload_config(self.app_config)
        self.window.behavior_engine.idle_behavior.is_allowed = self.is_idle_behavior_allowed
        self.window.behavior_engine.idle_behavior.is_night = self.is_night_behavior

        # If settings window is open, update its references as well
        if self.settings_window is not None and self.settings_window.isVisible():
            self.settings_window.character_editor = CharacterPackEditor(character_id=resolved_char_id)
            self.settings_window._refresh_char_info()
            self.settings_window._refresh_character_status()
            self.settings_window._refresh_action_status()
            self.settings_window._load_pack_file(self.settings_window.pack_file_combo.currentText())

        print(f"[Daniya] Hot reloaded character ID: {resolved_char_id} (requested: {character_id})")
        return True

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
        self.window.speak("……人设更新了。别总是变来变去的。")

    def save_profile(self, profile: dict[str, str]) -> None:
        self.profile_manager.save(profile)
        self.chat_client.reload()
        self.window.speak("……你的事情，我稍微记了一下。")

    def add_note(self, text: str) -> None:
        self.idle_manager.mark_activity()
        if self.notes_manager.append(text):
            self.window.speak("……记下了。别丢三落四的。")
        else:
            self.window.speak("……空白的。你是在耍我吗？")

    def add_reminder(self, time_text: str, text: str) -> tuple[bool, str]:
        self.idle_manager.mark_activity()
        ok, message = self.reminder_manager.add(time_text, text)
        self.window.speak(message)
        return ok, message

    def on_reminder_due(self, reminder_id: str, text: str) -> None:
        self.window.set_always_on_top(True)
        self.window.animation_manager.trigger_remind()
        self.window.speak(f"……喂，时间到了：{text}。去处理一下。")
        # [CHANGE-003+005] 提醒到期事件流入引擎（后台线程）
        self._fire_physical_event("reminder_due")
        box = QMessageBox(self.window)
        box.setWindowTitle("达妮娅的唠叨")
        box.setText(f"……喂，时间到了：\n【{text}】\n去处理一下。")
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
        upgraded = self.affinity_manager.add_value(1)
        self.window.update_affinity(self.affinity_manager.badge())
        if upgraded:
            QTimer.singleShot(1000, lambda: self._check_affinity_upgrade(upgraded))

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
        upgraded = None
        if user_wins:
            upgraded = self.affinity_manager.add_value(1)
            self.window.update_affinity(self.affinity_manager.badge())
        self.window.speak(message)
        if upgraded:
            QTimer.singleShot(2500, lambda: self._check_affinity_upgrade(upgraded))

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
            if self.settings_window is not None:
                if self.settings_window.isMinimized():
                    self.settings_window.showNormal()
                else:
                    self.settings_window.show()
                self.settings_window.setWindowState(
                    (self.settings_window.windowState() & ~Qt.WindowState.WindowMinimized)
                    | Qt.WindowState.WindowActive
                )
                self.settings_window.raise_()
                self.settings_window.activateWindow()
                return
            self.settings_window = SettingsWindow(self, None)
            self.settings_window.finished.connect(lambda _result: setattr(self, "settings_window", None))
            self.settings_window.show()
            self.settings_window.raise_()
            self.settings_window.activateWindow()
        except Exception as exc:
            self.settings_window = None
            traceback.print_exc()
            detail = f"{exc.__class__.__name__}: {exc}" if str(exc) else exc.__class__.__name__
            QMessageBox.warning(
                self.window,
                "\u8bbe\u7f6e\u4e2d\u5fc3",
                f"\u8bbe\u7f6e\u4e2d\u5fc3\u6253\u5f00\u5931\u8d25\uff1a{detail}",
            )
            return

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

    def _check_affinity_upgrade(self, upgrade_level: str | None) -> None:
        if not upgrade_level:
            return
        lines = {
            "熟悉": "……好像稍微习惯你在旁边了。关系变成「熟悉」了。",
            "亲近": "……允许你再离我近一点点。只是……一点点哦。关系变成「亲近」了。",
            "依赖": "……真是的。以后，别指望我会放你走。关系变成「依赖」了。"
        }
        line = lines.get(upgrade_level)
        if line:
            self.window.animation_manager.trigger_happy()
            self.window.speak(line)

def _configure_application_lifecycle(app: QApplication) -> None:
    app.setQuitOnLastWindowClosed(False)


def run() -> None:
    app = QApplication(sys.argv)
    _configure_application_lifecycle(app)

    app.setStyleSheet("""
        QDialog, QMainWindow {
            background-color: #f3f5f7;
        }
        QTabWidget::pane {
            border: 1px solid #e2e8f0;
            background-color: #ffffff;
            border-radius: 8px;
        }
        QTabBar::tab {
            background-color: #f8fafc;
            border: 1px solid #e2e8f0;
            padding: 8px 16px;
            margin-right: 4px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            color: #64748b;
            font-family: "Segoe UI", "Microsoft YaHei";
            font-size: 13px;
        }
        QTabBar::tab:selected {
            background-color: #ffffff;
            border-bottom-color: transparent;
            color: #0f172a;
            font-weight: bold;
        }
        QTabBar::tab:hover:!selected {
            background-color: #f1f5f9;
        }
        QGroupBox {
            border: 1px solid #cbd5e1;
            border-radius: 8px;
            margin-top: 18px;
            background-color: rgba(255, 255, 255, 0.6);
            font-family: "Segoe UI", "Microsoft YaHei";
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            left: 12px;
            padding: 0 4px;
            color: #475569;
            font-weight: bold;
        }
        QLineEdit, QTextEdit, QComboBox {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 6px 8px;
            color: #334155;
            selection-background-color: #bae6fd;
        }
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
            border: 1px solid #3b82f6;
            background-color: #ffffff;
        }
        QPushButton {
            background-color: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 6px 14px;
            color: #334155;
            font-family: "Segoe UI", "Microsoft YaHei";
        }
        QPushButton:hover {
            background-color: #f0f9ff;
            border: 1px solid #7dd3fc;
            color: #0284c7;
        }
        QPushButton:pressed {
            background-color: #e0f2fe;
        }
        QScrollArea {
            border: none;
            background-color: transparent;
        }
        QScrollBar:vertical {
            border: none;
            background-color: transparent;
            width: 8px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:vertical {
            background-color: #cbd5e1;
            min-height: 20px;
            border-radius: 4px;
        }
        QScrollBar::handle:vertical:hover {
            background-color: #94a3b8;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
        }
    """)

    from .setup_state_manager import SetupStateManager
    from .first_run_wizard import FirstRunWizard

    setup_manager = SetupStateManager()
    if not setup_manager.is_first_run_complete():
        wizard = FirstRunWizard(setup_manager)
        wizard.exec()
        if not setup_manager.is_first_run_complete():
            # 用户关闭了向导而没有完成设置
            sys.exit(0)

    controller = AppController(app)
    controller.show()
    sys.exit(app.exec())
