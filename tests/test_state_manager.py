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


def test_transition_weights_intensity_quiet():
    sm = StateManager()
    w = sm.transition_weights(intensity="quiet")
    assert w["taskbar_sit"] == 0.0
    assert w["idle"] > 0.35


def test_transition_weights_intensity_demo():
    sm = StateManager()
    w = sm.transition_weights(intensity="demo")
    assert w["walking"] > 0.25
    assert w["happy"] > 0.05
    assert w["idle"] < 0.35


def test_transition_weights_intensity_lively_is_baseline():
    sm = StateManager()
    w_lively = sm.transition_weights(intensity="lively")
    w_default = sm.transition_weights()
    assert w_lively == w_default


def test_pick_idle_action_quiet_never_taskbar_sit():
    sm = StateManager()
    actions = set()
    for _ in range(200):
        actions.add(sm.pick_idle_action(intensity="quiet"))
    assert "taskbar_sit" not in actions
