from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from src.app import AppController
from src.settings_window import SettingsWindow
from src.startup_timing import REQUIRED_STARTUP_STAGES, StartupTimer


@pytest.fixture()
def qapp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> QApplication:
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("DANIYA_RUNTIME_ROOT", str(tmp_path / "runtime"))
    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(tmp_path / "relation"))
    return QApplication.instance() or QApplication(sys.argv)


def test_startup_timer_records_only_named_stages_without_sensitive_values():
    timer = StartupTimer(started_at=100.0, detailed=False)
    for offset, stage in enumerate(REQUIRED_STARTUP_STAGES[1:], start=1):
        timer.mark(stage, timestamp=100.0 + offset / 10)
    timer.mark("C:\\Users\\someone\\secret-key", timestamp=200.0)

    snapshot = timer.snapshot()
    summary = timer.format_summary()

    assert [row["stage"] for row in snapshot] == list(REQUIRED_STARTUP_STAGES)
    assert all(row["elapsed_ms"] >= 0 for row in snapshot)
    assert "C:\\Users" not in summary
    assert "secret-key" not in summary


def test_startup_does_not_call_network_and_disabled_services_do_not_poll(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
):
    from src.llm.boundaries import deepseek_api, openai_api
    from src.system_status import SystemStatusManager

    def fail_network(*_args, **_kwargs):
        raise AssertionError("startup attempted network access")

    monkeypatch.setattr(deepseek_api, "chat", fail_network)
    monkeypatch.setattr(deepseek_api, "test_connection", fail_network)
    monkeypatch.setattr(openai_api, "chat", fail_network)
    monkeypatch.setattr(openai_api, "test_connection", fail_network)
    monkeypatch.setattr(SystemStatusManager, "is_network_online", fail_network)

    controller = AppController(qapp)

    assert controller.reminder_manager.timer.isActive()
    assert not controller.idle_manager.timer.isActive()
    assert not controller.time_event_manager.timer.isActive()
    assert not controller.system_status_manager.timer.isActive()
    assert not controller.focus_mode_manager.timer.isActive()
    assert not controller.window.behavior_engine.idle_behavior.timer.isActive()
    assert not controller.window.edge_timer.isActive()
    assert not controller.window.global_click_timer.isActive()
    assert not controller.window.walk_move_timer.isActive()

    controller.show()
    qapp.processEvents()

    assert [row["stage"] for row in controller.startup_timer.snapshot()] == list(REQUIRED_STARTUP_STAGES)
    controller.window.close()


def test_settings_runtime_data_is_loaded_only_after_relevant_tab_opens(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
):
    from src.relationship_state_viewer import RelationshipStateViewer

    calls: list[int | None] = []

    def fake_status(self, event_limit=20):
        calls.append(event_limit)
        return {
            "data_dir": "runtime",
            "exists": True,
            "relationship_state": {},
            "relationship_state_readable": True,
            "relationship_state_error": None,
            "event_log": [],
            "event_log_readable": True,
            "event_log_error": None,
            "user_memory": {},
            "user_memory_readable": True,
            "user_memory_error": None,
        }

    monkeypatch.setattr(RelationshipStateViewer, "status", fake_status)
    controller = AppController(qapp)
    window = SettingsWindow(controller)

    assert calls == []

    relationship_index = next(
        index
        for index in range(window.tabs.count())
        if window.tabs.tabText(index) == "关系与事件"
    )
    window.tabs.setCurrentIndex(relationship_index)
    qapp.processEvents()

    assert calls
    window.close()
    controller.window.close()
