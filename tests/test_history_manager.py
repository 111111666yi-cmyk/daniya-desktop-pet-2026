from __future__ import annotations

from src.history_manager import HistoryManager


class _StubConfigManager:
    def __init__(self, data_dir):
        self.data_dir = data_dir


def test_recent_messages_returns_tail(tmp_path):
    hm = HistoryManager(_StubConfigManager(tmp_path))
    for i in range(50):
        hm.append(f"u{i}", f"a{i}", "test")

    messages = hm.recent_messages(3)

    # Last 3 records -> 6 alternating user/assistant messages.
    assert [m["content"] for m in messages] == ["u47", "a47", "u48", "a48", "u49", "a49"]


def test_recent_messages_handles_short_and_empty(tmp_path):
    hm = HistoryManager(_StubConfigManager(tmp_path))
    assert hm.recent_messages(5) == []

    hm.append("hello", "......在", "test")
    messages = hm.recent_messages(5)
    assert messages == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "......在"},
    ]
