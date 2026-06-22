import pytest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication

from src.animation_manager import AnimationManager
from src.motion_catalog import LocomotionProfile


@pytest.fixture(scope="session", autouse=True)
def qapp():
    import sys

    app = QApplication.instance()
    if not app:
        app = QApplication(sys.argv)
    return app

@pytest.fixture
def anim_mgr():
    from PySide6.QtCore import QObject
    window = QObject()
    asset_manager = Mock()
    asset_manager.locomotion_profile.return_value = LocomotionProfile(start_distance_px=0.0)
    asset_manager.action_config.return_value = None
    asset_manager.select_frames_for_state.return_value = []
    return AnimationManager(window, asset_manager)

def test_play_action(anim_mgr):
    with patch.object(anim_mgr.manifest, 'get_frames') as mock_get_frames:
        mock_get_frames.return_value = ["frame1.png", "frame2.png"]
        anim_mgr.play("talk")
        assert anim_mgr.current_action == "talk"
        assert anim_mgr.current_frames == ["frame1.png", "frame2.png"]

def test_next_frame(anim_mgr):
    anim_mgr.current_action = "talk"
    anim_mgr.current_frames = ["frame1.png", "frame2.png"]
    anim_mgr.frame_index = 0
    
    anim_mgr.next_frame()
    assert anim_mgr.frame_index == 1
    
    anim_mgr.next_frame()
    # It loops
    assert anim_mgr.frame_index == 0

def test_non_looping_ends_in_idle(anim_mgr):
    anim_mgr.current_action = "clicked"
    anim_mgr.current_frames = ["normal2.png"]
    anim_mgr.frame_index = 0
    
    anim_mgr.next_frame()
    # Should stop and return to idle
    assert anim_mgr.current_action == "idle"


def test_walking_loop_uses_clip_timer_instead_of_distance(anim_mgr):
    walk_frames = [f"walk_{idx:02d}.png" for idx in range(1, 25)]
    configs = {
        "walk_start": {"duration_ms": 41, "loop": False},
        "walking": {"duration_ms": 41, "loop": True},
        "idle": {"duration_ms": 41, "loop": True},
    }
    frame_map = {
        "walk_start": ["walk_start_01.png", "walk_start_02.png"],
        "walking": walk_frames,
        "idle": ["idle_01.png"],
    }
    anim_mgr.asset_manager.action_config.side_effect = lambda state: configs.get(state)
    anim_mgr.asset_manager.select_frames_for_state.side_effect = lambda state: frame_map.get(state, [])

    anim_mgr.start_locomotion()
    anim_mgr.update_locomotion(
        step_distance_px=8.0,
        cumulative_distance_px=24.0,
        speed_px_per_s=72.0,
    )

    assert anim_mgr.current_action == "walking"
    assert anim_mgr.frame_index == 0
    assert anim_mgr.animation_timer.isActive() is True
    assert anim_mgr.animation_timer.interval() == 41

    anim_mgr.update_locomotion(
        step_distance_px=8.0,
        cumulative_distance_px=48.0,
        speed_px_per_s=96.0,
    )
    assert anim_mgr.frame_index == 0

    anim_mgr.next_frame()
    assert anim_mgr.frame_index == 1
