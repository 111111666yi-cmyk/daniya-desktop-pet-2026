from __future__ import annotations

from src.notes_manager import NotesManager


class FakeConfigManager:
    def __init__(self, data_dir):
        self.data_dir = data_dir


def test_notes_manager_clear_removes_manual_memory_notes(tmp_path):
    manager = NotesManager(FakeConfigManager(tmp_path / "data"))
    assert manager.append("喜欢安静陪伴") is True
    assert "喜欢安静陪伴" in manager.path.read_text(encoding="utf-8")

    manager.clear()

    assert manager.path.exists()
    assert manager.path.read_text(encoding="utf-8") == ""
