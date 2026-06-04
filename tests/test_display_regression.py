import json
import sys

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication

from src.asset_manager import AssetManager
from src.pet_window import PetWindow


def _app():
    return QApplication.instance() or QApplication(sys.argv)


def _close_window(app, window):
    window.close()
    window.deleteLater()
    app.processEvents()


def test_pet_window_offscreen_position_falls_back_to_visible_right(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setattr("src.utils.runtime_root", lambda: tmp_path)
    app = _app()
    config = {
        "window": {"start_x": 999999, "start_y": 999999, "always_on_top": False, "show_input": True},
        "pet": {"pet_height": 96, "target_height": 96},
        "ui": {"bubble_max_width": 300, "input_min_width": 180},
    }
    window = PetWindow(AssetManager(config), config)
    try:
        window.show_at_config_position()
        app.processEvents()
        bounds = window._desktop_bounds()
        assert window.isVisible()
        assert window.geometry().intersected(bounds).width() >= window.width() * 0.85
        assert window.geometry().intersected(bounds).height() >= window.height() * 0.85
        assert config["window"]["start_x"] == 999999
        assert config["window"]["start_y"] == 999999
        state = json.loads((tmp_path / "data" / "window_state.json").read_text(encoding="utf-8"))
        assert state["x"] == window.x()
        assert state["y"] == window.y()
        assert window.image_label.pixmap() is not None
        assert not window.image_label.pixmap().isNull()
    finally:
        _close_window(app, window)


def test_pet_window_clamps_all_positions_fully_inside_screen(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = _app()
    config = {
        "window": {"start_x": 100, "start_y": 100, "always_on_top": False, "show_input": True},
        "pet": {"pet_height": 96, "target_height": 96},
        "ui": {"bubble_max_width": 300, "input_min_width": 180},
    }
    window = PetWindow(AssetManager(config), config)
    try:
        window.show_at_config_position()
        app.processEvents()
        bounds = window._desktop_bounds()
        for requested in (
            QPoint(-999999, -999999),
            QPoint(999999, 999999),
            QPoint(bounds.left() - window.width(), bounds.center().y()),
            QPoint(bounds.right() + window.width(), bounds.center().y()),
        ):
            clamped = window._clamped_position(requested)
            assert bounds.contains(QRect(clamped, window.size()))
    finally:
        _close_window(app, window)


def test_pet_window_edge_peek_keeps_only_visible_strip_on_left_and_right(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = _app()
    config = {
        "window": {"start_x": 100, "start_y": 100, "always_on_top": False, "show_input": True},
        "pet": {"pet_height": 96, "target_height": 96, "edge_peek_enabled": True},
        "ui": {"bubble_max_width": 300, "input_min_width": 180},
    }
    window = PetWindow(AssetManager(config), config)
    try:
        window.show_at_config_position()
        app.processEvents()
        bounds = window._desktop_bounds()
        visible = 32
        for side in ("left", "right"):
            pos = window._docked_position(side, visible=visible)
            exposed = QRect(pos, window.size()).intersected(bounds)
            assert exposed.width() == visible
            assert exposed.height() == window.height()
    finally:
        _close_window(app, window)


def test_pet_window_input_can_be_restored_after_hidden_config(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = _app()
    config = {
        "window": {"start_x": 100, "start_y": 100, "always_on_top": False, "show_input": False},
        "pet": {"pet_height": 96, "target_height": 96},
        "ui": {"bubble_max_width": 300, "input_min_width": 180},
    }
    window = PetWindow(AssetManager(config), config)
    try:
        window.show_at_config_position()
        app.processEvents()
        assert not window.input_box.isVisible()

        window.set_input_visible(True)
        app.processEvents()
        assert window.input_box.isVisible()
        assert window.input_box.line_edit.isVisible()

        window.set_input_visible(False)
        app.processEvents()
        assert not window.input_box.isVisible()
    finally:
        _close_window(app, window)


def test_pet_window_drag_cannot_leave_screen(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = _app()
    config = {
        "window": {"start_x": 100, "start_y": 100, "always_on_top": False, "show_input": True},
        "pet": {"pet_height": 96, "target_height": 96},
        "ui": {"bubble_max_width": 300, "input_min_width": 180},
    }
    window = PetWindow(AssetManager(config), config)
    try:
        window.show_at_config_position()
        app.processEvents()
        window._start_drag(QPoint(100, 100))
        window._drag(QPoint(999999, 999999))
        bounds = window._desktop_bounds()
        assert bounds.contains(window.geometry())
    finally:
        _close_window(app, window)


def test_v0415_actions_fallback_to_v041_playable_states(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = _app()
    config = {"window": {"always_on_top": False}, "pet": {"pet_height": 96, "target_height": 96}, "ui": {}}
    window = PetWindow(AssetManager(config), config)
    try:
        window.set_pet_state("soft_idle")
        assert window.animation_manager.current_state == "idle"

        window.set_pet_state("close_idle")
        assert window.animation_manager.current_state == "happy"

        window.set_pet_state("bubble")
        assert window.animation_manager.current_state == "happy"

        window.set_pet_state("look_away")
        assert window.animation_manager.current_state == "idle"

        window.set_pet_state("drag")
        assert window.animation_manager.current_state == "dragging"
    finally:
        _close_window(app, window)


def test_missing_extended_action_frames_fallback_to_existing_images():
    manager = AssetManager({"pet": {"pet_height": 96, "target_height": 96}})
    for action in ("soft_idle", "close_idle", "bubble", "look_away", "idle", "talk", "clicked", "drag", "remind"):
        frames = manager.frames_for_state(action)
        assert frames
        assert all(path.exists() for path in frames)
