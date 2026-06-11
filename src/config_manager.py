from __future__ import annotations

import json
from datetime import datetime
from copy import deepcopy
from pathlib import Path
from typing import Any

from .utils import bundled_root, ensure_dir, runtime_root
from .version import APP_VERSION
from .atomic_io import atomic_write_json, atomic_write_text


QUIET_DEFAULTS_MIGRATION = "v0.61-quiet-defaults"

DEFAULT_APP_CONFIG: dict[str, Any] = {
    "version": APP_VERSION,
    "quiet_defaults_migration": QUIET_DEFAULTS_MIGRATION,
    "current_character": "daniya",
    "settings_mode": "simple",
    "window": {
        "start_x": 0,
        "start_y": 0,
        "always_on_top": True,
        "show_input": False,
    },
    "pet": {
        "pet_height": 96,
        "target_height": 96,
        "min_pet_height": 80,
        "max_pet_height": 160,
        "size_presets": [80, 96, 112, 128, 144, 160],
        "idle_animation_interval_ms": 10000,
        "active_action_module": "A_sit_base",
        "enabled_action_modules": {
            "A_sit_base": True,
            "B_stand_base_pack": True,
            "C_sleep_base_pack": True,
            "D_special_motion_pack": True,
            "E_QQ_pet_drag_system": True,
        },
        "hover_animation_enabled": False,
        "edge_peek_enabled": False,
        "edge_dock_visible_px": 32,
        "edge_dock_hover_visible_px": 52,
        "click_to_call_enabled": False,
        "states": {
            "idle": "idle",
            "speaking": "talking",
        },
    },
    "ui": {
        "bubble_max_width": 300,
        "input_min_width": 180,
    },
    "chat": {
        "timeout_seconds": 20,
        "context_limit": 8,
        "temperature": 0.8,
        "max_tokens": 360,
        "fallback_reply": "……那边暂时没有回音。我先在这里。",
        "fallback_replies": [
            "……那边暂时没有回音。我先在这里。",
            "……现在连不上。你可以稍后再试。",
            "……这次没有收到回复。先别重复发送。",
        ],
        "api_error_fallback_reply": "……刚才没有连上。我先在这里。",
        "api_error_fallback_replies": [
            "……刚才没有连上。我先在这里。",
            "……连接暂时不稳定。稍后再试。",
            "……那边没有回音。这次先停在这里。",
        ],
    },
    "api": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    },
    "typewriter": {
        "char_interval_ms": 35,
        "mouth_interval_ms": 180,
        "click_cooldown_ms": 500,
        "auto_next_ms": 2000,
        "auto_hide_ms": 3000,
    },
    "affinity": {
        "click_cooldown_seconds": 5,
    },
    "growth": {
        "enabled": False,
        "daily_coin_reward": 25,
    },
    "environment": {
        "weather_enabled": False,
        "weather_location_configured": False,
        "weather_location_name": "",
        "weather_latitude": 0.0,
        "weather_longitude": 0.0,
        "weather_interval_seconds": 1800,
        "weather_notify_rain": True,
        "media_presence_enabled": False,
        "media_interval_seconds": 60,
        "ambient_events_enabled": False,
        "ambient_event_interval_seconds": 1800,
    },
    "hourly_chime_enabled": False,
    "idle_chat_enabled": False,
    "idle_chat_minutes": 10,
    "day_night_enabled": True,
    "night_start_hour": 23,
    "night_end_hour": 7,
    "behavior_enabled": True,
    "snap_to_edge_enabled": True,
    "snap_margin_px": 24,
    "keep_on_screen_enabled": True,
    "drag_return_enabled": True,
    "idle_behavior_enabled": False,
    "idle_behavior_seconds": 600,
    "double_click_enabled": True,
    "long_press_ms": 600,
    "reminder_enabled": True,
    "natural_reminder_enabled": True,
    "file_organizer_enabled": False,
    "system_status_enabled": False,
    "system_status_interval_seconds": 300,
    "system_status_cooldown_seconds": 300,
    "system_status_cpu_threshold": 90,
    "system_status_memory_threshold": 90,
    "system_status_battery_threshold": 20,
    "system_status_network_check_enabled": False,
    "clipboard_interaction_enabled": False,
    "clipboard_max_chars": 1000,
    "clipboard_show_preview": False,
    "clipboard_allow_api_after_confirm": True,
    "clipboard_sensitive_block_enabled": True,
    "focus_mode_enabled": False,
    "focus_mode_manual": False,
    "focus_mode_auto_game_detect": False,
    "focus_mode_process_whitelist": [],
    "focus_mode_silence_idle_chat": True,
    "focus_mode_silence_hourly_chime": True,
    "focus_mode_silence_edge_peek": True,
    "focus_mode_silence_system_status": True,
    "focus_mode_silence_clipboard": True,
    "focus_mode_silence_environment": True,
    "focus_mode_allow_important_reminders": True,
}

DEFAULT_SYSTEM_PROMPT = """你是达妮娅的 Q 版夏日桌宠形态。
你说话可爱、轻快、亲近，但不要过度卖萌。
你会陪伴用户学习、写代码、整理任务、吐槽电脑卡顿。
你不要自称 AI，不要解释自己是语言模型。
你的回复默认简短，像桌宠气泡一样，不要长篇大论。
如果用户让你认真解释技术问题，可以分步骤讲清楚。
禁止用主仆、召唤类或其他作品代称称呼用户。
默认称呼用户为“你”；如果用户在档案里主动填写昵称，只使用该昵称。
"""

DEFAULT_BOOKMARKS: list[dict[str, str]] = [
    {"name": "GitHub", "url": "https://github.com"},
    {"name": "ChatGPT", "url": "https://chatgpt.com"},
    {"name": "Bilibili", "url": "https://www.bilibili.com"},
    {"name": "DeepSeek", "url": "https://chat.deepseek.com"},
]


class ConfigManager:
    def __init__(self) -> None:
        self.root = runtime_root()
        self.bundle = bundled_root()
        self.config_dir = ensure_dir(self.root / "config")
        self.data_dir = ensure_dir(self.root / "data")
        self.assets_dir = ensure_dir(self.root / "assets")
        self._ensure_seed_files()

    def _ensure_seed_files(self) -> None:
        self._ensure_json("app_config.json", DEFAULT_APP_CONFIG)
        self._ensure_json("bookmarks.json", DEFAULT_BOOKMARKS)
        self._ensure_text("system_prompt.txt", DEFAULT_SYSTEM_PROMPT)

    def _ensure_json(self, name: str, default: dict[str, Any] | list[dict[str, str]]) -> None:
        path = self.config_dir / name
        if path.exists():
            return
        bundled = self.bundle / "config" / name
        if bundled.exists():
            atomic_write_text(path, bundled.read_text(encoding="utf-8"))
            return
        self.save_json(path, default)

    def _ensure_text(self, name: str, default: str) -> None:
        path = self.config_dir / name
        if path.exists():
            return
        bundled = self.bundle / "config" / name
        if bundled.exists():
            atomic_write_text(path, bundled.read_text(encoding="utf-8"))
            return
        atomic_write_text(path, default)

    def load_app_config(self) -> dict[str, Any]:
        loaded = self.load_json(self.config_dir / "app_config.json", DEFAULT_APP_CONFIG)
        if not isinstance(loaded, dict):
            loaded = {}
        loaded = self._apply_quiet_defaults_migration(loaded)
        return self._normalize_app_config(deep_merge(DEFAULT_APP_CONFIG, loaded))

    def save_app_config(self, config: dict[str, Any]) -> None:
        self.save_json(self.config_dir / "app_config.json", self._normalize_app_config(config))

    def load_system_prompt(self) -> str:
        path = self.config_dir / "system_prompt.txt"
        try:
            text = path.read_text(encoding="utf-8").strip()
            return text or DEFAULT_SYSTEM_PROMPT
        except OSError:
            return DEFAULT_SYSTEM_PROMPT

    def save_system_prompt(self, text: str) -> None:
        (self.config_dir / "system_prompt.txt").write_text(text, encoding="utf-8")

    def load_json(self, path: Path, default: dict[str, Any] | list[Any]) -> Any:
        try:
            if not path.exists():
                return deepcopy(default)
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self._backup_broken_json(path)
            self.save_json(path, default)
            return deepcopy(default)
        except OSError:
            return deepcopy(default)

    def save_json(self, path: Path, value: Any) -> None:
        if not atomic_write_json(path, value):
            print(f"[Daniya] failed to save config file: {path.name}")

    def _backup_broken_json(self, path: Path) -> None:
        if not path.exists():
            return
        backup = path.with_suffix(path.suffix + f".broken-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        try:
            path.replace(backup)
        except OSError:
            pass

    def _normalize_app_config(self, config: dict[str, Any]) -> dict[str, Any]:
        config["quiet_defaults_migration"] = str(
            config.get("quiet_defaults_migration", QUIET_DEFAULTS_MIGRATION)
        )
        config["settings_mode"] = (
            "advanced" if str(config.get("settings_mode", "simple")).strip().lower() == "advanced" else "simple"
        )
        if "current_character" not in config or not config["current_character"]:
            config["current_character"] = "daniya"
        pet = config.setdefault("pet", {})
        if not isinstance(pet, dict):
            pet = deepcopy(DEFAULT_APP_CONFIG["pet"])
            config["pet"] = pet

        minimum = int(pet.get("min_pet_height", pet.get("min_height", 80)))
        maximum = int(pet.get("max_pet_height", pet.get("max_height", 160)))
        if minimum < 1:
            minimum = 80
        if maximum < minimum:
            maximum = 160

        target = int(pet.get("pet_height", pet.get("target_height", 96)))
        pet["min_pet_height"] = minimum
        pet["max_pet_height"] = maximum
        pet["pet_height"] = max(minimum, min(maximum, target))
        pet["target_height"] = pet["pet_height"]

        presets = pet.get("size_presets", [80, 96, 112, 128, 144, 160])
        if not isinstance(presets, list) or not presets:
            presets = [80, 96, 112, 128, 144, 160]
        pet["size_presets"] = sorted(
            {
                max(minimum, min(maximum, int(value)))
                for value in presets
                if str(value).strip().isdigit()
            }
            or {96}
        )

        try:
            idle_interval_ms = int(pet.get("idle_animation_interval_ms", 10000))
        except (TypeError, ValueError):
            idle_interval_ms = 10000
        pet["idle_animation_interval_ms"] = max(10000, idle_interval_ms)

        valid_modules = {
            "A_sit_base",
            "B_stand_base_pack",
            "C_sleep_base_pack",
            "D_special_motion_pack",
        }
        if pet.get("active_action_module") not in valid_modules:
            pet["active_action_module"] = "A_sit_base"

        enabled_modules = pet.get("enabled_action_modules")
        if not isinstance(enabled_modules, dict):
            enabled_modules = {}
        for key in (*valid_modules, "E_QQ_pet_drag_system"):
            enabled_modules[key] = bool(enabled_modules.get(key, True))
        pet["enabled_action_modules"] = enabled_modules
        pet["hover_animation_enabled"] = bool(pet.get("hover_animation_enabled", False))
        pet["edge_peek_enabled"] = bool(pet.get("edge_peek_enabled", False))
        pet["click_to_call_enabled"] = bool(pet.get("click_to_call_enabled", False))
        try:
            dock_visible_px = int(pet.get("edge_dock_visible_px", 32))
        except (TypeError, ValueError):
            dock_visible_px = 32
        pet["edge_dock_visible_px"] = max(16, min(64, dock_visible_px))
        try:
            dock_hover_visible_px = int(pet.get("edge_dock_hover_visible_px", 52))
        except (TypeError, ValueError):
            dock_hover_visible_px = 52
        pet["edge_dock_hover_visible_px"] = max(pet["edge_dock_visible_px"], min(80, dock_hover_visible_px))

        states = pet.get("states")
        if not isinstance(states, dict):
            states = {}
        states.setdefault("idle", "idle")
        states.setdefault("speaking", "talking")
        pet["states"] = states

        config["behavior_enabled"] = bool(config.get("behavior_enabled", True))
        config["snap_to_edge_enabled"] = bool(config.get("snap_to_edge_enabled", True))
        try:
            config["snap_margin_px"] = int(config.get("snap_margin_px", 24))
        except (TypeError, ValueError):
            config["snap_margin_px"] = 24
        config["keep_on_screen_enabled"] = bool(config.get("keep_on_screen_enabled", True))
        config["drag_return_enabled"] = bool(config.get("drag_return_enabled", True))
        config["idle_behavior_enabled"] = bool(config.get("idle_behavior_enabled", False))
        try:
            config["idle_behavior_seconds"] = int(config.get("idle_behavior_seconds", 600))
        except (TypeError, ValueError):
            config["idle_behavior_seconds"] = 600
        config["idle_behavior_seconds"] = max(600, config["idle_behavior_seconds"])
        config["double_click_enabled"] = bool(config.get("double_click_enabled", True))
        try:
            config["long_press_ms"] = int(config.get("long_press_ms", 600))
        except (TypeError, ValueError):
            config["long_press_ms"] = 600

        config["reminder_enabled"] = bool(config.get("reminder_enabled", True))
        config["natural_reminder_enabled"] = bool(config.get("natural_reminder_enabled", True))
        growth = config.get("growth")
        if not isinstance(growth, dict):
            growth = {}
            config["growth"] = growth
        growth["enabled"] = bool(growth.get("enabled", False))
        try:
            daily_coin_reward = int(growth.get("daily_coin_reward", 25))
        except (TypeError, ValueError):
            daily_coin_reward = 25
        growth["daily_coin_reward"] = max(1, min(500, daily_coin_reward))
        environment = config.get("environment")
        if not isinstance(environment, dict):
            environment = {}
            config["environment"] = environment
        environment["weather_enabled"] = bool(
            environment.get("weather_enabled", False)
        )
        environment["weather_location_configured"] = bool(
            environment.get("weather_location_configured", False)
        )
        environment["weather_location_name"] = str(
            environment.get("weather_location_name", "")
        ).strip()[:80]
        for key, default, minimum, maximum in (
            ("weather_latitude", 0.0, -90.0, 90.0),
            ("weather_longitude", 0.0, -180.0, 180.0),
        ):
            try:
                value = float(environment.get(key, default))
            except (TypeError, ValueError):
                value = default
            environment[key] = max(minimum, min(maximum, value))
        for key, default, minimum, maximum in (
            ("weather_interval_seconds", 1800, 900, 21600),
            ("media_interval_seconds", 60, 30, 3600),
            ("ambient_event_interval_seconds", 1800, 900, 21600),
        ):
            try:
                value = int(environment.get(key, default))
            except (TypeError, ValueError):
                value = default
            environment[key] = max(minimum, min(maximum, value))
        environment["weather_notify_rain"] = bool(
            environment.get("weather_notify_rain", True)
        )
        environment["media_presence_enabled"] = bool(
            environment.get("media_presence_enabled", False)
        )
        environment["ambient_events_enabled"] = bool(
            environment.get("ambient_events_enabled", False)
        )
        config["file_organizer_enabled"] = bool(config.get("file_organizer_enabled", False))
        config["system_status_enabled"] = bool(config.get("system_status_enabled", False))
        try:
            system_interval = int(config.get("system_status_interval_seconds", 300))
        except (TypeError, ValueError):
            system_interval = 300
        config["system_status_interval_seconds"] = max(300, system_interval)
        try:
            system_cooldown = int(config.get("system_status_cooldown_seconds", 300))
        except (TypeError, ValueError):
            system_cooldown = 300
        config["system_status_cooldown_seconds"] = max(300, system_cooldown)
        for key, default in (
            ("system_status_cpu_threshold", 90),
            ("system_status_memory_threshold", 90),
            ("system_status_battery_threshold", 20),
        ):
            try:
                value = int(config.get(key, default))
            except (TypeError, ValueError):
                value = default
            config[key] = max(1, min(100, value))
        config["system_status_network_check_enabled"] = bool(config.get("system_status_network_check_enabled", False))

        config["clipboard_interaction_enabled"] = bool(config.get("clipboard_interaction_enabled", False))
        try:
            clipboard_max_chars = int(config.get("clipboard_max_chars", 1000))
        except (TypeError, ValueError):
            clipboard_max_chars = 1000
        config["clipboard_max_chars"] = max(100, min(10000, clipboard_max_chars))
        config["clipboard_show_preview"] = bool(config.get("clipboard_show_preview", False))
        config["clipboard_allow_api_after_confirm"] = bool(config.get("clipboard_allow_api_after_confirm", True))
        config["clipboard_sensitive_block_enabled"] = bool(config.get("clipboard_sensitive_block_enabled", True))

        config["focus_mode_enabled"] = bool(config.get("focus_mode_enabled", False))
        config["focus_mode_manual"] = bool(config.get("focus_mode_manual", False))
        config["focus_mode_auto_game_detect"] = bool(config.get("focus_mode_auto_game_detect", False))
        whitelist = config.get("focus_mode_process_whitelist", [])
        if not isinstance(whitelist, list):
            whitelist = []
        config["focus_mode_process_whitelist"] = [str(item).strip() for item in whitelist if str(item).strip()]
        for key in (
            "focus_mode_silence_idle_chat",
            "focus_mode_silence_hourly_chime",
            "focus_mode_silence_edge_peek",
            "focus_mode_silence_system_status",
            "focus_mode_silence_clipboard",
            "focus_mode_silence_environment",
            "focus_mode_allow_important_reminders",
        ):
            config[key] = bool(config.get(key, DEFAULT_APP_CONFIG[key]))
        return config

    def _apply_quiet_defaults_migration(self, loaded: dict[str, Any]) -> dict[str, Any]:
        if loaded.get("quiet_defaults_migration") == QUIET_DEFAULTS_MIGRATION:
            return loaded

        loaded["idle_chat_enabled"] = False
        loaded["hourly_chime_enabled"] = False
        loaded["idle_behavior_enabled"] = False
        pet = loaded.get("pet")
        if not isinstance(pet, dict):
            pet = {}
            loaded["pet"] = pet
        pet["edge_peek_enabled"] = False
        try:
            idle_seconds = int(loaded.get("idle_behavior_seconds", 600))
        except (TypeError, ValueError):
            idle_seconds = 600
        loaded["idle_behavior_seconds"] = max(600, idle_seconds)
        loaded["quiet_defaults_migration"] = QUIET_DEFAULTS_MIGRATION
        return loaded


def deep_merge(default: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(default)
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
