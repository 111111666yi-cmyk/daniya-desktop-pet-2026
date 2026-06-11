from __future__ import annotations

import json
from pathlib import Path

from core import memory_engine, relationship_engine
from src import history_manager as history_module
from src.config_manager import ConfigManager
from src.history_manager import HistoryManager


def test_recent_history_uses_tail_reader_and_rotation(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DANIYA_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setattr(history_module, "MAX_HISTORY_BYTES", 900)
    monkeypatch.setattr(history_module, "KEEP_HISTORY_BYTES", 450)
    manager = HistoryManager(ConfigManager())

    for index in range(60):
        manager.append(f"user-{index}", f"assistant-{index}-" + "x" * 60, "test")

    original_read_text = Path.read_text

    def guarded_read_text(path: Path, *args, **kwargs):
        if path == manager.path:
            raise AssertionError("recent history attempted full-file read")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    recent = manager.recent_messages(2)

    assert recent[-2:] == [
        {"role": "user", "content": "user-59"},
        {"role": "assistant", "content": "assistant-59-" + "x" * 60},
    ]
    assert manager.path.stat().st_size <= 900


def test_history_skips_partial_json_line(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DANIYA_RUNTIME_ROOT", str(tmp_path))
    manager = HistoryManager(ConfigManager())
    manager.append("one", "ok", "test")
    with manager.path.open("a", encoding="utf-8") as file:
        file.write('{"broken":')

    assert [record["user"] for record in manager.records()] == ["one"]


def test_atomic_replace_failure_preserves_existing_runtime_json(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DANIYA_RUNTIME_ROOT", str(tmp_path))
    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(tmp_path / "relation"))
    config = ConfigManager()
    target = config.data_dir / "state.json"
    target.write_text(json.dumps({"value": "old"}), encoding="utf-8")

    original_replace = Path.replace

    def fail_tmp_replace(path: Path, target_path: Path):
        if path.suffix == ".tmp":
            raise OSError("read only")
        return original_replace(path, target_path)

    monkeypatch.setattr(Path, "replace", fail_tmp_replace)

    config.save_json(target, {"value": "new"})
    memory_engine.save_user_memory(memory_engine.default_user_memory())
    relationship_engine.save_state({"character_id": "daniya", "trust": 50})

    assert json.loads(target.read_text(encoding="utf-8")) == {"value": "old"}
    assert not target.with_suffix(".json.tmp").exists()
