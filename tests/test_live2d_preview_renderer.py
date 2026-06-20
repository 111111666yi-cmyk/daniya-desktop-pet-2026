from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtGui import QColor, QImage, QPixmap

from src.live2d_preview_renderer import Live2DPreviewRenderer
from src.renderer import Renderer


@pytest.fixture(scope="session", autouse=True)
def qapp():
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    return app


def _save_solid_png(path: Path, color: QColor) -> None:
    image = QImage(64, 64, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(color)
    pixmap = QPixmap.fromImage(image)
    pixmap.save(str(path))


def test_live2d_preview_renderer_implements_renderer_protocol(tmp_path: Path) -> None:
    live2d_dir = tmp_path.parent / "live2d" / "example_model"
    live2d_dir.mkdir(parents=True)
    (live2d_dir / "bindings.json").write_text(json.dumps({"states": {}}), encoding="utf-8")
    renderer = Live2DPreviewRenderer(tmp_path)
    assert isinstance(renderer, Renderer)


def test_live2d_preview_renderer_uses_preview_sprite_when_available(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    _save_solid_png(assets_dir / "fallback.png", QColor(255, 0, 0))
    _save_solid_png(assets_dir / "preview.png", QColor(0, 255, 0))

    live2d_dir = tmp_path / "live2d" / "example_model"
    live2d_dir.mkdir(parents=True)
    (live2d_dir / "bindings.json").write_text(
        json.dumps(
            {
                "states": {
                    "idle": {
                        "preview_sprite": "preview.png",
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    renderer = Live2DPreviewRenderer(assets_dir)
    renderer.set_motion_context("idle", {"preview_sprite": "preview.png"})
    pixmap = renderer.render_frame("fallback.png", 48, 1.0)

    assert pixmap is not None
    assert not pixmap.isNull()
    assert abs(pixmap.height() - 48) <= 2


def test_live2d_preview_renderer_falls_back_to_requested_frame(tmp_path: Path) -> None:
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    _save_solid_png(assets_dir / "fallback.png", QColor(255, 0, 0))

    renderer = Live2DPreviewRenderer(assets_dir)
    pixmap = renderer.render_frame("fallback.png", 48, 1.0)

    assert pixmap is not None
    assert not pixmap.isNull()
