from __future__ import annotations

import json
import sys

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication

from src.asset_manager import AssetManager
from src.pet_window import PetWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication(sys.argv)


def _config() -> dict:
    return {
        "window": {
            "start_x": 100,
            "start_y": 100,
            "always_on_top": False,
            "show_input": False,
        },
        "pet": {
            "pet_height": 96,
            "target_height": 96,
            "edge_peek_enabled": False,
        },
        "ui": {"bubble_max_width": 300, "input_min_width": 180},
        "snap_to_edge_enabled": True,
        "snap_margin_px": 24,
        "keep_on_screen_enabled": True,
        "drag_return_enabled": False,
    }


def _close(app: QApplication, window: PetWindow) -> None:
    window.close()
    window.deleteLater()
    app.processEvents()


def test_snap_uses_negative_coordinate_secondary_screen(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr("src.utils.runtime_root", lambda: tmp_path)
    app = _app()
    config = _config()
    window = PetWindow(AssetManager(config), config)
    screens = [QRect(0, 0, 1920, 1040), QRect(-1280, 0, 1280, 1024)]
    monkeypatch.setattr(window, "_screen_geometries", lambda: screens)
    try:
        window.resize(220, 180)
        window.move(QPoint(-1274, 300))
        window.behavior_engine.snap_controller.snap_and_save(QPoint(-1274, 300))

        assert window.x() == -1280
        assert screens[1].contains(window.geometry())
    finally:
        _close(app, window)


def test_saved_position_repairs_after_secondary_screen_is_removed(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr("src.utils.runtime_root", lambda: tmp_path)
    app = _app()
    config = _config()
    window = PetWindow(AssetManager(config), config)
    screens = [QRect(0, 0, 1920, 1040)]
    monkeypatch.setattr(window, "_screen_geometries", lambda: screens)
    try:
        state_path = tmp_path / "data" / "window_state.json"
        state_path.parent.mkdir(parents=True)
        state_path.write_text(
            json.dumps({"x": -1100, "y": 300, "snap": "none"}),
            encoding="utf-8",
        )

        restored = window.behavior_engine.snap_controller.load_window_state()

        assert restored is not None
        assert screens[0].contains(QRect(QPoint(*restored), window.size()))
    finally:
        _close(app, window)


def test_edge_dock_is_released_when_feature_is_disabled(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = _app()
    config = _config()
    config["pet"]["edge_peek_enabled"] = True
    window = PetWindow(AssetManager(config), config)
    screen = QRect(0, 0, 1920, 1040)
    monkeypatch.setattr(window, "_screen_geometries", lambda: [screen])
    try:
        window.resize(220, 180)
        window.dock_side = "left"
        window.move(window._docked_position("left", visible=32))
        assert window.x() < screen.left()

        config["pet"]["edge_peek_enabled"] = False
        window.sync_feature_timers()

        assert window.dock_side is None
        assert screen.contains(window.geometry())
    finally:
        _close(app, window)


def test_screen_change_repair_keeps_window_visible(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr("src.utils.runtime_root", lambda: tmp_path)
    app = _app()
    config = _config()
    window = PetWindow(AssetManager(config), config)
    screen = QRect(0, 0, 1280, 720)
    monkeypatch.setattr(window, "_screen_geometries", lambda: [screen])
    try:
        window.move(-4000, 3000)
        window._repair_after_screen_change()
        app.processEvents()

        assert screen.contains(window.geometry())
    finally:
        _close(app, window)


def test_fast_drag_uses_shorter_bounded_snap_animation(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = _app()
    config = _config()
    config["drag_return_enabled"] = True
    window = PetWindow(AssetManager(config), config)
    try:
        controller = window.behavior_engine.snap_controller
        controller.animate_to(QPoint(300, 200), velocity=0)
        slow_duration = controller._anim.duration()
        controller._anim.stop()

        controller.animate_to(QPoint(300, 200), velocity=3000)
        fast_duration = controller._anim.duration()
        controller._anim.stop()

        assert slow_duration == 300
        assert fast_duration == 150
        assert fast_duration >= 140
    finally:
        _close(app, window)
