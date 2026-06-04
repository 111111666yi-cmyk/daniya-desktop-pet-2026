from __future__ import annotations
import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from PySide6.QtCore import QPoint, QRect, QCoreApplication
from PySide6.QtWidgets import QWidget

from src.behavior.behavior_config import BehaviorConfig
from src.behavior.interaction_detector import InteractionDetector
from src.behavior.drag_controller import DragController
from src.behavior.snap_controller import SnapController
from src.behavior.idle_behavior import IdleBehavior
from src.behavior.behavior_engine import PetBehaviorEngine


@pytest.fixture(scope="session", autouse=True)
def qapp():
    import sys
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    return app


# ═══════════════════════════════════════════════════════════════════
# BehaviorConfig Tests
# ═══════════════════════════════════════════════════════════════════

class TestBehaviorConfig:
    def test_default_values(self) -> None:
        cfg = BehaviorConfig({})
        assert cfg.behavior_enabled is True
        assert cfg.snap_to_edge_enabled is True
        assert cfg.snap_margin_px == 24
        assert cfg.keep_on_screen_enabled is True
        assert cfg.drag_return_enabled is True
        assert cfg.idle_behavior_enabled is False
        assert cfg.idle_behavior_seconds == 600
        assert cfg.double_click_enabled is True
        assert cfg.long_press_ms == 600

    def test_custom_values(self) -> None:
        custom = {
            "behavior_enabled": False,
            "snap_to_edge_enabled": False,
            "snap_margin_px": 50,
            "keep_on_screen_enabled": False,
            "drag_return_enabled": False,
            "idle_behavior_enabled": False,
            "idle_behavior_seconds": 120,
            "double_click_enabled": False,
            "long_press_ms": 1000,
        }
        cfg = BehaviorConfig(custom)
        assert cfg.behavior_enabled is False
        assert cfg.snap_to_edge_enabled is False
        assert cfg.snap_margin_px == 50
        assert cfg.keep_on_screen_enabled is False
        assert cfg.drag_return_enabled is False
        assert cfg.idle_behavior_enabled is False
        assert cfg.idle_behavior_seconds == 600
        assert cfg.double_click_enabled is False
        assert cfg.long_press_ms == 1000

    def test_type_error_fallbacks(self) -> None:
        bad_values = {
            "snap_margin_px": "invalid",
            "idle_behavior_seconds": "invalid",
            "long_press_ms": "invalid",
        }
        cfg = BehaviorConfig(bad_values)
        assert cfg.snap_margin_px == 24
        assert cfg.idle_behavior_seconds == 600
        assert cfg.long_press_ms == 600


# ═══════════════════════════════════════════════════════════════════
# InteractionDetector Tests
# ═══════════════════════════════════════════════════════════════════

class TestInteractionDetector:
    def test_single_click(self) -> None:
        single_click_mock = MagicMock()
        detector = InteractionDetector(
            on_single_click=single_click_mock
        )
        # Mouse press
        detector.handle_press(QPoint(100, 100))
        assert detector.press_pos == QPoint(100, 100)
        assert detector.click_delay_timer.isActive() is False

        # Mouse release
        detector.handle_release(QPoint(100, 100))
        assert detector.click_delay_timer.isActive() is True

        # Trigger single click timeout manually
        detector._handle_single_click_timeout()
        single_click_mock.assert_called_once()

    def test_double_click(self) -> None:
        double_click_mock = MagicMock()
        single_click_mock = MagicMock()
        detector = InteractionDetector(
            on_single_click=single_click_mock,
            on_double_click=double_click_mock
        )

        # First press/release
        detector.handle_press(QPoint(100, 100))
        detector.handle_release(QPoint(100, 100))
        assert detector.click_delay_timer.isActive() is True

        # Second press/release within double click timeframe
        detector.handle_press(QPoint(100, 100))
        detector.handle_release(QPoint(100, 100))

        assert detector.click_delay_timer.isActive() is False
        double_click_mock.assert_called_once()
        single_click_mock.assert_not_called()

    def test_long_press(self) -> None:
        long_press_mock = MagicMock()
        detector = InteractionDetector(
            on_long_press=long_press_mock
        )
        detector.handle_press(QPoint(100, 100))
        assert detector.long_press_triggered is False

        # Trigger long press timeout manually
        detector._handle_long_press_timeout()
        assert detector.long_press_triggered is True
        long_press_mock.assert_called_once()

        # Release does not trigger clicks
        detector.handle_release(QPoint(100, 100))
        assert detector.long_press_triggered is False

    def test_drag_gesture(self) -> None:
        drag_start_mock = MagicMock()
        drag_mock = MagicMock()
        drag_finish_mock = MagicMock()
        detector = InteractionDetector(
            drag_threshold=8,
            on_drag_start=drag_start_mock,
            on_drag=drag_mock,
            on_drag_finish=drag_finish_mock
        )

        detector.handle_press(QPoint(100, 100))
        assert detector.is_pressed is True
        # Move slightly (within threshold)
        detector.handle_move(QPoint(102, 102))
        assert detector.is_pressed is True
        assert detector.is_dragging is False
        drag_start_mock.assert_not_called()

        # Move beyond threshold
        detector.handle_move(QPoint(110, 110))
        assert detector.is_pressed is True
        assert detector.is_dragging is True
        drag_start_mock.assert_called_once_with(QPoint(100, 100))
        drag_mock.assert_called_with(QPoint(110, 110))

        # Release
        detector.handle_release(QPoint(115, 115))
        assert detector.is_pressed is False
        assert detector.is_dragging is False
        drag_finish_mock.assert_called_once_with(QPoint(115, 115))


# ═══════════════════════════════════════════════════════════════════
# DragController Tests
# ═══════════════════════════════════════════════════════════════════

class TestDragController:
    def test_dragging_state(self) -> None:
        mock_window = MagicMock(spec=QWidget)
        mock_window.pos.return_value = QPoint(50, 50)

        state_changed_mock = MagicMock()
        controller = DragController(mock_window, on_state_changed=state_changed_mock)

        controller.start_drag(QPoint(100, 100))
        state_changed_mock.assert_called_once_with("drag")
        assert controller.drag_start_pos == QPoint(100, 100)
        assert controller.drag_start_window_pos == QPoint(50, 50)

        # Drag to new location
        controller.drag(QPoint(120, 130))
        # Delta is (20, 30), so target window pos is (70, 80)
        mock_window.move.assert_called_with(QPoint(70, 80))

        # Finish drag
        global_pos, velocity = controller.finish_drag(QPoint(120, 130))
        assert global_pos == QPoint(120, 130)


# ═══════════════════════════════════════════════════════════════════
# SnapController Tests
# ═══════════════════════════════════════════════════════════════════

class TestSnapController:
    def test_state_file_path(self, tmp_path) -> None:
        config = BehaviorConfig({})
        mock_window = MagicMock(spec=QWidget)
        controller = SnapController(mock_window, config)
        with patch("src.utils.runtime_root", return_value=tmp_path):
            path = controller.state_file_path()
            assert path == tmp_path / "data" / "window_state.json"

    def test_get_current_snap_state(self) -> None:
        config = BehaviorConfig({})
        mock_window = MagicMock(spec=QWidget)
        mock_window.width.return_value = 100
        mock_window.height.return_value = 100

        controller = SnapController(mock_window, config)
        controller.get_desktop_bounds = MagicMock(return_value=QRect(0, 0, 1920, 1080))

        # Center position
        mock_window.pos.return_value = QPoint(500, 500)
        assert controller.get_current_snap_state() == "none"

        # Left edge
        mock_window.pos.return_value = QPoint(0, 500)
        assert controller.get_current_snap_state() == "left"

        # Right edge
        mock_window.pos.return_value = QPoint(1820, 500)
        assert controller.get_current_snap_state() == "right"

        # Bottom edge
        mock_window.pos.return_value = QPoint(500, 980)
        assert controller.get_current_snap_state() == "bottom"

        # Left bottom
        mock_window.pos.return_value = QPoint(0, 980)
        assert controller.get_current_snap_state() == "left_bottom"

        # Right bottom
        mock_window.pos.return_value = QPoint(1820, 980)
        assert controller.get_current_snap_state() == "right_bottom"

    def test_load_save_window_state(self, tmp_path) -> None:
        config = BehaviorConfig({})
        mock_window = MagicMock(spec=QWidget)
        mock_window.width.return_value = 100
        mock_window.height.return_value = 100

        controller = SnapController(mock_window, config)
        controller.get_desktop_bounds = MagicMock(return_value=QRect(0, 0, 1920, 1080))

        with patch("src.utils.runtime_root", return_value=tmp_path):
            # Save state
            controller.save_window_state(200, 300, "none")

            # Load state
            loaded = controller.load_window_state()
            assert loaded == (200, 300)

            # Save offscreen position (which should fail visibility bounds check on load)
            controller.save_window_state(-500, -500, "none")
            loaded = controller.load_window_state()
            assert loaded is None

    def test_snap_and_save(self) -> None:
        config = BehaviorConfig({
            "snap_to_edge_enabled": True,
            "snap_margin_px": 24,
            "keep_on_screen_enabled": True,
            "drag_return_enabled": False  # Disable return bounce to test immediate snap
        })
        mock_window = MagicMock(spec=QWidget)
        mock_window.width.return_value = 100
        mock_window.height.return_value = 100
        mock_window.pos.return_value = QPoint(10, 500)  # Close to left margin (24px)

        controller = SnapController(mock_window, config)
        controller.get_desktop_bounds = MagicMock(return_value=QRect(0, 0, 1920, 1080))
        controller.save_window_state = MagicMock()

        controller.snap_and_save(QPoint(10, 500))
        # Should snap to x=0
        mock_window.move.assert_called_with(QPoint(0, 500))
        controller.save_window_state.assert_called_with(0, 500, "left")


# ═══════════════════════════════════════════════════════════════════
# IdleBehavior Tests
# ═══════════════════════════════════════════════════════════════════

class TestIdleBehavior:
    def test_idle_check_daytime(self) -> None:
        config = BehaviorConfig({
            "idle_behavior_enabled": True,
            "idle_behavior_seconds": 600
        })
        is_allowed = MagicMock(return_value=True)
        is_night = MagicMock(return_value=False)

        idle = IdleBehavior(config, is_allowed, is_night)

        # Spy signals
        action_received = []
        idle.idle_action_triggered.connect(action_received.append)

        # Test inactive check
        idle.last_activity_time = time.time() - 601
        idle.last_behavior_time = 0.0

        idle._check_idle()
        assert "idle" in action_received

    def test_idle_check_nighttime(self) -> None:
        config = BehaviorConfig({
            "idle_behavior_enabled": True,
            "idle_behavior_seconds": 600
        })
        is_allowed = MagicMock(return_value=True)
        is_night = MagicMock(return_value=True)

        idle = IdleBehavior(config, is_allowed, is_night)

        action_received = []
        idle.idle_action_triggered.connect(action_received.append)

        idle.last_activity_time = time.time() - 601
        idle.last_behavior_time = 0.0

        idle._check_idle()
        assert "sleep" in action_received

    def test_idle_not_allowed(self) -> None:
        config = BehaviorConfig({
            "idle_behavior_enabled": True,
            "idle_behavior_seconds": 600
        })
        is_allowed = MagicMock(return_value=False)
        is_night = MagicMock(return_value=False)

        idle = IdleBehavior(config, is_allowed, is_night)

        action_received = []
        idle.idle_action_triggered.connect(action_received.append)

        idle.last_activity_time = time.time() - 601
        idle.last_behavior_time = 0.0

        idle._check_idle()
        assert not action_received


# ═══════════════════════════════════════════════════════════════════
# PetBehaviorEngine Tests
# ═══════════════════════════════════════════════════════════════════

class TestPetBehaviorEngine:
    def test_engine_initialization_and_action_routing(self) -> None:
        mock_window = MagicMock(spec=QWidget)
        mock_window.pos.return_value = QPoint(100, 100)
        mock_window.width.return_value = 100
        mock_window.height.return_value = 100

        app_config = {
            "behavior_enabled": True,
            "double_click_enabled": True,
            "long_press_ms": 600
        }
        is_allowed = MagicMock(return_value=True)
        is_night = MagicMock(return_value=False)
        speak_mock = MagicMock()

        engine = PetBehaviorEngine(
            window=mock_window,
            app_config=app_config,
            is_allowed_callback=is_allowed,
            is_night_callback=is_night,
            speak_callback=speak_mock
        )

        # Test reload config
        engine.reload_config({
            "behavior_enabled": True,
            "double_click_enabled": False,
            "long_press_ms": 800
        })
        assert engine.config.double_click_enabled is False
        assert engine.detector.long_press_ms == 800

        # Test activity marking
        old_time = engine.idle_behavior.last_activity_time
        time.sleep(0.001)
        engine.mark_activity()
        assert engine.idle_behavior.last_activity_time > old_time

    def test_drag_sets_and_clears_window_drag_start_global(self) -> None:
        mock_window = MagicMock(spec=QWidget)
        mock_window.pos.return_value = QPoint(100, 100)
        mock_window.width.return_value = 100
        mock_window.height.return_value = 100
        mock_window.drag_start_global = None
        mock_window.position_changed = MagicMock()
        mock_window.drag_completed = MagicMock()

        app_config = {
            "behavior_enabled": True,
            "double_click_enabled": True,
            "long_press_ms": 600
        }

        engine = PetBehaviorEngine(
            window=mock_window,
            app_config=app_config,
            is_allowed_callback=lambda: True,
            is_night_callback=lambda: False,
            speak_callback=None
        )

        # Start drag
        engine._handle_drag_start(QPoint(120, 130))
        assert mock_window.drag_start_global == QPoint(120, 130)

        # Finish drag
        engine._handle_drag_finish(QPoint(120, 130))
        assert mock_window.drag_start_global is None
