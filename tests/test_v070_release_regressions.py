from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from core import memory_engine, relationship_engine
from core.character_loader import load_character
from core.dialogue_engine import DialogueEngine
from src import pet_window, system_status
from src.config_manager import ConfigManager
from src.daniya_engine_adapter import DaniyaEngineAdapter
from src.reminder_manager import ReminderManager


class TrackingLock:
    def __init__(self) -> None:
        self.entries = 0

    def __enter__(self):
        self.entries += 1
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        return None


def test_relationship_reads_share_the_state_lock(tmp_path, monkeypatch) -> None:
    path = tmp_path / "relationship_state.json"
    path.write_text(json.dumps({"character_id": "daniya", "trust": 73}), encoding="utf-8")
    lock = TrackingLock()
    monkeypatch.setattr(relationship_engine, "_state_lock", lock)

    data = relationship_engine._read_json(path, {})

    assert data["trust"] == 73
    assert lock.entries == 1


def test_memory_and_event_log_reads_share_the_file_lock(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(tmp_path))
    memory_path = tmp_path / "user_memory.json"
    memory_path.write_text(json.dumps(memory_engine.default_user_memory()), encoding="utf-8")
    event_path = tmp_path / "event_log.jsonl"
    event_path.write_text('{"event_id": "qa"}\n', encoding="utf-8")
    lock = TrackingLock()
    monkeypatch.setattr(memory_engine, "_file_lock", lock)

    memory_engine.load_user_memory()
    events = memory_engine.load_event_log()

    assert events == [{"event_id": "qa"}]
    assert lock.entries == 2


def test_memory_read_modify_write_transactions_do_not_lose_updates(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(tmp_path))
    memory_engine.save_user_memory(memory_engine.default_user_memory())
    start = threading.Barrier(3)

    def remember(text: str) -> None:
        start.wait()
        memory_engine.update_memory_from_interaction(text)

    first = threading.Thread(target=remember, args=("抱抱",))
    second = threading.Thread(target=remember, args=("归期到了",))
    first.start()
    second.start()
    start.wait()
    first.join()
    second.join()

    saved = memory_engine.load_user_memory()
    assert set(saved["important_user_phrases"]) >= {"抱抱", "归期到了"}


def test_network_probe_does_not_change_global_socket_timeout(monkeypatch) -> None:
    created: list[SimpleNamespace] = []

    class FakeSocket:
        def __init__(self, *_args, **_kwargs) -> None:
            self.timeout = None
            self.closed = False
            created.append(self)

        def settimeout(self, value: float) -> None:
            self.timeout = value

        def connect(self, _address) -> None:
            return None

        def close(self) -> None:
            self.closed = True

    previous = socket.getdefaulttimeout()
    socket.setdefaulttimeout(7.0)
    monkeypatch.setattr(system_status.socket, "socket", FakeSocket)
    try:
        assert system_status.SystemStatusManager().is_network_online() is True
        assert socket.getdefaulttimeout() == 7.0
        assert created[0].timeout == 1.5
        assert created[0].closed is True
    finally:
        socket.setdefaulttimeout(previous)


def test_non_windows_global_click_probe_is_a_noop(monkeypatch) -> None:
    monkeypatch.setattr(pet_window, "WINDOWS_NATIVE_AVAILABLE", False, raising=False)

    class ForbiddenWindll:
        def __getattr__(self, _name):
            raise AssertionError("Windows APIs must not be touched on non-Windows systems")

    monkeypatch.setattr(pet_window.ctypes, "windll", ForbiddenWindll(), raising=False)
    fake_window = SimpleNamespace(
        app_config={"pet": {"click_to_call_enabled": True}},
        _last_left_button_down=True,
    )

    pet_window.PetWindow._tick_global_click(fake_window)

    assert fake_window._last_left_button_down is False


def test_everyday_question_with_dao_di_is_not_story() -> None:
    engine = DialogueEngine(load_character("daniya"), model_client=lambda _prompt: "先慢慢处理。")

    result = engine._classify_message("我到底该怎么办", {}, None, None, None)

    assert result == "chat"


def test_new_reminder_persists_explicit_notified_state(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("DANIYA_RUNTIME_ROOT", str(tmp_path))
    manager = ReminderManager(ConfigManager())
    manager.timer.stop()

    ok, _message = manager.add("2026-06-05 23:59", "检查发布包")

    assert ok is True
    assert manager.records()[0]["notified"] is False


def test_adapter_serializes_chat_and_physical_engine_transactions() -> None:
    adapter = DaniyaEngineAdapter()
    active = 0
    max_active = 0
    guard = threading.Lock()

    class SlowEngine:
        def handle_user_message(self, _text, context=None):
            nonlocal active, max_active
            with guard:
                active += 1
                max_active = max(max_active, active)
            time.sleep(0.05)
            with guard:
                active -= 1
            return SimpleNamespace(errors=[], action=None, fallback_chain=[])

    adapter.engine = SlowEngine()
    first = threading.Thread(target=adapter.handle_user_text, args=("聊天",))
    second = threading.Thread(target=adapter.handle_physical_event, args=("user_click",))
    first.start()
    second.start()
    first.join()
    second.join()

    assert max_active == 1
