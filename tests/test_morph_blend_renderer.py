from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from PySide6.QtGui import QPixmap, QImage, QColor
from PySide6.QtCore import Qt

from src.renderer import PNGFrameRenderer, Renderer
from src.morph_blend_renderer import MorphBlendRenderer


@pytest.fixture(scope="session", autouse=True)
def qapp():
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    return app


def _make_solid_pixmap(w: int, h: int, color: QColor) -> QPixmap:
    img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(color)
    return QPixmap.fromImage(img)


@pytest.fixture
def tmp_assets(tmp_path):
    idle_dir = tmp_path / "idle"
    idle_dir.mkdir()
    red = _make_solid_pixmap(64, 64, QColor(255, 0, 0))
    blue = _make_solid_pixmap(64, 64, QColor(0, 0, 255))
    blink = _make_solid_pixmap(64, 64, QColor(0, 255, 0))
    red.save(str(tmp_path / "frame_a.png"))
    blue.save(str(tmp_path / "frame_b.png"))
    blink.save(str(idle_dir / "blink_01.png"))
    return tmp_path


class TestMorphBlendRendererProtocol:
    def test_implements_renderer_protocol(self, tmp_assets):
        r = MorphBlendRenderer(tmp_assets)
        assert isinstance(r, Renderer)

    def test_supports_smooth_morph_returns_true(self, tmp_assets):
        r = MorphBlendRenderer(tmp_assets)
        assert r.supports_smooth_morph() is True

    def test_png_renderer_does_not_support_morph(self, tmp_assets):
        r = PNGFrameRenderer(tmp_assets)
        assert r.supports_smooth_morph() is False


class TestMorphBlendRendererBasicRendering:
    def test_render_frame_returns_pixmap(self, tmp_assets):
        r = MorphBlendRenderer(tmp_assets)
        px = r.render_frame("frame_a.png", 48, 1.0)
        assert px is not None
        assert not px.isNull()

    def test_render_frame_respects_target_height(self, tmp_assets):
        r = MorphBlendRenderer(tmp_assets)
        px = r.render_frame("frame_a.png", 48, 1.0)
        assert abs(px.height() - 48) <= 2

    def test_render_missing_frame_returns_none(self, tmp_assets):
        r = MorphBlendRenderer(tmp_assets)
        px = r.render_frame("nonexistent.png", 48, 1.0)
        assert px is None

    def test_clear_cache_resets_state(self, tmp_assets):
        r = MorphBlendRenderer(tmp_assets)
        r.render_frame("frame_a.png", 48, 1.0)
        r.clear_cache()
        assert r._prev_frame_id is None
        assert r._old_frame_id is None


class TestPNGFrameRendererCache:
    def test_png_renderer_uses_lru_eviction(self, tmp_assets):
        green = _make_solid_pixmap(64, 64, QColor(0, 255, 0))
        green.save(str(tmp_assets / "frame_c.png"))

        renderer = PNGFrameRenderer(tmp_assets, max_cache_entries=2)
        renderer.render_frame("frame_a.png", 48, 1.0)
        renderer.render_frame("frame_b.png", 48, 1.0)
        renderer.render_frame("frame_a.png", 48, 1.0)
        renderer.render_frame("frame_c.png", 48, 1.0)

        assert ("frame_a.png", 48, 1.0) in renderer._cache
        assert ("frame_c.png", 48, 1.0) in renderer._cache
        assert ("frame_b.png", 48, 1.0) not in renderer._cache

    def test_png_renderer_default_cache_can_hold_more_than_legacy_limit(self, tmp_path):
        for idx in range(160):
            frame = _make_solid_pixmap(16, 16, QColor(idx % 255, (idx * 3) % 255, (idx * 7) % 255))
            frame.save(str(tmp_path / f"frame_{idx:03d}.png"))

        renderer = PNGFrameRenderer(tmp_path)
        for idx in range(160):
            renderer.render_frame(f"frame_{idx:03d}.png", 16, 1.0)

        assert len(renderer._cache) == 160

    def test_png_renderer_source_cache_tracks_original_frames_independently(self, tmp_assets):
        renderer = PNGFrameRenderer(tmp_assets, max_cache_entries=1, max_source_entries=2)

        renderer.render_frame("frame_a.png", 48, 1.0)
        renderer.render_frame("frame_b.png", 48, 1.0)
        renderer.render_frame("frame_a.png", 96, 1.0)

        assert len(renderer._cache) == 1
        assert len(renderer._source_cache) == 2
        assert str(tmp_assets / "frame_a.png") in renderer._source_cache
        assert str(tmp_assets / "frame_b.png") in renderer._source_cache

    def test_png_renderer_source_cache_uses_lru_eviction(self, tmp_assets):
        green = _make_solid_pixmap(64, 64, QColor(0, 255, 0))
        green.save(str(tmp_assets / "frame_c.png"))

        renderer = PNGFrameRenderer(tmp_assets, max_cache_entries=4, max_source_entries=2)
        renderer.render_frame("frame_a.png", 48, 1.0)
        renderer.render_frame("frame_b.png", 48, 1.0)
        renderer.render_frame("frame_a.png", 96, 1.0)
        renderer.render_frame("frame_c.png", 48, 1.0)

        assert str(tmp_assets / "frame_a.png") in renderer._source_cache
        assert str(tmp_assets / "frame_c.png") in renderer._source_cache
        assert str(tmp_assets / "frame_b.png") not in renderer._source_cache

    def test_png_renderer_clear_cache_also_drops_source_frames(self, tmp_assets):
        renderer = PNGFrameRenderer(tmp_assets)
        renderer.render_frame("frame_a.png", 48, 1.0)

        assert renderer._cache
        assert renderer._source_cache

        renderer.clear_cache()

        assert not renderer._cache
        assert not renderer._source_cache


class TestMorphBlendRendererCrossfade:
    def test_crossfade_triggers_on_frame_change(self, tmp_assets):
        r = MorphBlendRenderer(tmp_assets)
        r.render_frame("frame_a.png", 48, 1.0)
        r._transition_start = time.monotonic()
        px = r.render_frame("frame_b.png", 48, 1.0)
        assert px is not None
        assert r._old_frame_id == "frame_a.png"

    def test_crossfade_completes_after_duration(self, tmp_assets):
        r = MorphBlendRenderer(tmp_assets)
        r.render_frame("frame_a.png", 48, 1.0)
        r.render_frame("frame_b.png", 48, 1.0)
        r._transition_start = time.monotonic() - 1.0
        px = r.render_frame("frame_b.png", 48, 1.0)
        assert px is not None


class TestMorphBlendRendererBlink:
    def test_blink_frames_discovered(self, tmp_assets):
        r = MorphBlendRenderer(tmp_assets)
        assert len(r._blink_frames) == 1
        assert "blink_01" in r._blink_frames[0]

    def test_blink_does_not_trigger_during_active_animation(self, tmp_assets):
        r = MorphBlendRenderer(tmp_assets)
        r._next_blink_at = time.monotonic() - 1.0
        r.render_frame("frame_a.png", 48, 1.0)
        blink_id = r._check_blink(time.monotonic())
        assert blink_id is None

    def test_blink_triggers_after_stable_period(self, tmp_assets):
        r = MorphBlendRenderer(tmp_assets)
        r._frame_stable_since = time.monotonic() - 3.0
        r._next_blink_at = time.monotonic() - 0.1
        blink_id = r._check_blink(time.monotonic())
        assert blink_id is not None


class TestMorphBlendRendererBreathing:
    def test_breathing_varies_height(self, tmp_assets):
        r = MorphBlendRenderer(tmp_assets)
        heights = set()
        for i in range(20):
            r._breath_epoch = time.monotonic() - (i * 0.2)
            px = r.render_frame("frame_a.png", 96, 1.0)
            if px:
                heights.add(px.height())
        assert len(heights) >= 2
