from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from PySide6.QtCore import QObject, QTimer, Signal

from .config_manager import ConfigManager


TIME_FORMAT = "%Y-%m-%d %H:%M"


class ReminderManager(QObject):
    reminder_due = Signal(str, str)

    def __init__(self, config_manager: ConfigManager) -> None:
        super().__init__()
        self.config_manager = config_manager
        self.path = config_manager.data_dir / "reminders.json"
        if not self.path.exists():
            self._save([])

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.check_due)
        self.timer.start(30_000)

    def records(self) -> list[dict[str, Any]]:
        data = self.config_manager.load_json(self.path, [])
        if not isinstance(data, list):
            self._save([])
            return []
        return [item for item in data if isinstance(item, dict)]

    def add(self, time_text: str, text: str) -> tuple[bool, str]:
        clean_text = text.strip()
        if not clean_text:
            return False, "……提醒内容是空的，你想让我提醒什么？"
        try:
            reminder_time = datetime.strptime(time_text.strip(), TIME_FORMAT)
        except ValueError:
            return False, "……时间格式写错了。用类似 2026-05-24 21:30 这种格式。"

        records = self.records()
        records.append(
            {
                "id": uuid4().hex,
                "time": reminder_time.strftime(TIME_FORMAT),
                "text": clean_text,
                "done": False,
            }
        )
        self._save(records)
        return True, "……记下了。到时候别装作看不见。"

    def mark_done(self, reminder_id: str) -> None:
        records = self.records()
        for record in records:
            if str(record.get("id")) == reminder_id:
                record["done"] = True
                record["notified"] = True
        self._save(records)

    def check_due(self) -> None:
        now = datetime.now()
        records = self.records()
        changed = False
        for record in records:
            if bool(record.get("done")):
                continue
            if bool(record.get("notified")):
                continue
            try:
                due_time = datetime.strptime(str(record.get("time", "")), TIME_FORMAT)
            except ValueError:
                continue
            if due_time <= now:
                record["notified"] = True
                changed = True
                self.reminder_due.emit(str(record.get("id", "")), str(record.get("text", "")))
        if changed:
            self._save(records)

    def _save(self, records: list[dict[str, Any]]) -> None:
        self.config_manager.save_json(self.path, records)
