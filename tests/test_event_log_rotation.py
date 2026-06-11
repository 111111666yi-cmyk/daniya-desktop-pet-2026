from __future__ import annotations

from pathlib import Path

from core import memory_engine


def test_event_log_rotates_and_limit_reads_recent_records(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(memory_engine, "_MAX_EVENT_LOG_BYTES", 2400)
    monkeypatch.setattr(memory_engine, "_KEEP_EVENT_LOG_BYTES", 1400)

    for index in range(80):
        memory_engine.append_event_log({"index": index, "payload": "x" * 80})

    path = tmp_path / "event_log.jsonl"
    recent = memory_engine.load_event_log(limit=5)

    assert path.stat().st_size <= 2400
    assert [record["index"] for record in recent] == [75, 76, 77, 78, 79]
    assert not path.with_suffix(".jsonl.tmp").exists()


def test_event_log_skips_half_written_line(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(tmp_path))
    memory_engine.append_event_log({"index": 1})
    with (tmp_path / "event_log.jsonl").open("a", encoding="utf-8") as file:
        file.write('{"index":')

    records = memory_engine.load_event_log(limit=5)
    assert [record["index"] for record in records] == [1]


def test_event_log_append_failure_does_not_crash(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("DANIYA_RELATION_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(memory_engine, "append_json_line", lambda *_args, **_kwargs: False)

    memory_engine.append_event_log({"index": 1})

    assert memory_engine.load_event_log() == []
