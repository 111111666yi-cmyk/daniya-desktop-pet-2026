from __future__ import annotations

from unittest.mock import MagicMock
from src import focus_mode as focus_module
from src.focus_mode import FocusModeManager

def test_manual_focus_mode() -> None:
    manager = FocusModeManager()
    manager.timer.stop()

    emits = []
    manager.focus_state_changed.connect(emits.append)

    assert not manager.is_active
    assert not manager.should_suppress_notifications()

    # 1. Enter focus mode
    manager.enter_focus_mode()
    assert manager.is_active
    assert manager.should_suppress_notifications()
    assert emits == [True]

    # 2. Duplicate enter (should not trigger new emit)
    manager.enter_focus_mode()
    assert len(emits) == 1

    # 3. Exit focus mode
    manager.exit_focus_mode()
    assert not manager.is_active
    assert not manager.should_suppress_notifications()
    assert emits == [True, False]

def test_auto_detect_focus_mode(monkeypatch) -> None:
    mock_psutil = MagicMock()
    monkeypatch.setattr(focus_module, "psutil", mock_psutil)

    manager = FocusModeManager()
    manager.timer.stop()

    emits = []
    manager.focus_state_changed.connect(emits.append)

    manager.set_auto_detect(True)

    # 1. Normal running processes (no games)
    proc1 = MagicMock()
    proc1.info = {"name": "chrome.exe"}
    proc2 = MagicMock()
    proc2.info = {"name": "python.exe"}
    mock_psutil.process_iter.return_value = [proc1, proc2]

    manager._scan_processes_bg()
    assert not manager.is_active
    assert len(emits) == 0

    # 2. Whitelisted game starts running
    game_proc = MagicMock()
    game_proc.info = {"name": "eldenring.exe"}
    mock_psutil.process_iter.return_value = [proc1, proc2, game_proc]

    manager._scan_processes_bg()
    assert manager.is_active
    assert manager.should_suppress_notifications()
    assert emits == [True]

    # 3. Game closes
    mock_psutil.process_iter.return_value = [proc1, proc2]
    manager._scan_processes_bg()
    assert not manager.is_active
    assert emits == [True, False]

def test_empty_process_whitelist_disables_auto_match(monkeypatch) -> None:
    mock_psutil = MagicMock()
    monkeypatch.setattr(focus_module, "psutil", mock_psutil)

    manager = FocusModeManager(process_whitelist=[])
    manager.timer.stop()
    manager.set_auto_detect(True)

    game_proc = MagicMock()
    game_proc.info = {"name": "eldenring.exe"}
    mock_psutil.process_iter.return_value = [game_proc]

    manager._scan_processes_bg()

    assert manager.game_whitelist == set()
    assert not manager.is_active
