from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .config_manager import ConfigManager
from .atomic_io import atomic_write_text
from .jsonl_utils import append_json_line, read_json_lines, rotate_json_lines


MAX_HISTORY_BYTES = 2 * 1024 * 1024
KEEP_HISTORY_BYTES = 1024 * 1024
logger = logging.getLogger(__name__)


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
        if append_json_line(self.path, record):
            rotate_json_lines(self.path, MAX_HISTORY_BYTES, KEEP_HISTORY_BYTES)
        return record

    def records(self, limit: int | None = None) -> list[dict[str, Any]]:
        return read_json_lines(self.path, limit=limit)

    def delete(self, record_id: str) -> None:
        remaining = [record for record in self.records() if record.get("id") != record_id]
        self._rewrite(remaining)

    def recent_messages(self, limit: int) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        for record in self.records(limit=limit):
            user_text = str(record.get("user", "")).strip()
            assistant_text = str(record.get("assistant", "")).strip()
            if user_text:
                messages.append({"role": "user", "content": user_text})
            if assistant_text:
                messages.append({"role": "assistant", "content": assistant_text})
        return messages

    def _tail_records(self, limit: int) -> list[dict[str, Any]]:
        """Return up to the last `limit` records without parsing the whole file.

        The per-message context only needs the newest few records, so reading
        the tail keeps cost bounded even as chat_history.jsonl grows large.
        """
        if limit <= 0:
            return []
        records: list[dict[str, Any]] = []
        for line in self._tail_lines(limit):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
        return records[-limit:]

    def _tail_lines(self, count: int) -> list[str]:
        """Read roughly the last `count` complete lines by seeking from the end."""
        block = 8192
        needed = count + 1  # extra line guards against a partial leading fragment
        try:
            with self.path.open("rb") as file:
                file.seek(0, 2)
                position = file.tell()
                data = b""
                while position > 0 and data.count(b"\n") <= needed:
                    read_size = min(block, position)
                    position -= read_size
                    file.seek(position)
                    data = file.read(read_size) + data
        except OSError:
            return []
        return data.decode("utf-8", errors="ignore").splitlines()[-count:]

    def clear_short_context(self) -> None:
        # Short context is derived from the JSONL file at request time.
        # Keeping this method explicit makes prompt-reset behavior obvious.
        return

    def _rewrite(self, records: list[dict[str, Any]]) -> None:
        content = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
        if not atomic_write_text(self.path, content):
            logger.warning("history_rewrite_failed")

