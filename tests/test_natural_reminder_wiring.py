from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from PySide6.QtWidgets import QApplication
import pytest

from src.app import AppController, ChatWorker


@pytest.fixture()
def mock_app_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> QApplication:
    # Force headless offscreen QPA platform for PySide6
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("DANIYA_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(tmp_path / "relation"))
    
    # Mock first_run_done.json check to bypass first run wizard
    first_run_file = tmp_path / "data" / "first_run_done.json"
    first_run_file.parent.mkdir(parents=True, exist_ok=True)
    first_run_file.write_text('{"first_run_complete": true}', encoding="utf-8")
    
    app = QApplication.instance() or QApplication(sys.argv)
    return app


def test_natural_reminder_relative_wiring(mock_app_env, monkeypatch) -> None:
    # Mock ChatWorker to not start background thread in tests
    monkeypatch.setattr(ChatWorker, "start", lambda self: None)

    controller = AppController(mock_app_env)
    
    # Spy on window.speak
    spoken_text = []
    monkeypatch.setattr(controller.window, "speak", lambda text: spoken_text.append(text))

    # Base time context
    base_time = datetime(2026, 5, 24, 12, 0, 0)

    # 1. Test instant creation
    controller.send_message("十分钟后提醒我喝水", base_time=base_time)
    assert len(controller.reminder_manager.records()) == 1
    assert controller.reminder_manager.records()[0]["text"] == "喝水"
    assert "12:10" in spoken_text[-1]
    assert controller.worker is None

    # 2. Test normal chat fall through
    controller.send_message("帮我分析一下提醒系统怎么写", base_time=base_time)
    assert controller.worker is not None  # Started background chat worker
    assert len(controller.reminder_manager.records()) == 1

    # 3. Test ambiguous confirmation loop
    spoken_text.clear()
    controller.send_message("一会儿提醒我睡觉", base_time=base_time)
    assert len(controller.reminder_manager.records()) == 1
    assert controller.pending_reminder_result is not None
    assert "时间还不够明确" in spoken_text[-1]

    # Provide the time
    controller.send_message("十分钟后", base_time=base_time)
    assert len(controller.reminder_manager.records()) == 2
    assert controller.reminder_manager.records()[1]["text"] == "睡觉"
    assert controller.pending_reminder_result is None
    assert "12:10" in spoken_text[-1]

    # 4. Test mixed intent confirm loop (which is treated as ambiguous because it sets scheduled_at to None)
    spoken_text.clear()
    controller.send_message("十分钟后提醒我复习，然后帮我写代码", base_time=base_time)
    assert len(controller.reminder_manager.records()) == 2
    assert controller.pending_reminder_result is not None
    assert "时间还不够明确" in spoken_text[-1]

    # Provide the time
    controller.send_message("十分钟后", base_time=base_time)
    assert len(controller.reminder_manager.records()) == 3
    assert controller.reminder_manager.records()[2]["text"] == "复习"
    assert controller.pending_reminder_result is None
    assert "12:10" in spoken_text[-1]

    # 5. Test cancellation
    spoken_text.clear()
    controller.send_message("一会儿提醒我吃药", base_time=base_time)
    assert controller.pending_reminder_result is not None
    controller.send_message("算了", base_time=base_time)
    assert controller.pending_reminder_result is None
    assert "不记下了" in spoken_text[-1]
    assert len(controller.reminder_manager.records()) == 3

    # 6. Test with switch natural_reminder_enabled set to False
    controller.app_config["natural_reminder_enabled"] = False

    # Send a clear reminder text. It should bypass parsing and go to LLM (i.e. start worker).
    controller.worker = None
    controller.send_message("十分钟后提醒我喝水", base_time=base_time)
    assert controller.worker is not None  # Bypassed reminder service, fell back to ChatWorker
    assert len(controller.reminder_manager.records()) == 3  # No new records added

    # Send an ambiguous reminder text. It should not enter pending state.
    controller.worker = None
    controller.pending_reminder_result = None
    controller.send_message("一会儿提醒我喝水", base_time=base_time)
    assert controller.worker is not None
    assert controller.pending_reminder_result is None

    # If there was a pending result and switch is set to False, sending a message clears it
    controller.app_config["natural_reminder_enabled"] = True
    spoken_text.clear()
    controller.send_message("一会儿提醒我睡觉", base_time=base_time)
    assert controller.pending_reminder_result is not None

    controller.app_config["natural_reminder_enabled"] = False
    controller.worker = None
    controller.send_message("确认", base_time=base_time)
    assert controller.pending_reminder_result is None
    assert controller.worker is not None  # Bypassed and went to ChatWorker

    # 7. Technical question check when enabled
    controller.app_config["natural_reminder_enabled"] = True
    controller.worker = None
    controller.pending_reminder_result = None
    controller.send_message("Python中的定时器怎么实现", base_time=base_time)
    assert controller.worker is not None  # Goes to LLM
    assert controller.pending_reminder_result is None

    # Technical question check when disabled
    controller.app_config["natural_reminder_enabled"] = False
    controller.worker = None
    controller.pending_reminder_result = None
    controller.send_message("Python中的定时器怎么实现", base_time=base_time)
    assert controller.worker is not None  # Goes to LLM
    assert controller.pending_reminder_result is None
