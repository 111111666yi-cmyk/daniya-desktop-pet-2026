from __future__ import annotations

import logging
import socket
import sys
import traceback
import hashlib
from collections import deque
from datetime import datetime
from typing import Any, TYPE_CHECKING

from PySide6.QtCore import QObject, QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

from core.utility_copy import utility_text

from .affinity_manager import AffinityManager
from .ambient_event_theater import AmbientEventTheater
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
from .mood_manager import MoodManager
from .notes_manager import NotesManager
from .pet_window import PetWindow
from .profile_manager import ProfileManager
from .reminder_manager import ReminderManager
from .natural_reminder_service import NaturalReminderService
from .clipboard_interaction import ClipboardInteraction
from .focus_mode import FocusModeManager
from .pomodoro import PomodoroSession
from .feedback_coordinator import FeedbackCoordinator
from .growth_manager import GrowthManager
from .media_presence import MediaPresenceManager
from .observation_diary import ObservationDiary
from .system_status import SystemStatusManager
from .time_event_manager import TimeEventManager
from .startup_timing import StartupTimer
from .weather_manager import WeatherManager
from .utils import bundled_root
from core.long_term_memory import LongTermMemoryStore

if TYPE_CHECKING:
    from .settings_window import SettingsWindow


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
    def __init__(self, qapp: QApplication, startup_timer: StartupTimer | None = None) -> None:
        super().__init__()
        self.qapp = qapp
        self.startup_timer = startup_timer or StartupTimer()
        self.startup_timer.mark("QApplication created")
        self.config_manager = ConfigManager()
        self.startup_timer.mark("runtime root resolved")
        self.app_config = self.config_manager.load_app_config()
        self.startup_timer.mark("config loaded")
        self.config_manager.save_app_config(self.app_config)

        self.history_manager = HistoryManager(self.config_manager)
        self.profile_manager = ProfileManager(self.config_manager)
        self.affinity_manager = AffinityManager(
            self.config_manager,
            int(self.app_config.get("affinity", {}).get("click_cooldown_seconds", 5)),
        )
        self.chat_client = ChatClient(self.config_manager, self.history_manager, self.profile_manager)
        self.long_term_memory_store = LongTermMemoryStore()
        self.observation_diary = ObservationDiary(self.chat_client.reply)
        self.notes_manager = NotesManager(self.config_manager)
        self.reminder_manager = ReminderManager(
            self.config_manager,
            enabled=bool(self.app_config.get("reminder_enabled", True)),
        )
        self.natural_reminder_service = NaturalReminderService(self.reminder_manager)
        self.pending_reminder_result = None
        self.time_event_manager = TimeEventManager(self.app_config)
        self.day_night_manager = DayNightManager(self.app_config)
        self.mini_games = MiniGames()
        self.bookmark_manager = BookmarkManager(self.config_manager)
        self.system_status_manager = SystemStatusManager()
        self.clipboard_interaction = ClipboardInteraction(self.qapp.clipboard())
        self.focus_mode_manager = FocusModeManager()
        self.pomodoro = PomodoroSession(self.app_config.get("pomodoro", {}))
        self.mood_manager = MoodManager()
        self.startup_timer.mark("managers initialized")

        # [CHANGE-001] v0.415 引擎适配器初始化
        # 将 chat_client 作为 model_client 传入，适配器内部通过 _wrap_model_client
        # 自动包装其 .reply() 方法为 DialogueEngine 所需的接口。
        # animation_manager 和 state_manager 在 PetWindow 创建后再绑定。
        char_id = self.app_config.get("current_character", "daniya")
        self.daniya_adapter = DaniyaEngineAdapter(
            model_client=self.chat_client,
            config=DaniyaEngineAdapterConfig(character_id=char_id)
        )
        self.startup_timer.mark("character pack loaded")
        resolved_char_id = self.daniya_adapter.character_pack.character_id
        self.growth_manager = GrowthManager(
            self.config_manager,
            self.app_config,
            character_id=resolved_char_id,
        )
        environment = self.app_config.get("environment", {})
        if not isinstance(environment, dict):
            environment = {}
        self.weather_manager = WeatherManager(
            enabled=bool(environment.get("weather_enabled", False)),
            location_configured=bool(environment.get("weather_location_configured", False)),
            latitude=float(environment.get("weather_latitude", 0.0)),
            longitude=float(environment.get("weather_longitude", 0.0)),
            interval_seconds=int(environment.get("weather_interval_seconds", 1800)),
        )
        self.media_presence_manager = MediaPresenceManager(
            enabled=bool(environment.get("media_presence_enabled", False)),
            interval_seconds=int(environment.get("media_interval_seconds", 60)),
        )
        self.ambient_event_theater = AmbientEventTheater(
            resolved_char_id,
            enabled=bool(environment.get("ambient_events_enabled", False)),
            interval_seconds=int(environment.get("ambient_event_interval_seconds", 1800)),
        )
        self._last_weather_raining: bool | None = None
        self.reminder_manager.set_message_lookup(self.utility_text)
        self.system_status_manager.message_lookup = self.utility_text
        self.clipboard_interaction.message_lookup = self.utility_text
        self.asset_manager = AssetManager(self.app_config, resolved_char_id)

        self.window = PetWindow(self.asset_manager, self.app_config)
        self.startup_timer.mark("main window created")
        # Inject behavior engine checkers
        self.window.behavior_engine.idle_behavior.is_allowed = self.is_idle_behavior_allowed
        self.window.behavior_engine.idle_behavior.is_night = self.is_night_behavior
        self.window.behavior_engine.idle_behavior._mood_manager = self.mood_manager
        self.window.behavior_engine.idle_behavior._state_manager = self.window.animation_manager.state_manager
        self.window.behavior_engine.idle_behavior.set_enabled(False)
        self.window._stop_pet_feature_timers()
        self.window.edge_peek_allowed_callback = self._edge_peek_allowed

        self.idle_manager = IdleManager(self.app_config, self.window.can_show_idle_message)
        self.menu_manager = MenuManager(self.window, self)
        self.window.set_context_menu(self.menu_manager.create_menu())
        self.window.set_menu_refresh_callback(lambda: self.window.set_context_menu(self.menu_manager.create_menu()))

        # [CHANGE-001] 延迟绑定适配器的 animation_manager（PetWindow 必须先创建）
        # [CHANGE-005-FIX] 使用线程安全的动画管理器包装，防止后台线程崩溃 GUI
        self.thread_safe_anim_manager = ThreadSafeAnimationManager(self.window.animation_manager)
        self.daniya_adapter.animation_manager = self.thread_safe_anim_manager
        self.daniya_adapter.state_manager = self.thread_safe_anim_manager

        self.window.message_submitted.connect(self.send_message)
        self.window.pet_clicked.connect(self.on_pet_clicked)
        self.window.position_changed.connect(self.save_window_position)
        self.window.drag_completed.connect(self.on_drag_completed)
        self.window.activity_detected.connect(self.idle_manager.mark_activity)
        self.window.activity_detected.connect(self.window.behavior_engine.mark_activity)
        self.reminder_manager.reminder_due.connect(self.on_reminder_due)
        self.time_event_manager.hourly_chime.connect(self.speak_remind)
        self.idle_manager.idle_message.connect(self.speak_happy)
        self.system_status_manager.status_alert.connect(self._on_system_status_alert)
        self.clipboard_interaction.clipboard_alert.connect(self._on_clipboard_alert)
        self.focus_mode_manager.focus_state_changed.connect(self._on_focus_state_changed)
        self.pomodoro.distraction_detected.connect(self._on_pomodoro_distraction)
        self.pomodoro.completed.connect(self._on_pomodoro_completed)
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
        self._pending_phys_events: deque[str] = deque(maxlen=32)
        self._phys_busy = False
        self.feedback_coordinator = FeedbackCoordinator(
            show_text=self._speak_with_tts,
            trigger_action=self._trigger_feedback_action,
            return_to_idle=self.window.animation_manager.play_idle,
            is_dragging=self._is_feedback_dragging,
            is_settings_open=self._is_settings_open,
            is_user_busy=self._is_feedback_user_busy,
            is_talking=lambda: self.window.typewriter.is_typing or self.window.bubble.isVisible(),
            is_focus_suppressed=self._focus_suppresses,
        )
        self.window.behavior_engine.speak_callback = self._speak_idle_behavior
        self.window.typewriter.sequence_finished.connect(self.feedback_coordinator.complete)
        self.weather_manager.snapshot_ready.connect(self._on_weather_snapshot)
        self.media_presence_manager.presence_changed.connect(self._on_media_presence)
        self.ambient_event_theater.event_ready.connect(self._on_ambient_event)
        self._optional_services_initialized = False

    def _init_tts(self) -> None:
        from core.tts.voice_asset_manager import VoiceAssetManager
        from core.tts.tts_service import TTSService
        from core.tts.audio_player import AudioPlayer
        from core.tts.clip_pack import ClipPackVoiceService
        from core.tts.voice_mode_router import VoiceModeRouter
        tts_config = self.app_config.get("tts", {})
        self._voice_asset_manager = VoiceAssetManager()
        self._audio_player = AudioPlayer(self.window)
        self.tts_service = TTSService(self._voice_asset_manager, self._audio_player, tts_config)
        self._clip_pack_service = ClipPackVoiceService(audio_player=self._audio_player)
        self.voice_router = VoiceModeRouter(
            config=self.app_config,
            clip_pack_service=self._clip_pack_service,
            tts_service=self.tts_service,
            audio_player=self._audio_player,
        )

    def _tts_play(self, text: str, interaction: bool = False) -> None:
        if not hasattr(self, "voice_router"):
            return
        mode = self.app_config.get("voice", {}).get("mode", "off")
        if mode == "off":
            return
        if interaction:
            import random
            prob = self.app_config.get("tts", {}).get("interaction_probability", 0.25)
            if random.random() > prob:
                return
        self.voice_router.play_text(text)

    def _voice_play_event(self, event_type: str, text: str | None = None) -> None:
        if hasattr(self, "voice_router"):
            self.voice_router.play_pet_event(event_type, text)

    def show(self) -> None:
        self.window.show_at_config_position()
        self.window.behavior_engine.idle_behavior.set_enabled(
            bool(self.app_config.get("idle_behavior_enabled", False))
        )
        self.window.sync_feature_timers()
        self.config_manager.save_app_config(self.app_config)
        self.startup_timer.mark("first show")
        QTimer.singleShot(0, self._initialize_optional_services)

    def _initialize_optional_services(self) -> None:
        if self._optional_services_initialized:
            return
        self.apply_integrated_feature_config()
        self._init_tts()
        self._optional_services_initialized = True
        self.startup_timer.mark("optional services initialized")

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
                            self.window.speak(f"{msg}【{time_str}】【{result.reminder_text}】")
                        else:
                            self.window.speak(msg)
                    else:
                        self.window.speak(self.utility_text("reminder_ambiguous"))
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
                                self.window.speak(f"{msg}【{time_str}】【{r_text}】")
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
        context: dict[str, Any] = {"recent_messages": recent_messages}
        memory_config = self.app_config.get("memory_features", {})
        if isinstance(memory_config, dict) and bool(
            memory_config.get("long_term_enabled", False)
        ):
            context["long_term_memories"] = self.long_term_memory_store.retrieve(
                user_text,
                top_k=int(memory_config.get("long_term_top_k", 3)),
            )
        self.worker = ChatWorker(self.daniya_adapter, user_text, context=context)
        # [LEGACY] 原: self.worker = ChatWorker(self.chat_client, user_text)
        self.worker.reply_ready.connect(lambda reply, source: self._handle_reply(user_text, reply, source))
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.start()

    def _handle_reply(self, user_text: str, reply: str, source: str) -> None:
        self.mood_manager.update_from_interaction("chat")
        print(f"[Daniya] chat saved source={source}")
        self.history_manager.append(user_text, reply, source)
        memory_config = self.app_config.get("memory_features", {})
        if (
            source != "engine_error"
            and isinstance(memory_config, dict)
            and bool(memory_config.get("long_term_enabled", False))
        ):
            self.long_term_memory_store.remember_exchange(
                user_text,
                reply,
                source=source,
                max_entries=int(memory_config.get("long_term_max_entries", 500)),
            )
        upgraded = self.affinity_manager.add_chat()
        self.window.update_affinity(self.affinity_manager.badge())
        self.window.set_input_enabled(True)
        self.window.set_thinking_state(False)
        self.window.speak(reply)
        self._tts_play(reply)
        self.worker = None
        if upgraded:
            QTimer.singleShot(2500, lambda: self._check_affinity_upgrade(upgraded))

    def is_idle_behavior_allowed(self) -> bool:
        if self._focus_suppresses("focus_mode_silence_idle_chat"):
            return False
        if self._is_feedback_dragging():
            return False
        if self.worker is not None and self.worker.isRunning():
            return False
        if self.window.typewriter.is_typing:
            return False
        if self.window.bubble.isVisible():
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
        self.mood_manager.update_from_interaction("click")
        success, upgraded = self.affinity_manager.add_click()
        if success:
            self.window.update_affinity(self.affinity_manager.badge())
        # [FIX-S2] 记录点击前状态，用于 sleep/wake 语音判定（首次入睡 / 从睡眠醒来）
        was_sleeping = (
            self.window.animation_manager.state_manager.get_state() == "sleeping"
        )
        if self.day_night_manager.is_night():
            self.window.animation_manager.trigger_sleeping()
            # [FIX-S2] sleep 语音：仅首次进入睡眠时播（已在睡眠再点击不重播）
            if not was_sleeping:
                self._voice_play_event("sleep")
        else:
            self.window.animation_manager.trigger_clicked()
            # [FIX-S2] wake 语音：白天点击若宠物刚从睡眠醒来
            if was_sleeping:
                self._voice_play_event("wake")
        self.window.speak(self.day_night_manager.click_line())
        # [CHANGE-003+005] 物理点击事件流入引擎（后台线程，不阻塞 GUI）
        self._fire_physical_event("user_click")
        # [FIX-S2] 接入物理事件语音：clip pack 分类音效（click 类）。
        # voice_router 未初始化时 _voice_play_event 自动 no-op，不影响首启。
        self._voice_play_event("pet_click")
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

    def reload_character(self, character_id: str | None = None) -> bool:
        from .character_pack_editor import CharacterPackEditor
        requested_character_id = character_id or self.app_config.get("current_character", "daniya")

        # 1. Re-initialize DaniyaEngineAdapter
        self.daniya_adapter = DaniyaEngineAdapter(
            model_client=self.chat_client,
            config=DaniyaEngineAdapterConfig(character_id=requested_character_id)
        )
        resolved_char_id = self.daniya_adapter.character_pack.character_id
        self.app_config["current_character"] = resolved_char_id
        self.config_manager.save_app_config(self.app_config)

        # 2. Re-initialize AssetManager
        self.asset_manager = AssetManager(self.app_config, resolved_char_id)
        growth_manager = getattr(self, "growth_manager", None)
        if growth_manager is not None:
            growth_manager.reload_character(resolved_char_id)
        ambient_theater = getattr(self, "ambient_event_theater", None)
        if ambient_theater is not None:
            ambient_theater.reload_character(resolved_char_id)

        # 3. Bind animation and state managers
        self.daniya_adapter.animation_manager = self.thread_safe_anim_manager
        self.daniya_adapter.state_manager = self.thread_safe_anim_manager

        # 4. Update window references and reload manifest/assets
        self.window.clear_render_cache()
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
            self.settings_window.relationship_viewer.character_id = resolved_char_id
            self.settings_window._refresh_char_info()
            self.settings_window._refresh_character_status()
            self.settings_window._refresh_action_status()
            self.settings_window._load_pack_file(self.settings_window.pack_file_combo.currentText())

        print(f"[Daniya] Hot reloaded character ID: {resolved_char_id} (requested: {requested_character_id})")
        return True

    def set_pet_feature(self, key: str, enabled: bool) -> None:
        if key not in {"hover_animation_enabled", "edge_peek_enabled", "click_to_call_enabled"}:
            return
        self.app_config.setdefault("pet", {})[key] = bool(enabled)
        self.config_manager.save_app_config(self.app_config)
        self.window.sync_feature_timers()
        self.window.set_context_menu(self.menu_manager.create_menu())

    def open_file_organizer(self) -> None:
        from .file_organizer_dialog import FileOrganizerDialog

        dialog = FileOrganizerDialog(
            enabled=bool(self.app_config.get("file_organizer_enabled", False)),
            parent=self.window,
            message_lookup=self.utility_text,
        )
        dialog.exec()

    def open_growth_center(self) -> None:
        from .growth_dialog import GrowthDialog

        dialog = GrowthDialog(self, self.window)
        dialog.exec()
        self.window.set_context_menu(self.menu_manager.create_menu())

    def apply_integrated_feature_config(self) -> None:
        config = self.config_manager._normalize_app_config(self.app_config)
        self.pomodoro.update_config(config.get("pomodoro", {}))
        self.app_config.update(config)
        self.reminder_manager.set_enabled(bool(config.get("reminder_enabled", True)))
        self.idle_manager.set_enabled(bool(config.get("idle_chat_enabled", False)))
        self.time_event_manager.set_enabled(bool(config.get("hourly_chime_enabled", False)))
        self.window.behavior_engine.reload_config(config)
        self.window.sync_feature_timers()

        self.system_status_manager.sample_interval_ms = int(config.get("system_status_interval_seconds", 300)) * 1000
        self.system_status_manager.cooldown_seconds = int(config.get("system_status_cooldown_seconds", 300))
        self.system_status_manager.cpu_threshold = int(config.get("system_status_cpu_threshold", 90))
        self.system_status_manager.memory_threshold = int(config.get("system_status_memory_threshold", 90))
        self.system_status_manager.battery_threshold = int(config.get("system_status_battery_threshold", 20))
        self.system_status_manager.network_check_enabled = bool(config.get("system_status_network_check_enabled", False))
        self.system_status_manager.set_enabled(bool(config.get("system_status_enabled", False)))

        self.clipboard_interaction.max_chars = int(config.get("clipboard_max_chars", 1000))
        self.clipboard_interaction.show_preview = bool(config.get("clipboard_show_preview", False))
        self.clipboard_interaction.sensitive_block_enabled = bool(config.get("clipboard_sensitive_block_enabled", True))
        self.clipboard_interaction.set_enabled(bool(config.get("clipboard_interaction_enabled", False)))

        environment = config.get("environment", {})
        if not isinstance(environment, dict):
            environment = {}
        self.weather_manager.configure(
            location_configured=bool(environment.get("weather_location_configured", False)),
            latitude=float(environment.get("weather_latitude", 0.0)),
            longitude=float(environment.get("weather_longitude", 0.0)),
            interval_seconds=int(environment.get("weather_interval_seconds", 1800)),
        )
        self.weather_manager.set_enabled(bool(environment.get("weather_enabled", False)))
        self.media_presence_manager.configure(
            int(environment.get("media_interval_seconds", 60))
        )
        self.media_presence_manager.set_enabled(
            bool(environment.get("media_presence_enabled", False))
        )
        self.ambient_event_theater.configure(
            int(environment.get("ambient_event_interval_seconds", 1800))
        )
        self.ambient_event_theater.set_enabled(
            bool(environment.get("ambient_events_enabled", False))
        )

        whitelist = config.get("focus_mode_process_whitelist", [])
        if isinstance(whitelist, list):
            self.focus_mode_manager.game_whitelist = {str(item).lower() for item in whitelist if str(item).strip()}
        focus_enabled = bool(config.get("focus_mode_enabled", False))
        if not focus_enabled:
            self.focus_mode_manager.set_auto_detect(False)
            self.focus_mode_manager.exit_focus_mode()
            return
        self.focus_mode_manager.set_auto_detect(bool(config.get("focus_mode_auto_game_detect", False)))
        if bool(config.get("focus_mode_manual", False)):
            self.focus_mode_manager.enter_focus_mode()
        elif not self.focus_mode_manager.auto_focus_active:
            self.focus_mode_manager.exit_focus_mode()

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
        self.window.animation_manager.trigger_remind()
        reminder_text = self.utility_text("reminder_due", text=text)
        self.window.speak(reminder_text)
        self._tts_play(reminder_text)
        # [FIX-S2] 接入物理事件语音：clip pack 分类音效（reminder 类）。
        self._voice_play_event("reminder", text=reminder_text)
        # [CHANGE-003+005] 提醒到期事件流入引擎（后台线程）
        self._fire_physical_event("reminder_due")
        box = QMessageBox(self.window)
        box.setWindowTitle("达妮娅的唠叨")
        box.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
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
        self.feedback_coordinator.present(
            source="hourly_chime",
            text=text,
            action="remind",
            focus_config_key="focus_mode_silence_hourly_chime",
        )

    def speak_happy(self, text: str) -> None:
        self.feedback_coordinator.present(
            source="idle_chat",
            text=text,
            action="happy",
            focus_config_key="focus_mode_silence_idle_chat",
        )

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
            release_edge_dock = getattr(self.window, "release_edge_dock", None)
            if callable(release_edge_dock):
                release_edge_dock()
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
            from .settings_window import SettingsWindow
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

    def _focus_suppresses(self, config_key: str) -> bool:
        return (
            bool(self.app_config.get("focus_mode_enabled", False))
            and self.focus_mode_manager.should_suppress_notifications()
            and bool(self.app_config.get(config_key, False))
        )

    def _is_feedback_dragging(self) -> bool:
        detector = self.window.behavior_engine.detector
        return bool(
            self.window.drag_start_global is not None
            or detector.is_dragging
            or getattr(detector, "is_pressed", False)
        )

    def _is_settings_open(self) -> bool:
        return self.settings_window is not None and self.settings_window.isVisible()

    def _is_feedback_user_busy(self) -> bool:
        if self.worker is not None and self.worker.isRunning():
            return True
        if self.reminder_boxes:
            return True
        return self.window.is_input_active()

    def _edge_peek_allowed(self) -> bool:
        if self._focus_suppresses("focus_mode_silence_edge_peek"):
            return False
        if self._is_feedback_dragging() or self._is_settings_open() or self._is_feedback_user_busy():
            return False
        return not self.window.typewriter.is_typing and not self.window.bubble.isVisible()

    def _trigger_feedback_action(self, action: str) -> None:
        if action == "happy":
            self.window.animation_manager.trigger_happy()
        elif action == "remind":
            self.window.animation_manager.trigger_remind()
        elif action == "idle":
            self.window.animation_manager.play_idle()

    def _speak_with_tts(self, text: str) -> None:
        """Wrapper for feedback coordinator: show bubble + TTS."""
        self.window.speak(text)
        self._tts_play(text)

    def _speak_idle_behavior(self, text: str) -> None:
        self.feedback_coordinator.present(
            source="idle_behavior",
            text=text,
            action="keep",
            focus_config_key="focus_mode_silence_idle_chat",
        )

    def _on_focus_state_changed(self, active: bool) -> None:
        if active:
            window = getattr(self, "window", None)
            release_edge_dock = getattr(window, "release_edge_dock", None)
            if callable(release_edge_dock):
                release_edge_dock()
        self.feedback_coordinator.present(
            source="focus_enter" if active else "focus_exit",
            text=self.utility_text("focus_enter" if active else "focus_exit"),
            action="remind" if active else "happy",
        )

    def start_pomodoro(self, minutes: int | None = None) -> None:
        self.mood_manager.update_from_interaction("pomodoro_start")
        mins = self.pomodoro.start(minutes)
        self._speak_with_tts(f"……开始专注。{mins} 分钟。我看着你。")

    def cancel_pomodoro(self) -> None:
        if self.pomodoro.active:
            self.pomodoro.cancel()
            self._speak_with_tts("……提前停了。也行。")

    def _on_pomodoro_distraction(self, name: str) -> None:
        self._speak_with_tts("……喂。别分心。")

    def _on_pomodoro_completed(self) -> None:
        self.mood_manager.update_from_interaction("pomodoro_end")
        self.affinity_manager.add_value(self.pomodoro.reward_affinity)
        self.window.update_affinity(self.affinity_manager.badge())
        self._speak_with_tts("……时间到。这次你做到了。")

    def utility_text(self, key: str, **values: Any) -> str:
        return utility_text(self.daniya_adapter.character_pack, key, **values)

    def _on_system_status_alert(self, alert_type: str, message: str) -> None:
        if not bool(self.app_config.get("system_status_enabled", False)):
            return
        self.feedback_coordinator.present(
            source=f"system_status:{alert_type}",
            text=message,
            action="remind",
            focus_config_key="focus_mode_silence_system_status",
        )

    def _on_clipboard_alert(self, result: dict[str, object]) -> None:
        if not bool(self.app_config.get("clipboard_interaction_enabled", False)):
            return
        status = str(result.get("status", ""))
        message = str(result.get("message", ""))
        if status in {"safe", "too_long", "sensitive"} and message:
            self.feedback_coordinator.present(
                source=f"clipboard:{status}",
                text=message,
                action="remind",
                focus_config_key="focus_mode_silence_clipboard",
            )

    def _on_weather_snapshot(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        raining = bool(payload.get("is_raining", False))
        environment = self.app_config.get("environment", {})
        enabled = isinstance(environment, dict) and bool(
            environment.get("weather_enabled", False)
        )
        notify_rain = isinstance(environment, dict) and bool(
            environment.get("weather_notify_rain", True)
        )
        should_notify = (
            enabled
            and notify_rain
            and raining
            and self._last_weather_raining is not True
        )
        self._last_weather_raining = raining
        if not should_notify:
            return
        description = str(payload.get("description", "有降水"))
        temperature = payload.get("temperature_c")
        temperature_text = (
            f"，约 {float(temperature):.0f}°C"
            if isinstance(temperature, (int, float))
            else ""
        )
        self.feedback_coordinator.present(
            source="weather:rain",
            text=f"……外面{description}{temperature_text}。出门记得带伞。",
            action="remind",
            focus_config_key="focus_mode_silence_environment",
            cooldown_seconds=3600,
        )

    def _on_media_presence(self, player_name: str) -> None:
        environment = self.app_config.get("environment", {})
        if not isinstance(environment, dict) or not bool(
            environment.get("media_presence_enabled", False)
        ):
            return
        self.feedback_coordinator.present(
            source=f"media:{player_name}",
            text=f"……检测到 {player_name} 正在运行。我不会读取歌名或播放内容。",
            action="keep",
            focus_config_key="focus_mode_silence_environment",
            cooldown_seconds=300,
        )

    def _on_ambient_event(self, payload: object) -> None:
        if not isinstance(payload, dict):
            return
        environment = self.app_config.get("environment", {})
        if not isinstance(environment, dict) or not bool(
            environment.get("ambient_events_enabled", False)
        ):
            return
        self.feedback_coordinator.present(
            source=f"ambient:{payload.get('id', 'event')}",
            text=str(payload.get("text", "")),
            action=str(payload.get("action", "keep")),
            focus_config_key="focus_mode_silence_environment",
            cooldown_seconds=60,
        )

    def quit(self) -> None:
        # [FIX-S1] 统一退出清理：停止全部后台 QTimer / 线程 / worker，保存最后状态。
        # 退出路径必须永不抛异常——任何一步失败都用 try/except 兜住，保证最终 qapp.quit()。
        self._shutdown_background_managers()
        self._wait_running_workers()
        self._save_state_on_quit()
        self._close_open_dialogs()
        self.qapp.quit()

    def _shutdown_background_managers(self) -> None:
        """[FIX-S1] 停止所有周期性后台 manager 的 QTimer / 线程。

        各 manager 均为 QTimer 驱动（IdleManager/TimeEventManager/MediaPresenceManager/
        SystemStatusManager/FocusModeManager/AmbientEventTheater），停 timer 即不再派发新任务。
        WeatherManager 有完整 shutdown()（含等飞行 worker）。
        """
        logger = logging.getLogger("daniya")
        # (attr_name, stop_callable)：stop_callable 接收 manager 实例
        stoppers = [
            ("system_status_manager", _stop_timer_manager),
            ("focus_mode_manager", _stop_timer_manager),
            ("idle_manager", _stop_timer_manager),
            ("time_event_manager", _stop_timer_manager),
            ("media_presence_manager", _stop_timer_manager),
            ("ambient_event_theater", _stop_timer_manager),
            ("weather_manager", lambda m: m.shutdown()),
        ]
        for attr_name, stop in stoppers:
            mgr = getattr(self, attr_name, None)
            if mgr is None:
                continue
            try:
                stop(mgr)
            except Exception:
                logger.debug("quit: stopping %s raised", attr_name, exc_info=True)

    def _wait_running_workers(self) -> None:
        """[FIX-S1] 等待飞行中的 chat worker / 物理事件 worker 收尾（带超时，避免卡退出）。"""
        if hasattr(self, "worker") and self.worker is not None and self.worker.isRunning():
            try:
                self.worker.wait(2000)
            except Exception:
                pass
        if hasattr(self, "_phys_workers"):
            for w in list(self._phys_workers):
                try:
                    if w.isRunning():
                        w.wait(2000)
                except Exception:
                    pass

    def _save_state_on_quit(self) -> None:
        """[FIX-S1] 退出前持久化最后状态（窗口/好感度/提醒等）。原 quit() 缺这步会丢最后一次变更。"""
        logger = logging.getLogger("daniya")
        try:
            self.config_manager.save_app_config(self.app_config)
        except Exception:
            logger.debug("quit: save_app_config raised", exc_info=True)
        # 提醒：若有 save 方法则保存（防御性，方法不存在则跳过）
        save_fn = getattr(getattr(self, "reminder_manager", None), "save", None)
        if callable(save_fn):
            try:
                save_fn()
            except Exception:
                logger.debug("quit: reminder_manager.save raised", exc_info=True)

    def _close_open_dialogs(self) -> None:
        """[FIX-S1] 关闭仍在屏幕上的提醒弹窗，避免退出时残留或访问已销毁对象。"""
        boxes = list(getattr(self, "reminder_boxes", []))
        for box in boxes:
            try:
                box.done(0)
            except Exception:
                pass
        try:
            self.reminder_boxes.clear()
        except Exception:
            pass


    # -- [CHANGE-005] 物理事件后台调度 --

    def _fire_physical_event(self, event_name: str) -> None:
        """在后台线程中串行触发物理事件，避免阻塞 GUI 主线程。"""
        self._pending_phys_events.append(event_name)
        if not self._phys_busy:
            self._drain_next_physical_event()

    def _drain_next_physical_event(self) -> None:
        if not self._pending_phys_events:
            self._phys_busy = False
            return
        self._phys_busy = True
        event_name = self._pending_phys_events.popleft()
        w = PhysicalEventWorker(self.daniya_adapter, event_name)
        self._phys_workers.append(w)

        def _done() -> None:
            self._cleanup_phys_worker(w)
            self._drain_next_physical_event()

        w.finished.connect(_done)
        w.start()

    def _fire_drag_event(self) -> None:
        """拖拽防抖定时器到期后触发一次拖拽事件。"""
        self.mood_manager.update_from_interaction("drag")
        self._voice_play_event("pet_drag")
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


def _stop_timer_manager(mgr: object) -> None:
    """[FIX-S1] 停止 QTimer 驱动的 manager。

    优先调用 shutdown()（若存在），否则停 timer。抽成模块级纯函数便于单测 mock。
    """
    shutdown = getattr(mgr, "shutdown", None)
    if callable(shutdown):
        shutdown()
        return
    timer = getattr(mgr, "timer", None)
    if timer is not None:
        timer.stop()


def _stable_single_instance_port() -> int:
    seed = str(bundled_root()).encode("utf-8", "ignore")
    digest = hashlib.blake2s(seed, digest_size=2).digest()
    return 42000 + (int.from_bytes(digest, "big") % 20000)


_SINGLE_INSTANCE_PORT = _stable_single_instance_port()
_SINGLE_INSTANCE_LOCK: socket.socket | None = None


def _acquire_single_instance_lock() -> bool:
    """[FIX-S3] 尝试占用单实例锁。

    用绑定到 127.0.0.1:固定端口 的 socket 作为单实例锁。
    - 绑定成功 → 本进程持锁，返回 True。
    - 绑定失败（端口被占）→ 已有实例在运行，返回 False。
    - 进程退出时 socket 由 OS 回收端口，崩溃也不会残留。
    """
    global _SINGLE_INSTANCE_LOCK
    if _SINGLE_INSTANCE_LOCK is not None:
        return True
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
    try:
        sock.bind(("127.0.0.1", _SINGLE_INSTANCE_PORT))
    except OSError:
        try:
            sock.close()
        except OSError:
            pass
        return False
    _SINGLE_INSTANCE_LOCK = sock
    return True


def run(process_started_at: float | None = None) -> None:
    from .logging_setup import configure_logging, install_excepthook
    startup_timer = StartupTimer(started_at=process_started_at)
    configure_logging()
    install_excepthook()
    logger = logging.getLogger("daniya")

    # [FIX-S3] 单实例锁：防止双开导致配置互覆盖 / 双桌宠重叠
    if not _acquire_single_instance_lock():
        logger.info("single_instance: another instance already running, exiting")
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.information(
            None,
            "达妮娅已经在运行",
            "桌宠已经开着一个啦，去屏幕上找找她吧。",
        )
        sys.exit(0)

    app = QApplication(sys.argv)
    startup_timer.mark("QApplication created")
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

    # [FIX-S4] 包住 controller 初始化与首帧显示：任一 manager 初始化抛异常时，
    # console=False 打包下进程会静默崩溃，用户零反馈。这里兜底弹窗 + 写日志。
    controller = None
    try:
        controller = AppController(app, startup_timer=startup_timer)
        # [FIX-S1] 绑定 aboutToQuit 作为退出清理双保险：即便托盘退出路径漏调 quit()，
        # 应用关闭时也会走统一清理。controller 已确认创建成功才绑定。
        app.aboutToQuit.connect(controller.quit)
        controller.show()
    except Exception:
        _report_fatal_startup_error(logger)
        sys.exit(1)
    sys.exit(app.exec())


def _report_fatal_startup_error(logger: logging.Logger) -> None:
    """[FIX-S4] 首启崩溃的统一反馈：写日志 + 弹 critical 提示。

    抽成独立函数便于单测（run() 整体含阻塞 wizard，不宜直接单测）。
    console=False 打包下，AppController 初始化抛异常若不兜底 → 进程静默死、用户零提示。
    """
    logger.exception("fatal: AppController init or show failed")
    QMessageBox.critical(
        None,
        "达妮娅启动失败",
        "桌宠启动时遇到严重错误，无法继续。\n"
        "详细信息已写入日志。\n请把 logs\\app.log 反馈给开发者。",
    )
