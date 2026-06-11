from __future__ import annotations

import os
import stat
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    with tempfile.TemporaryDirectory(prefix="daniya-runtime-") as temp_dir:
        temp = Path(temp_dir)
        runtime = temp / "runtime"
        relation = runtime / "data" / "daniya_relation"
        os.environ["DANIYA_RUNTIME_ROOT"] = str(runtime)
        os.environ["DANIYA_RELATION_DATA_DIR"] = str(relation)

        from PySide6.QtCore import QCoreApplication

        from core import memory_engine, relationship_engine
        from src import history_manager
        from src.atomic_io import atomic_write_json
        from src.config_manager import ConfigManager
        from src.history_manager import HistoryManager
        from src.reminder_manager import ReminderManager
        from src.utils import bundled_root, runtime_root

        app = QCoreApplication.instance() or QCoreApplication([])
        config = ConfigManager()

        broken_config = config.config_dir / "broken.json"
        broken_config.write_text('{"unfinished":', encoding="utf-8")
        recovered = config.load_json(broken_config, {"recovered": True})
        _require(recovered == {"recovered": True}, "bad config JSON did not fall back")
        _require(
            list(config.config_dir.glob("broken.json.broken-*")),
            "bad config JSON was not preserved",
        )

        history_manager.MAX_HISTORY_BYTES = 64 * 1024
        history_manager.KEEP_HISTORY_BYTES = 32 * 1024
        history = HistoryManager(config)
        for index in range(800):
            history.append(f"user-{index}", "x" * 180, "runtime-check")
        _require(history.path.stat().st_size <= history_manager.MAX_HISTORY_BYTES, "history grew past cap")
        _require(history.records(limit=5)[-1]["user"] == "user-799", "history tail read failed")
        with history.path.open("a", encoding="utf-8") as file:
            file.write('{"unfinished":')
        _require(history.records(limit=5)[-1]["user"] == "user-799", "partial history line was not skipped")

        memory_engine._MAX_EVENT_LOG_BYTES = 64 * 1024
        memory_engine._KEEP_EVENT_LOG_BYTES = 32 * 1024
        for index in range(800):
            memory_engine.append_event_log({"index": index, "payload": "x" * 180})
        event_path = relation / "event_log.jsonl"
        _require(event_path.stat().st_size <= memory_engine._MAX_EVENT_LOG_BYTES, "event log grew past cap")
        _require(memory_engine.load_event_log(limit=5)[-1]["index"] == 799, "event log tail read failed")

        memory_engine.save_user_memory({"important_user_phrases": ["test"]})
        _require(
            memory_engine.load_user_memory()["important_user_phrases"] == ["test"],
            "memory state round trip failed",
        )
        memory_path = relation / "user_memory.json"
        memory_path.write_text('{"unfinished":', encoding="utf-8")
        _require(
            isinstance(memory_engine.load_user_memory(), dict),
            "bad memory JSON did not fall back",
        )

        relationship_engine.save_state({"character_id": "daniya", "trust": 55})
        _require(
            relationship_engine.load_state("daniya")["trust"] == 55,
            "relationship state round trip failed",
        )
        relationship_path = relationship_engine.state_path()
        relationship_path.write_text('{"unfinished":', encoding="utf-8")
        _require(
            isinstance(relationship_engine.load_state("daniya"), dict),
            "bad relationship JSON did not fall back",
        )

        reminders = ReminderManager(config, enabled=False)
        reminder_path = config.data_dir / "reminders.json"
        reminders._save([{"time": "2099-01-01 00:00", "text": "test"}])
        _require(config.load_json(reminder_path, [])[0]["text"] == "test", "reminder state round trip failed")

        readonly_path = runtime / "readonly.json"
        _require(atomic_write_json(readonly_path, {"stable": True}), "initial atomic write failed")
        readonly_path.chmod(stat.S_IREAD)
        try:
            atomic_write_json(readonly_path, {"stable": False})
        finally:
            readonly_path.chmod(stat.S_IWRITE | stat.S_IREAD)

        original_override = os.environ.pop("DANIYA_RUNTIME_ROOT")
        original_appdata = os.environ.get("APPDATA")
        original_frozen = getattr(sys, "frozen", None)
        try:
            os.environ["APPDATA"] = str(temp / "appdata")
            sys.frozen = True
            packaged_root = runtime_root()
            _require(packaged_root == runtime_root(), "packaged runtime root was not stable")
            _require(packaged_root != bundled_root(), "packaged mode selected install directory")
        finally:
            os.environ["DANIYA_RUNTIME_ROOT"] = original_override
            if original_appdata is None:
                os.environ.pop("APPDATA", None)
            else:
                os.environ["APPDATA"] = original_appdata
            if original_frozen is None:
                delattr(sys, "frozen")
            else:
                sys.frozen = original_frozen

        app.processEvents()
        print("Runtime data check passed.")
        print("- history_rotation: PASS")
        print("- event_log_rotation: PASS")
        print("- partial_jsonl_recovery: PASS")
        print("- memory_relationship_reminder_atomic_write: PASS")
        print("- bad_json_fallback_and_backup: PASS")
        print("- read_only_write_does_not_crash: PASS")
        print("- packaged_runtime_root: PASS")
        return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Runtime data check failed: {exc.__class__.__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
