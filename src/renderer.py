from __future__ import annotations

from collections import OrderedDict
from pathlib import Path
from typing import Protocol, runtime_checkable

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap


@runtime_checkable
class Renderer(Protocol):
    """Swappable rendering backend for the desktop pet.

    Implementations:
      - PNGFrameRenderer: direct PNG scaling (default)
      - MorphBlendRenderer: PNG + crossfade/breathing/blink (morph_blend_renderer.py)

    Future — Live2D / Cubism SDK:
      Cubism SDK for Native (C++) requires a license from Live2D Inc.
      Free SDK license: personal/indie projects under 10M JPY annual revenue.
      The Python path would use CubismNativePython or pre-rendered sprite sheets
      exported from Cubism Editor. Model files (.moc3, .model3.json, textures)
      must be placed under characters/<id>/live2d/.
      MorphBlendRenderer validates that the Renderer protocol swap works
      end-to-end before committing to the native SDK integration.
    """

    def render_frame(self, frame_id: str, target_height: int, dpr: float) -> QPixmap | None:
        ...

    def supports_smooth_morph(self) -> bool:
        ...

    def clear_cache(self) -> None:
        ...


class PNGFrameRenderer:
    def __init__(self, base_dir: Path, max_cache_entries: int = 512) -> None:
        self._base_dir = base_dir
        self._max_cache_entries = max(1, int(max_cache_entries))
        self._cache: OrderedDict[tuple[str, int, float], QPixmap] = OrderedDict()

    def render_frame(self, frame_id: str, target_height: int, dpr: float) -> QPixmap | None:
        key = (frame_id, target_height, round(dpr, 2))
        cached = self._cache.get(key)
        if cached is not None and not cached.isNull():
            self._cache.move_to_end(key)
            return cached

        path = Path(frame_id)
        if not path.is_absolute():
            path = self._base_dir / frame_id

        original = QPixmap(str(path))
        if original.isNull():
            return None

        physical_height = max(1, int(round(target_height * dpr)))
        physical_width = max(
            1,
            int(round(original.width() * physical_height / max(1, original.height()))),
        )
        scaled = original.scaled(
            physical_width,
            physical_height,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(dpr)

        self._cache[key] = scaled
        self._cache.move_to_end(key)
        if len(self._cache) > self._max_cache_entries:
            self._cache.popitem(last=False)

        return scaled

    def supports_smooth_morph(self) -> bool:
        return False

    def clear_cache(self) -> None:
        self._cache.clear()
