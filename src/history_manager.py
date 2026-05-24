from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config_manager import ConfigManager


class HistoryManager:
    def __init__(self, config_manager: ConfigManager) -> None:
        self.path = config_manager.data_dir / "chat_history.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def append(self, user_text: str, assistant_text: str, source: str) -> dict[str, str]:
        record = {
            "id": uuid4().hex,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "user": user_text,
            "assistant": assistant_text,
            "source": source,
        }
        with self.path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    def records(self) -> list[dict[str, Any]]:
        output: list[dict[str, Any]] = []
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return output

        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                output.append(record)
        return output

    def delete(self, record_id: str) -> None:
        remaining = [record for record in self.records() if record.get("id") != record_id]
        self._rewrite(remaining)

    def recent_messages(self, limit: int) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        for record in self.records()[-limit:]:
            user_text = str(record.get("user", "")).strip()
            assistant_text = str(record.get("assistant", "")).strip()
            if user_text:
                messages.append({"role": "user", "content": user_text})
            if assistant_text:
                messages.append({"role": "assistant", "content": assistant_text})
        return messages

    def clear_short_context(self) -> None:
        # Short context is derived from the JSONL file at request time.
        # Keeping this method explicit makes prompt-reset behavior obvious.
        return

    def _rewrite(self, records: list[dict[str, Any]]) -> None:
        with self.path.open("w", encoding="utf-8") as file:
            for record in records:
                file.write(json.dumps(record, ensure_ascii=False) + "\n")

