import pytest
from unittest.mock import Mock, patch
from src.animation_manager import AnimationManager
from src.state_manager import StateManager
from src.action_manifest import ActionManifest

@pytest.fixture
def anim_mgr():
    from PySide6.QtCore import QObject
    window = QObject()
    asset_manager = Mock()
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
