from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from .config_manager import ConfigManager
from .utils import resource_path


DEFAULT_GROWTH_STATE: dict[str, Any] = {
    "schema_version": 1,
    "coins": 100,
    "level": 1,
    "experience": 0,
    "inventory": {},
    "owned_outfits": ["default"],
    "equipped_outfit": "default",
    "last_daily_claim": "",
}


@dataclass(frozen=True)
class GrowthResult:
    ok: bool
    message: str
    affinity_delta: int = 0


class GrowthManager:
    """Pure-local growth, inventory, shop, and outfit state."""

    def __init__(
        self,
        config_manager: ConfigManager,
        app_config: dict[str, Any],
        character_id: str = "daniya",
        catalog_root: Path | None = None,
    ) -> None:
        self.config_manager = config_manager
        self.app_config = app_config
        self.character_id = character_id
        self.catalog_root = catalog_root or resource_path("characters", character_id)
        self.state_path = self.config_manager.data_dir / "growth_state.json"
        self._items = self._load_catalog("items.json", "items")
        self._outfits = self._load_catalog("outfits.json", "outfits")

    def reload_character(
        self,
        character_id: str,
        catalog_root: Path | None = None,
    ) -> None:
        self.character_id = character_id
        self.catalog_root = catalog_root or resource_path("characters", character_id)
        self._items = self._load_catalog("items.json", "items")
        self._outfits = self._load_catalog("outfits.json", "outfits")

    def is_enabled(self) -> bool:
        growth = self.app_config.get("growth", {})
        return isinstance(growth, dict) and bool(growth.get("enabled", False))

    def set_enabled(self, enabled: bool) -> None:
        growth = self.app_config.setdefault("growth", {})
        if not isinstance(growth, dict):
            growth = {}
            self.app_config["growth"] = growth
        growth["enabled"] = bool(enabled)
        self.config_manager.save_app_config(self.app_config)

    def items(self) -> list[dict[str, Any]]:
        return deepcopy(self._items)

    def outfits(self) -> list[dict[str, Any]]:
        return deepcopy(self._outfits)

    def snapshot(self, affinity: int = 0) -> dict[str, Any]:
        state = self._load_state()
        state["next_level_experience"] = self._level_threshold(int(state["level"]))
        state["available_outfits"] = [
            outfit["id"]
            for outfit in self._outfits
            if self._requirements_met(outfit, state, affinity)
        ]
        return state

    def claim_daily(self, today: date | None = None) -> GrowthResult:
        if not self.is_enabled():
            return self._disabled_result()
        state = self._load_state()
        day = (today or date.today()).isoformat()
        if state["last_daily_claim"] == day:
            return GrowthResult(False, "今天的本地补给已经领取过了。")
        reward = self._positive_int(
            self.app_config.get("growth", {}).get("daily_coin_reward", 25),
            25,
        )
        state["last_daily_claim"] = day
        state["coins"] += reward
        self._save_state(state)
        return GrowthResult(True, f"领取了 {reward} 枚本地硬币。")

    def buy_item(self, item_id: str, quantity: int = 1) -> GrowthResult:
        if not self.is_enabled():
            return self._disabled_result()
        item = self._find(self._items, item_id)
        if item is None:
            return GrowthResult(False, "没有找到这个物品。")
        quantity = max(1, min(99, int(quantity)))
        cost = self._positive_int(item.get("price"), 0) * quantity
        state = self._load_state()
        if state["coins"] < cost:
            return GrowthResult(False, f"硬币不足，还需要 {cost - state['coins']} 枚。")
        state["coins"] -= cost
        inventory = state["inventory"]
        inventory[item_id] = int(inventory.get(item_id, 0)) + quantity
        self._save_state(state)
        return GrowthResult(True, f"已购买 {item['name']} × {quantity}。")

    def feed(self, item_id: str) -> GrowthResult:
        if not self.is_enabled():
            return self._disabled_result()
        item = self._find(self._items, item_id)
        if item is None:
            return GrowthResult(False, "没有找到这个物品。")
        state = self._load_state()
        inventory = state["inventory"]
        count = int(inventory.get(item_id, 0))
        if count <= 0:
            return GrowthResult(False, f"背包里没有 {item['name']}。")
        inventory[item_id] = count - 1
        if inventory[item_id] <= 0:
            inventory.pop(item_id, None)
        old_level = state["level"]
        self._add_experience(state, self._positive_int(item.get("growth"), 1))
        self._save_state(state)
        level_text = (
            f" 成长等级提升到 {state['level']}。"
            if state["level"] > old_level
            else ""
        )
        return GrowthResult(
            True,
            f"达妮娅收下了 {item['name']}。{level_text}".strip(),
            affinity_delta=max(0, int(item.get("affinity", 0))),
        )

    def buy_outfit(self, outfit_id: str, affinity: int) -> GrowthResult:
        if not self.is_enabled():
            return self._disabled_result()
        outfit = self._find(self._outfits, outfit_id)
        if outfit is None:
            return GrowthResult(False, "没有找到这套服装。")
        state = self._load_state()
        if outfit_id in state["owned_outfits"]:
            return GrowthResult(False, "这套服装已经在衣柜里了。")
        if not self._requirements_met(outfit, state, affinity):
            return GrowthResult(False, self._requirement_message(outfit))
        cost = self._positive_int(outfit.get("price"), 0)
        if state["coins"] < cost:
            return GrowthResult(False, f"硬币不足，还需要 {cost - state['coins']} 枚。")
        state["coins"] -= cost
        state["owned_outfits"].append(outfit_id)
        self._save_state(state)
        return GrowthResult(True, f"已解锁服装：{outfit['name']}。")

    def equip_outfit(self, outfit_id: str, affinity: int) -> GrowthResult:
        if not self.is_enabled():
            return self._disabled_result()
        outfit = self._find(self._outfits, outfit_id)
        if outfit is None:
            return GrowthResult(False, "没有找到这套服装。")
        state = self._load_state()
        if not self._requirements_met(outfit, state, affinity):
            return GrowthResult(False, self._requirement_message(outfit))
        if outfit_id not in state["owned_outfits"]:
            return GrowthResult(False, "请先在衣柜中解锁这套服装。")
        state["equipped_outfit"] = outfit_id
        self._save_state(state)
        return GrowthResult(True, f"当前服装已切换为：{outfit['name']}。")

    def reset_state(self) -> None:
        self._save_state(deepcopy(DEFAULT_GROWTH_STATE))

    def _load_catalog(self, filename: str, key: str) -> list[dict[str, Any]]:
        path = self.catalog_root / filename
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        values = payload.get(key, []) if isinstance(payload, dict) else []
        if not isinstance(values, list):
            return []
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for value in values:
            if not isinstance(value, dict):
                continue
            item_id = str(value.get("id", "")).strip()
            name = str(value.get("name", "")).strip()
            if not item_id or not name or item_id in seen:
                continue
            clean = deepcopy(value)
            clean["id"] = item_id
            clean["name"] = name
            result.append(clean)
            seen.add(item_id)
        return result

    def _load_state(self) -> dict[str, Any]:
        loaded = self.config_manager.load_json(self.state_path, DEFAULT_GROWTH_STATE)
        if not isinstance(loaded, dict):
            loaded = {}
        state = deepcopy(DEFAULT_GROWTH_STATE)
        state.update(loaded)
        state["coins"] = max(0, self._safe_int(state.get("coins"), 100))
        state["level"] = max(1, self._safe_int(state.get("level"), 1))
        state["experience"] = max(0, self._safe_int(state.get("experience"), 0))
        inventory = state.get("inventory")
        state["inventory"] = {
            str(item_id): max(0, self._safe_int(count, 0))
            for item_id, count in (inventory.items() if isinstance(inventory, dict) else [])
            if str(item_id).strip() and self._safe_int(count, 0) > 0
        }
        owned = state.get("owned_outfits")
        if not isinstance(owned, list):
            owned = ["default"]
        state["owned_outfits"] = list(
            dict.fromkeys(str(item) for item in owned if str(item).strip())
        )
        if "default" not in state["owned_outfits"]:
            state["owned_outfits"].insert(0, "default")
        equipped = str(state.get("equipped_outfit", "default"))
        state["equipped_outfit"] = (
            equipped if equipped in state["owned_outfits"] else "default"
        )
        state["last_daily_claim"] = str(state.get("last_daily_claim", ""))
        return state

    def _save_state(self, state: dict[str, Any]) -> None:
        self.config_manager.save_json(self.state_path, state)

    def _add_experience(self, state: dict[str, Any], amount: int) -> None:
        state["experience"] += max(0, amount)
        while state["experience"] >= self._level_threshold(state["level"]):
            state["experience"] -= self._level_threshold(state["level"])
            state["level"] += 1

    @staticmethod
    def _level_threshold(level: int) -> int:
        return 40 + max(1, int(level)) * 20

    @staticmethod
    def _find(values: list[dict[str, Any]], value_id: str) -> dict[str, Any] | None:
        return next((value for value in values if value["id"] == value_id), None)

    @classmethod
    def _requirements_met(
        cls,
        outfit: dict[str, Any],
        state: dict[str, Any],
        affinity: int,
    ) -> bool:
        return (
            cls._safe_int(state["level"], 1)
            >= max(1, cls._safe_int(outfit.get("required_level"), 1))
            and cls._safe_int(affinity, 0)
            >= max(0, cls._safe_int(outfit.get("required_affinity"), 0))
        )

    @classmethod
    def _requirement_message(cls, outfit: dict[str, Any]) -> str:
        return (
            f"需要成长等级 {max(1, cls._safe_int(outfit.get('required_level'), 1))}，"
            f"好感度 {max(0, cls._safe_int(outfit.get('required_affinity'), 0))}。"
        )

    @staticmethod
    def _disabled_result() -> GrowthResult:
        return GrowthResult(False, "养成功能尚未启用，请先在养成中心主动开启。")

    @staticmethod
    def _safe_int(value: Any, fallback: int) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    @classmethod
    def _positive_int(cls, value: Any, fallback: int) -> int:
        return max(0, cls._safe_int(value, fallback))
