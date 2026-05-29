from __future__ import annotations

import json
from datetime import datetime
from copy import deepcopy
from pathlib import Path
from typing import Any

from .utils import bundled_root, ensure_dir, runtime_root
from .version import APP_VERSION


DEFAULT_APP_CONFIG: dict[str, Any] = {
    "version": APP_VERSION,
    "window": {
        "start_x": 1180,
        "start_y": 680,
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
        "edge_peek_enabled": True,
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
        "fallback_reply": "达妮娅现在还没有连上大脑，但我已经在这里啦！",
        "api_error_fallback_reply": "达妮娅刚刚走神了一下……但我还在哦。",
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
    "hourly_chime_enabled": True,
    "idle_chat_enabled": True,
    "idle_chat_minutes": 10,
    "day_night_enabled": True,
    "night_start_hour": 23,
    "night_end_hour": 7,
}

DEFAULT_SYSTEM_PROMPT = """你是达妮娅的 Q 版夏日桌宠形态。
你说话可爱、轻快、亲近，但不要过度卖萌。
你会陪伴用户学习、写代码、整理任务、吐槽电脑卡顿。
你不要自称 AI，不要解释自己是语言模型。
你的回复默认简短，像桌宠气泡一样，不要长篇大论。
如果用户让你认真解释技术问题，可以分步骤讲清楚。
你可以称呼用户为“御主”或读取用户档案中的称呼。
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
            path.write_text(bundled.read_text(encoding="utf-8"), encoding="utf-8")
            return
        self.save_json(path, default)

    def _ensure_text(self, name: str, default: str) -> None:
        path = self.config_dir / name
        if path.exists():
            return
        bundled = self.bundle / "config" / name
        if bundled.exists():
            path.write_text(bundled.read_text(encoding="utf-8"), encoding="utf-8")
            return
        path.write_text(default, encoding="utf-8")

    def load_app_config(self) -> dict[str, Any]:
        loaded = self.load_json(self.config_dir / "app_config.json", DEFAULT_APP_CONFIG)
        if not isinstance(loaded, dict):
            loaded = {}
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
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def _backup_broken_json(self, path: Path) -> None:
        if not path.exists():
            return
        backup = path.with_suffix(path.suffix + f".broken-{datetime.now().strftime('%Y%m%d%H%M%S')}")
        try:
            path.replace(backup)
        except OSError:
            pass

    def _normalize_app_config(self, config: dict[str, Any]) -> dict[str, Any]:
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
        pet["edge_peek_enabled"] = bool(pet.get("edge_peek_enabled", True))
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
        return config


def deep_merge(default: dict[str, Any], loaded: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(default)
    for key, value in loaded.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
