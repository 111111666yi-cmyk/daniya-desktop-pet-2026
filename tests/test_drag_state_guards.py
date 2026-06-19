from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import Mock

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QApplication, QWidget

from src.app import AppController
from src.asset_manager import AssetManager
from src.behavior.interaction_detector import InteractionDetector
from src.pet_window import PetWindow


def _app() -> QApplication:
    return QApplication.instance() or QApplication(sys.argv)


def test_click_double_click_and_drag_are_mutually_exclusive() -> None:
    app = _app()
    single = Mock()
    double = Mock()
    drag_start = Mock()
    drag_move = Mock()
    drag_finish = Mock()
    detector = InteractionDetector(
        drag_threshold=8,
        on_single_click=single,
        on_double_click=double,
        on_drag_start=drag_start,
        on_drag=drag_move,
        on_drag_finish=drag_finish,
    )

    detector.handle_press(QPoint(10, 10))
    detector.handle_release(QPoint(10, 10))
    detector.handle_press(QPoint(10, 10))
    detector.handle_release(QPoint(10, 10))

    double.assert_called_once_with()
    single.assert_not_called()
    drag_start.assert_not_called()

    detector.handle_press(QPoint(10, 10))
    detector.handle_move(QPoint(30, 10))
    detector.handle_move(QPoint(50, 10))
    detector.handle_release(QPoint(60, 10))
    app.processEvents()

    drag_start.assert_called_once_with(QPoint(10, 10))
    assert drag_move.call_count == 2
    drag_finish.assert_called_once_with(QPoint(60, 10))
    single.assert_not_called()
    assert double.call_count == 1


def test_long_press_release_does_not_emit_click() -> None:
    single = Mock()
    long_press = Mock()
    detector = InteractionDetector(on_single_click=single, on_long_press=long_press)

    detector.handle_press(QPoint(20, 20))
    detector._handle_long_press_timeout()
    detector.handle_release(QPoint(20, 20))

    long_press.assert_called_once_with()
    single.assert_not_called()


def test_input_activity_uses_child_editor_focus_or_text() -> None:
    window = SimpleNamespace(is_input_active=Mock(return_value=True))
    controller = SimpleNamespace(window=window, worker=None, reminder_boxes=[])

    assert AppController._is_feedback_user_busy(controller) is True
    window.is_input_active.assert_called_once_with()


def test_opening_input_releases_edge_dock_without_clearing_text(monkeypatch) -> None:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    app = _app()
    config = {
        "window": {"always_on_top": False, "show_input": False},
        "pet": {"pet_height": 96, "target_height": 96, "edge_peek_enabled": True},
        "ui": {"bubble_max_width": 300, "input_min_width": 180},
    }
    window = PetWindow(AssetManager(config), config)
    try:
        window.show_at_config_position()
        app.processEvents()
        window.dock_side = "left"
        window.move(window._docked_position("left", visible=32))
        window.input_box.line_edit.setText("draft")

        window.set_input_visible(True)
        app.processEvents()

        assert window.dock_side is None
        assert window.input_box.line_edit.text() == "draft"
        assert window.is_input_active()
    finally:
        window.close()


def test_focus_entry_releases_existing_edge_dock() -> None:
    window = SimpleNamespace(release_edge_dock=Mock())
    feedback = Mock()
    controller = SimpleNamespace(
        window=window,
        feedback_coordinator=feedback,
        utility_text=Mock(return_value="focus"),
    )

    AppController._on_focus_state_changed(controller, True)

    window.release_edge_dock.assert_called_once_with()
    feedback.present.assert_called_once()


def test_due_reminder_does_not_change_pet_topmost_setting() -> None:
    app = _app()
    window = QWidget()
    window.always_on_top = False
    window.set_always_on_top = Mock()
    window.animation_manager = SimpleNamespace(trigger_remind=Mock())
    window.speak = Mock()
    controller = SimpleNamespace(
        window=window,
        utility_text=Mock(return_value="reminder"),
        _fire_physical_event=Mock(),
        _tts_play=Mock(),
        _voice_play_event=Mock(),  # [FIX-S2] on_reminder_due 新增语音事件调用
        reminder_boxes=[],
    )

    AppController.on_reminder_due(controller, "reminder-id", "test")
    app.processEvents()

    window.set_always_on_top.assert_not_called()
    box = controller.reminder_boxes.pop()
    assert box.windowFlags() & Qt.WindowType.WindowStaysOnTopHint
    box.finished.disconnect()
    box.close()
    window.close()
