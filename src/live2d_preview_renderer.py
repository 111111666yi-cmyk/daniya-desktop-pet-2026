from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .renderer import PNGFrameRenderer


class Live2DPreviewRenderer:
    """Preview-only renderer that preserves a Live2D-shaped interface.

    This stage keeps PNG as the actual rendering path and treats Live2D data as
    optional state metadata. Missing preview assets always fall back to sprite
    frames so the desktop pet remains usable without additional SDK/runtime
    dependencies.
    """

    def __init__(self, base_dir: Path) -> None:
        self._png = PNGFrameRenderer(base_dir)
        self._base_dir = base_dir
        self._live2d_root = base_dir.parent / "live2d"
        self._bindings = self._load_bindings()
        self._last_state = "idle"
        self._last_binding: dict[str, Any] = {}

    def set_motion_context(self, state_name: str, binding: dict[str, Any] | None = None) -> None:
        self._last_state = state_name
        if isinstance(binding, dict):
            self._last_binding = binding
            return
        self._last_binding = self._bindings.get(state_name, {})

    def render_frame(self, frame_id: str, target_height: int, dpr: float):
        sprite_frame = self._preview_sprite_frame(frame_id)
        return self._png.render_frame(sprite_frame, target_height, dpr)

    def supports_smooth_morph(self) -> bool:
        return False

    def clear_cache(self) -> None:
        self._png.clear_cache()
        self._last_state = "idle"
        self._last_binding = {}

    def _preview_sprite_frame(self, frame_id: str) -> str:
        sprite_ref = str(self._last_binding.get("preview_sprite", "")).strip()
        if sprite_ref and (self._base_dir / sprite_ref).exists():
            return sprite_ref
        return frame_id

    def _load_bindings(self) -> dict[str, dict[str, Any]]:
        if not self._live2d_root.exists():
            return {}
        for model_dir in sorted(path for path in self._live2d_root.iterdir() if path.is_dir()):
            binding_path = model_dir / "bindings.json"
            if not binding_path.exists():
                continue
            try:
                payload = json.loads(binding_path.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError):
                continue
            states = payload.get("states", {})
            if isinstance(states, dict):
                return {
                    key: value
                    for key, value in states.items()
                    if isinstance(value, dict)
                }
        return {}
