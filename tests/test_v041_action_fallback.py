import pytest
from src.state_manager import StateManager
from src.action_manifest import ActionManifest
from src.animation_manager import AnimationManager
from unittest.mock import Mock

def test_v0415_action_fallback():
    sm = StateManager()
    
    # soft_idle -> idle
    sm.set_state("soft_idle")
    assert sm.get_state() == "idle"
    
    # close_idle -> happy -> idle (Wait, close_idle maps to happy in StateManager)
    sm.set_state("close_idle")
    assert sm.get_state() == "happy"
    
    # bubble -> happy
    sm.set_state("bubble")
    assert sm.get_state() == "happy"
    
    # look_away -> idle
    sm.set_state("look_away")
    assert sm.get_state() == "idle"
    
def test_fallback_when_action_missing():
    # If a state isn't mapped, it should fallback to idle
    sm = StateManager()
    sm.set_state("unknown_state_123")
    assert sm.get_state() == "idle"
