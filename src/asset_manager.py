from __future__ import annotations

from pathlib import Path
from typing import Any

from .utils import bundled_root, runtime_root


PET_ID = "daniya_summer"

DEFAULT_MANIFEST: dict[str, Any] = {
    "name": PET_ID,
    "display_name": "达妮娅·夏日形态",
    "default_height": 96,
    "animations": {
        "idle": ["normal1.png"],
        "talking": ["normal1.png", "normal2.png"],
        "hover": ["normal1.png"],
        "clicked": ["normal2.png"],
        "dragging": ["normal2.png"],
        "sleeping": ["normal1.png"],
        "happy": ["normal2.png"],
        "remind": ["normal2.png"],
    },
}


class AssetManager:
    def __init__(self, app_config: dict[str, Any]) -> None:
        self.app_config = app_config
        self.runtime_assets = runtime_root() / "assets"
        self.bundled_assets = bundled_root() / "assets"
        self.pet_id = PET_ID
        self._manifest: dict[str, Any] | None = None
        self._asset_dir: Path | None = None

    def active_asset_dir(self) -> Path:
        if self._asset_dir is not None:
            return self._asset_dir

        candidates = [
            self.runtime_assets / "private" / self.pet_id,
            self.runtime_assets / "private",
            self.runtime_assets / "placeholder" / self.pet_id,
            self.runtime_assets / "placeholder",
            self.bundled_assets / "placeholder" / self.pet_id,
            self.bundled_assets / "placeholder",
        ]
        for candidate in candidates:
            if (candidate / "manifest.json").exists() or (candidate / "normal1.png").exists():
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
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._manifest = {**DEFAULT_MANIFEST, **data}
                    if not isinstance(self._manifest.get("animations"), dict):
                        self._manifest["animations"] = DEFAULT_MANIFEST["animations"]
                    return self._manifest
            except (OSError, json.JSONDecodeError):
                pass
        self._manifest = DEFAULT_MANIFEST.copy()
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
            value = animations.get(state)
            if isinstance(value, list):
                refs = [str(item) for item in value if str(item).strip()]
            elif isinstance(value, str):
                refs = [value]

        if not refs and state in {"normal1", "normal2"}:
            refs = [f"{state}.png"]
        if not refs:
            refs = DEFAULT_MANIFEST["animations"].get(state, ["normal1.png"])

        frames = [path for ref in refs if (path := self._resolve_image_ref(ref)).exists()]
        if frames:
            return frames

        fallback_refs = ["normal1.png", "normal2.png"] if state == "talking" else ["normal1.png"]
        return [path for ref in fallback_refs if (path := self._resolve_image_ref(ref)).exists()]

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
        candidates = [
            active / clean,
            self.runtime_assets / "private" / self.pet_id / clean,
            self.runtime_assets / "private" / clean,
            self.runtime_assets / "placeholder" / self.pet_id / clean,
            self.runtime_assets / "placeholder" / clean,
            self.bundled_assets / "placeholder" / self.pet_id / clean,
            self.bundled_assets / "placeholder" / clean,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return active / clean
