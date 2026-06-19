from __future__ import annotations

import math
import random
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPixmap

from .renderer import PNGFrameRenderer


class MorphBlendRenderer:
    """PNG renderer with crossfade blending, breathing, and auto-blink.

    Validates the Renderer protocol swap architecture before real Live2D/Cubism.
    """

    def __init__(self, base_dir: Path) -> None:
        self._png = PNGFrameRenderer(base_dir)
        self._base_dir = base_dir

        self._prev_frame_id: str | None = None
        self._old_frame_id: str | None = None
        self._transition_start: float = 0.0
        self._transition_ms: float = 280.0

        self._breath_epoch: float = time.monotonic()
        self._breath_period: float = 4.0
        self._breath_amplitude: float = 0.012

        self._frame_stable_since: float = time.monotonic()
        self._next_blink_at: float = time.monotonic() + random.uniform(4.0, 8.0)
        self._blink_start: float = 0.0
        self._blinking: bool = False
        self._blink_duration: float = 0.12
        self._blink_frames: list[str] = self._discover_blink_frames()

    def _discover_blink_frames(self) -> list[str]:
        blink_dir = self._base_dir / "idle"
        frames = sorted(blink_dir.glob("blink_*.png"))
        return [str(f) for f in frames] if frames else []

    def render_frame(self, frame_id: str, target_height: int, dpr: float) -> QPixmap | None:
        now = time.monotonic()

        if frame_id != self._prev_frame_id:
            if self._prev_frame_id is not None:
                self._old_frame_id = self._prev_frame_id
                self._transition_start = now
            self._prev_frame_id = frame_id
            self._frame_stable_since = now

        breath_phase = ((now - self._breath_epoch) % self._breath_period) / self._breath_period
        breath_scale = 1.0 + self._breath_amplitude * math.sin(breath_phase * 2 * math.pi)
        adjusted_height = max(1, int(round(target_height * breath_scale)))

        blink_id = self._check_blink(now)

        elapsed_ms = (now - self._transition_start) * 1000
        if self._old_frame_id and elapsed_ms < self._transition_ms and not blink_id:
            progress = elapsed_ms / self._transition_ms
            progress = progress * progress * (3.0 - 2.0 * progress)
            old_px = self._png.render_frame(self._old_frame_id, adjusted_height, dpr)
            new_px = self._png.render_frame(frame_id, adjusted_height, dpr)
            if old_px and new_px:
                return self._blend(old_px, new_px, progress, dpr)
            return new_px or old_px

        render_id = blink_id if blink_id else frame_id
        return self._png.render_frame(render_id, adjusted_height, dpr)

    def _check_blink(self, now: float) -> str | None:
        if not self._blink_frames:
            return None
        stable_seconds = now - self._frame_stable_since
        if stable_seconds < 1.5:
            return None

        if not self._blinking and now >= self._next_blink_at:
            self._blinking = True
            self._blink_start = now

        if self._blinking:
            elapsed = now - self._blink_start
            total = self._blink_duration * len(self._blink_frames)
            if elapsed >= total:
                self._blinking = False
                self._next_blink_at = now + random.uniform(3.0, 7.0)
                return None
            idx = min(int(elapsed / self._blink_duration), len(self._blink_frames) - 1)
            return self._blink_frames[idx]

        return None

    def _blend(self, old_px: QPixmap, new_px: QPixmap, progress: float, dpr: float) -> QPixmap:
        w = max(old_px.width(), new_px.width())
        h = max(old_px.height(), new_px.height())
        result = QPixmap(w, h)
        result.setDevicePixelRatio(dpr)
        result.fill(Qt.GlobalColor.transparent)

        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        painter.setOpacity(1.0 - progress)
        ox = (w - old_px.width()) // 2
        oy = h - old_px.height()
        painter.drawPixmap(ox, oy, old_px)

        painter.setOpacity(progress)
        nx = (w - new_px.width()) // 2
        ny = h - new_px.height()
        painter.drawPixmap(nx, ny, new_px)

        painter.end()
        return result

    def supports_smooth_morph(self) -> bool:
        return True

    def clear_cache(self) -> None:
        self._png.clear_cache()
        self._prev_frame_id = None
        self._old_frame_id = None
        self._blinking = False
