from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from .utils import bundled_root, runtime_root


PET_ID = "daniya_summer"

ACTION_ALIASES: dict[str, tuple[str, ...]] = {
    "idle": ("idle", "normal1"),
    "soft_idle": ("soft_idle", "idle", "normal1"),
    "talk": ("talk", "talking", "speaking", "normal2"),
    "talking": ("talking", "talk", "speaking", "normal2"),
    "speaking": ("talk", "talking", "speaking", "normal2"),
    "hover": ("hover", "idle", "normal1"),
    "clicked": ("clicked",),
    "drag": ("drag", "dragging"),
    "dragging": ("dragging", "drag"),
    "drag_pickup": ("drag_pickup", "pickup", "dragging", "drag"),
    "drag_hold": ("drag_hold", "dragging", "drag"),
    "drag_drop": ("drag_drop", "drop", "dragging", "drag"),
    "sleep": ("sleep", "sleeping"),
    "sleeping": ("sleeping", "sleep"),
    "happy": ("happy",),
    "remind": ("remind",),
    "bubble": ("bubble", "happy", "talk", "talking", "idle", "normal1"),
    "look_away": ("look_away", "idle", "normal1"),
    "close_idle": ("close_idle", "happy", "idle", "normal1"),
    "walking": ("walking",),
    "edge_peek_left": ("edge_peek_left",),
    "edge_peek_right": ("edge_peek_right",),
}

ACTION_MODULES: dict[str, str] = {
    "A_sit_base": "A_sit_base",
    "B_stand_base_pack": "B_stand_base_pack",
    "C_sleep_base_pack": "C_sleep_base_pack",
    "D_special_motion_pack": "D_special_motion_pack",
}

DEFAULT_MANIFEST: dict[str, Any] = {
    "name": PET_ID,
    "display_name": "Public Placeholder Asset",
    "default_height": 96,
    "actions_version": "0.4",
    "animations": {
        "idle": ["normal1.png"],
        "talk": ["normal1.png", "normal2.png"],
        "talking": ["normal1.png", "normal2.png"],
        "hover": ["normal1.png"],
        "clicked": ["normal2.png"],
        "drag": ["normal2.png"],
        "dragging": ["normal2.png"],
        "drag_pickup": ["normal2.png"],
        "drag_hold": ["normal2.png"],
        "drag_drop": ["normal2.png"],
        "sleep": ["normal1.png"],
        "sleeping": ["normal1.png"],
        "happy": ["normal2.png"],
        "remind": ["normal2.png"],
        "walking": ["normal1.png", "normal2.png"],
        "edge_peek_left": ["normal1.png"],
        "edge_peek_right": ["normal1.png"],
    },
    "animation_groups": {},
}


class AssetManager:
    def __init__(self, app_config: dict[str, Any], character_id: str = "daniya") -> None:
        self.app_config = app_config
        self.character_id = character_id
        self.runtime_assets = runtime_root() / "assets"
        self.bundled_assets = bundled_root() / "assets"
        self.characters_dir = runtime_root() / "characters"
        if not self.characters_dir.exists():
            self.characters_dir = bundled_root() / "characters"
        self.pet_id = PET_ID
        self._manifest: dict[str, Any] | None = None
        self._asset_dir: Path | None = None
        self._manifest_log_printed = False

    def active_asset_dir(self) -> Path:
        if self._asset_dir is not None:
            return self._asset_dir

        candidates = [
            self.characters_dir / self.character_id / "assets",
            self.characters_dir / "template" / "assets",
            self.runtime_assets / "private" / self.pet_id,
            self.runtime_assets / "private",
            self.runtime_assets / "placeholder" / self.pet_id,
            self.runtime_assets / "placeholder",
            self.bundled_assets / "placeholder" / self.pet_id,
            self.bundled_assets / "placeholder",
        ]
        for candidate in candidates:
            if candidate.exists() and ((candidate / "manifest.json").exists() or (candidate / "normal1.png").exists()):
                self._asset_dir = candidate
                return candidate
        self._asset_dir = self.runtime_assets / "placeholder"
        return self._asset_dir

    def manifest(self) -> dict[str, Any]:
        if self._manifest is not None:
            return self._manifest

        import json

        path = self.active_asset_dir() / "manifest.json"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict):
                    self._manifest = self._merge_manifest(data)
                    self._print_manifest_debug(path, self._manifest)
                    return self._manifest
            except (OSError, json.JSONDecodeError):
                pass

        # Fallback to template manifest
        template_path = self.characters_dir / "template" / "assets" / "manifest.json"
        if template_path.exists() and template_path != path:
            try:
                data = json.loads(template_path.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict):
                    self._manifest = self._merge_manifest(data)
                    self._print_manifest_debug(template_path, self._manifest)
                    return self._manifest
            except (OSError, json.JSONDecodeError):
                pass

        self._manifest = self._merge_manifest({})
        self._print_manifest_debug(path, self._manifest)
        return self._manifest

    def image_path(self, name: str) -> Path:
        frames = self.frames_for_state(name)
        if frames:
            return frames[0]
        return self._resolve_image_ref(f"{name}.png")

    def frames_for_state(self, state: str) -> list[Path]:
        animations = self.manifest().get("animations", {})
        refs: list[str] = []
        if isinstance(animations, dict):
            for key in self._state_keys(state):
                value = animations.get(key)
                if isinstance(value, list):
                    refs = [str(item) for item in value if str(item).strip()]
                elif isinstance(value, str):
                    refs = [value]
                if refs:
                    break

        if not refs and state in {"normal1", "normal2"}:
            refs = [f"{state}.png"]
        if not refs:
            refs = DEFAULT_MANIFEST["animations"].get(state, ["normal1.png"])

        frames = [path for ref in refs if (path := self._resolve_image_ref(ref)).exists()]
        if frames:
            return frames

        fallback_refs = ["normal1.png", "normal2.png"] if state in {"talk", "talking", "speaking"} else ["normal1.png"]
        return [path for ref in fallback_refs if (path := self._resolve_image_ref(ref)).exists()]

    def select_frames_for_state(self, state: str) -> list[Path]:
        groups = self._animation_groups_for_state(state)
        if not groups:
            return self.frames_for_state(state)

        total = sum(weight for weight, _frames in groups)
        if total <= 0:
            return self.frames_for_state(state)

        pick = random.uniform(0, total)
        upto = 0.0
        for weight, frames in groups:
            upto += weight
            if pick <= upto:
                return frames
        return groups[-1][1]

    def active_action_module(self) -> str:
        pet_config = self.app_config.setdefault("pet", {})
        module = str(pet_config.get("active_action_module", "A_sit_base"))
        return module if module in ACTION_MODULES else "A_sit_base"

    def set_active_action_module(self, module: str) -> str:
        pet_config = self.app_config.setdefault("pet", {})
        active = module if module in ACTION_MODULES else "A_sit_base"
        pet_config["active_action_module"] = active
        return active

    def state_name(self, role: str) -> str:
        states = self.app_config.get("pet", {}).get("states", {})
        if isinstance(states, dict):
            value = states.get(role)
            if isinstance(value, str) and value.strip():
                return value.strip()
        fallback = {"idle": "idle", "speaking": "talking"}
        return fallback.get(role, role)

    def icon_path(self) -> Path:
        candidates = [
            self.active_asset_dir() / "app.ico",
            self.runtime_assets / "private" / "app.ico",
            self.runtime_assets / "placeholder" / "app.ico",
            self.bundled_assets / "placeholder" / "app.ico",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[-1]

    def target_height(self) -> int:
        pet_config = self.app_config.get("pet", {})
        minimum = int(pet_config.get("min_pet_height", pet_config.get("min_height", 80)))
        maximum = int(pet_config.get("max_pet_height", pet_config.get("max_height", 160)))
        target = int(pet_config.get("pet_height", pet_config.get("target_height", 96)))
        return max(minimum, min(maximum, target))

    def size_presets(self) -> list[int]:
        pet_config = self.app_config.get("pet", {})
        presets = pet_config.get("size_presets", [80, 96, 112, 128, 144, 160])
        if not isinstance(presets, list):
            return [80, 96, 112, 128, 144, 160]
        minimum = int(pet_config.get("min_pet_height", 80))
        maximum = int(pet_config.get("max_pet_height", 160))
        values: set[int] = set()
        for value in presets:
            try:
                values.add(max(minimum, min(maximum, int(value))))
            except (TypeError, ValueError):
                continue
        return sorted(values or {96})

    def set_target_height(self, height: int) -> int:
        pet_config = self.app_config.setdefault("pet", {})
        minimum = int(pet_config.get("min_pet_height", 80))
        maximum = int(pet_config.get("max_pet_height", 160))
        clamped = max(minimum, min(maximum, int(height)))
        pet_config["pet_height"] = clamped
        pet_config["target_height"] = clamped
        return clamped

    def _resolve_image_ref(self, ref: str) -> Path:
        clean = ref.replace("\\", "/").lstrip("/")
        active = self.active_asset_dir()

        template_assets = self.characters_dir / "template" / "assets"
        placeholder_dir = self.runtime_assets / "placeholder"
        if not placeholder_dir.exists():
            placeholder_dir = self.bundled_assets / "placeholder"

        candidates = [
            active / clean,
            template_assets / clean,
            placeholder_dir / clean,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate

        # Resolve normal1/normal2 fallback if file is still not found
        is_normal2 = "normal2" in clean or any(k in clean.lower() for k in ("clicked", "drag", "happy", "remind", "talk", "speaking"))
        fallback_name = "normal2.png" if is_normal2 else "normal1.png"

        candidates_fallback = [
            active / fallback_name,
            template_assets / fallback_name,
            placeholder_dir / fallback_name,
            placeholder_dir / "normal1.png",
        ]
        for candidate in candidates_fallback:
            if candidate.exists():
                return candidate

        return active / clean

    def _merge_manifest(self, data: dict[str, Any]) -> dict[str, Any]:
        manifest = {**DEFAULT_MANIFEST, **data}
        defaults = DEFAULT_MANIFEST["animations"]
        animations = data.get("animations")
        if isinstance(animations, dict):
            user_animations = dict(animations)
            for current, legacy in (("talk", "talking"), ("drag", "dragging"), ("sleep", "sleeping")):
                if current not in user_animations and legacy in user_animations:
                    user_animations[current] = user_animations[legacy]
                if legacy not in user_animations and current in user_animations:
                    user_animations[legacy] = user_animations[current]
            manifest["animations"] = {**defaults, **user_animations}
        else:
            manifest["animations"] = defaults.copy()
        if not isinstance(data.get("animation_groups"), dict):
            manifest["animation_groups"] = {}
        return manifest

    def _print_manifest_debug(self, path: Path, manifest: dict[str, Any]) -> None:
        if self._manifest_log_printed:
            return
        animations = manifest.get("animations", {})
        action_count = len(animations) if isinstance(animations, dict) else 0
        print(
            "[Daniya] manifest loaded "
            f"path={path} exists={path.exists()} asset_dir={self.active_asset_dir()} "
            f"actions={action_count}"
        )
        self._manifest_log_printed = True

    def _state_keys(self, state: str) -> list[str]:
        aliases = ACTION_ALIASES.get(state, (state,))
        keys: list[str] = []
        for key in aliases:
            if key not in keys:
                keys.append(key)
        return keys

    def _animation_groups_for_state(self, state: str) -> list[tuple[float, list[Path]]]:
        manifest_groups = self.manifest().get("animation_groups", {})
        if not isinstance(manifest_groups, dict):
            return []

        candidates: Any = None
        for key in self._state_keys(state):
            value = manifest_groups.get(key)
            if isinstance(value, list):
                candidates = value
                break
        if not isinstance(candidates, list):
            return []

        groups: list[tuple[float, list[Path]]] = []
        for item in candidates:
            if not isinstance(item, dict) or item.get("enabled", True) is False:
                continue
            try:
                weight = float(item.get("weight", 0))
            except (TypeError, ValueError):
                weight = 0.0
            if weight <= 0:
                continue

            raw_frames = item.get("frames", [])
            if isinstance(raw_frames, str):
                refs = [raw_frames]
            elif isinstance(raw_frames, list):
                refs = [str(ref) for ref in raw_frames if str(ref).strip()]
            else:
                refs = []

            frames = [path for ref in refs if (path := self._resolve_image_ref(ref)).exists()]
            if frames and str(item.get("pick", "")).lower() in {"one", "single", "random_one"}:
                frames = [random.choice(frames)]
            if frames:
                groups.append((weight, frames))
        return self._filter_groups_for_active_module(state, groups, candidates)

    def _filter_groups_for_active_module(
        self,
        state: str,
        groups: list[tuple[float, list[Path]]],
        raw_groups: list[Any],
    ) -> list[tuple[float, list[Path]]]:
        if state not in {"idle", "talk", "talking", "speaking"}:
            return groups

        active = self.active_action_module()
        filtered: list[tuple[float, list[Path]]] = []
        for parsed, raw in zip(groups, [item for item in raw_groups if isinstance(item, dict) and item.get("enabled", True) is not False]):
            name = str(raw.get("name", ""))
            anchor = str(raw.get("anchor", ""))
            if active == "A_sit_base" and (name.startswith("A_") or anchor == "sit_base"):
                filtered.append(parsed)
            elif active == "B_stand_base_pack" and (name.startswith("B_") or anchor == "stand_base"):
                filtered.append(parsed)
            elif active == "C_sleep_base_pack" and (name.startswith("C_") or anchor == "sleep_base"):
                filtered.append(parsed)
            elif active == "D_special_motion_pack" and (name.startswith("D_") or anchor == "special_base"):
                filtered.append(parsed)
        return filtered or groups
