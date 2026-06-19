from __future__ import annotations
from typing import Any

INTENSITY_LEVELS = ("quiet", "lively", "demo")


class BehaviorConfig:
    def __init__(self, app_config: dict[str, Any]) -> None:
        self.app_config = app_config

    @property
    def behavior_enabled(self) -> bool:
        return bool(self.app_config.get("behavior_enabled", True))

    @property
    def behavior_intensity(self) -> str:
        raw = self.app_config.get("behavior_intensity", "lively")
        return raw if raw in INTENSITY_LEVELS else "lively"

    @property
    def dnd_mode(self) -> bool:
        return bool(self.app_config.get("dnd_mode", False))

    @property
    def snap_to_edge_enabled(self) -> bool:
        return bool(self.app_config.get("snap_to_edge_enabled", True))

    @property
    def snap_margin_px(self) -> int:
        try:
            return int(self.app_config.get("snap_margin_px", 24))
        except (TypeError, ValueError):
            return 24

    @property
    def keep_on_screen_enabled(self) -> bool:
        return bool(self.app_config.get("keep_on_screen_enabled", True))

    @property
    def drag_return_enabled(self) -> bool:
        return bool(self.app_config.get("drag_return_enabled", True))

    @property
    def idle_behavior_enabled(self) -> bool:
        return bool(self.app_config.get("idle_behavior_enabled", False))

    @property
    def idle_behavior_seconds(self) -> int:
        try:
            return max(600, int(self.app_config.get("idle_behavior_seconds", 600)))
        except (TypeError, ValueError):
            return 600

    @property
    def double_click_enabled(self) -> bool:
        return bool(self.app_config.get("double_click_enabled", True))

    @property
    def long_press_ms(self) -> int:
        try:
            return int(self.app_config.get("long_press_ms", 600))
        except (TypeError, ValueError):
            return 600
