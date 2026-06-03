from __future__ import annotations

from datetime import datetime
from src.config_manager import ConfigManager
from src.reminder_manager import ReminderManager
from src.natural_reminder_service import NaturalReminderService

def test_natural_reminder_service(tmp_path, monkeypatch) -> None:
    # Set up config manager using temp path as DANIYA_RUNTIME_ROOT to isolate test write operations
    monkeypatch.setenv("DANIYA_RUNTIME_ROOT", str(tmp_path))
    config = ConfigManager()

    reminder_mgr = ReminderManager(config)
    # Stop timer in test to prevent event loop issues
    reminder_mgr.timer.stop()

    service = NaturalReminderService(reminder_mgr)
    base = datetime(2026, 5, 24, 12, 0, 0)

    # 1. Successful instant reminder
    ok, reply, res = service.process_chat_message("十分钟后提醒我喝水", base_time=base)
    assert ok is True
    assert "喝水" in reply
    assert "12:10" in reply
    assert res is not None
    assert res.ok
    assert res.kind == "relative"

    records = reminder_mgr.records()
    assert len(records) == 1
    assert records[0]["text"] == "喝水"
    assert records[0]["time"] == "2026-05-24 12:10"

    # 2. Ambiguous need confirm
    ok, reply, res = service.process_chat_message("一会儿提醒我喝水", base_time=base)
    assert ok is True
    assert "时间太模糊" in reply
    assert res is not None
    assert res.need_confirm

    # Reminders count should still be 1 (ambiguous was not added)
    assert len(reminder_mgr.records()) == 1

    # 3. Non-reminder intent
    ok, reply, res = service.process_chat_message("帮我分析一下提醒系统怎么写", base_time=base)
    assert ok is False
    assert reply == ""
