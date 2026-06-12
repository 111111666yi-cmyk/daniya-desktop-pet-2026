from __future__ import annotations

from unittest.mock import MagicMock

from src import pomodoro as pomodoro_module
from src.pomodoro import PomodoroSession, find_distraction


def test_find_distraction_is_case_insensitive():
    running = {"chrome.exe", "Steam.exe", "python.exe"}
    assert find_distraction(running, ["steam.exe", "vlc.exe"]) == "steam.exe"
    assert find_distraction(running, ["vlc.exe"]) is None


def test_session_completion_clears_state_and_keeps_reward(monkeypatch):
    monkeypatch.setattr(pomodoro_module, "psutil", None)
    session = PomodoroSession({"default_minutes": 25, "reward_affinity": 3})

    events = []
    session.started.connect(lambda m: events.append(("start", m)))
    session.completed.connect(lambda: events.append(("done", None)))

    assert session.start(1) == 1
    assert session.active
    assert session.reward_affinity == 3

    session._finish()
    assert not session.active
    assert events == [("start", 1), ("done", None)]


def test_cancel_does_not_complete_and_is_idempotent():
    session = PomodoroSession({})
    cancelled, completed = [], []
    session.cancelled.connect(lambda: cancelled.append(True))
    session.completed.connect(lambda: completed.append(True))

    session.start(25)
    session.cancel()
    assert not session.active
    assert cancelled == [True]
    assert completed == []

    session.cancel()  # no-op when already inactive
    assert cancelled == [True]


def test_distraction_warns_once_within_cooldown(monkeypatch):
    mock_psutil = MagicMock()
    monkeypatch.setattr(pomodoro_module, "psutil", mock_psutil)
    session = PomodoroSession({"distraction_process_list": ["steam.exe"], "warn_cooldown_sec": 60})
    session.start(25)

    warned = []
    session.distraction_detected.connect(warned.append)

    steam = MagicMock(); steam.info = {"name": "Steam.exe"}
    other = MagicMock(); other.info = {"name": "python.exe"}
    mock_psutil.process_iter.return_value = [steam, other]

    session._scan_bg()
    assert warned == ["steam.exe"]

    session._scan_bg()  # still within cooldown -> no repeat warning
    assert warned == ["steam.exe"]
