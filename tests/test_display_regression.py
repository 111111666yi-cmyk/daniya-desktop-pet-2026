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


def test_pet_window_snap_drag_path_uses_edge_peek_position(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = _app()
    config = {
        "window": {"start_x": 100, "start_y": 100, "always_on_top": False, "show_input": True},
        "pet": {"pet_height": 96, "target_height": 96, "edge_peek_enabled": True},
        "ui": {"bubble_max_width": 300, "input_min_width": 180},
        "drag_return_enabled": False,
    }
    window = PetWindow(AssetManager(config), config)
    try:
        window.show_at_config_position()
        app.processEvents()
        bounds = window._desktop_bounds()
        window.move(QPoint(bounds.left() + 2, bounds.center().y()))
        window.behavior_engine.snap_controller.snap_and_save(QPoint(bounds.left() + 2, bounds.center().y()))
        app.processEvents()
        assert window.dock_side == "left"
        assert window.x() < bounds.left()
        assert QRect(window.pos(), window.size()).intersected(bounds).width() >= 32
    finally:
        _close_window(app, window)


def test_pet_window_snap_drag_respects_edge_peek_pause(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = _app()
    config = {
        "window": {"start_x": 100, "start_y": 100, "always_on_top": False, "show_input": True},
        "pet": {"pet_height": 96, "target_height": 96, "edge_peek_enabled": True},
        "ui": {"bubble_max_width": 300, "input_min_width": 180},
        "drag_return_enabled": False,
    }
    window = PetWindow(AssetManager(config), config)
    try:
        window.show_at_config_position()
        app.processEvents()
        bounds = window._desktop_bounds()
        window.edge_peek_allowed_callback = lambda: False
        window.move(QPoint(bounds.left() + 2, bounds.center().y()))
        window.behavior_engine.snap_controller.snap_and_save(QPoint(bounds.left() + 2, bounds.center().y()))
        app.processEvents()
        assert window.dock_side is None
        assert window.x() == bounds.left()
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


def test_pet_window_supports_negative_origin_virtual_desktop(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = _app()
    config = {
        "window": {"start_x": 100, "start_y": 100, "always_on_top": False, "show_input": False},
        "pet": {"pet_height": 96, "target_height": 96, "edge_peek_enabled": True},
        "ui": {"bubble_max_width": 300, "input_min_width": 180},
    }
    window = PetWindow(AssetManager(config), config)
    virtual_bounds = QRect(-1920, -180, 6400, 2340)
    monkeypatch.setattr(window, "_desktop_bounds", lambda: virtual_bounds)
    try:
        window.resize(256, 304)
        for requested in (
            QPoint(-3000, -500),
            QPoint(6000, 3000),
            QPoint(-1800, 100),
            QPoint(4200, 1500),
        ):
            clamped = window._clamped_position(requested)
            assert virtual_bounds.contains(QRect(clamped, window.size()))

        for side in ("left", "right"):
            docked = window._docked_position(side, visible=32)
            exposed = QRect(docked, window.size()).intersected(virtual_bounds)
            assert exposed.width() == 32
    finally:
        _close_window(app, window)


def test_pet_window_keeps_logical_size_across_mixed_dpi(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = _app()
    config = {
        "window": {"start_x": 100, "start_y": 100, "always_on_top": False, "show_input": False},
        "pet": {"pet_height": 96, "target_height": 96},
        "ui": {"bubble_max_width": 300, "input_min_width": 180},
    }
    window = PetWindow(AssetManager(config), config)
    frame = window.asset_manager.frames_for_state("idle")[0]
    try:
        logical_sizes = []
        for dpr in (1.0, 1.25, 1.5, 2.0):
            monkeypatch.setattr(window, "_current_device_pixel_ratio", lambda value=dpr: value)
            window.clear_render_cache()
            scaled, _, _ = window._get_scaled_pixmap(frame, 96, dpr)
            assert abs(scaled.devicePixelRatio() - dpr) < 0.01
            window.render_pet_pixmap(frame)
            pixmap = window.image_label.pixmap()
            assert pixmap is not None and not pixmap.isNull()
            logical_sizes.append((window.image_label.width(), window.image_label.height()))
        assert len(set(logical_sizes)) == 1
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
