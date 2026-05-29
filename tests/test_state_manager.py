import pytest
from src.state_manager import StateManager

def test_state_manager_init():
    sm = StateManager()
    assert sm.get_state() == "idle"

def test_state_transitions():
    sm = StateManager()
    assert sm.set_state("talking") is True
    assert sm.get_state() == "talking"

def test_interruption_rules():
    sm = StateManager()
    sm.set_state("dragging")
    # while dragging, cannot talk
    assert sm.set_state("talking") is False
    assert sm.get_state() == "dragging"
    
    # can return to idle
    sm.return_to_idle()
    assert sm.get_state() == "idle"

def test_v0415_fallback():
    sm = StateManager()
    # soft_idle falls back to idle
    sm.set_state("soft_idle")
    assert sm.get_state() == "idle"
    
    sm.set_state("bubble")
    assert sm.get_state() == "happy"
