from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .atomic_io import atomic_write_text


logger = logging.getLogger(__name__)


def append_json_line(path: Path, record: dict[str, Any]) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
        return True
    except OSError as exc:
        logger.warning(
            "jsonl_append_failed file=%s error=%s",
            path.name,
            exc.__class__.__name__,
        )
        return False


def read_json_lines(path: Path, limit: int | None = None) -> list[dict[str, Any]]:
    lines = _tail_text_lines(path, max(0, int(limit))) if limit is not None else _all_text_lines(path)
    output: list[dict[str, Any]] = []
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(record, dict):
            output.append(record)
    return output[-limit:] if limit is not None and limit > 0 else output


def rotate_json_lines(path: Path, max_bytes: int, keep_bytes: int) -> bool:
    try:
        if path.stat().st_size <= max_bytes:
            return False
        lines = _tail_text_lines_by_bytes(path, max(1, keep_bytes))
        return atomic_write_text(path, "".join(line.rstrip("\r\n") + "\n" for line in lines))
    except OSError as exc:
        logger.warning(
            "jsonl_rotation_failed file=%s error=%s",
            path.name,
            exc.__class__.__name__,
        )
        return False


def _all_text_lines(path: Path) -> list[str]:
    try:
        with path.open("r", encoding="utf-8") as file:
            return list(file)
    except OSError:
        return []


def _tail_text_lines(path: Path, limit: int) -> list[str]:
    if limit <= 0:
        return []
    try:
        with path.open("rb") as file:
            file.seek(0, 2)
            position = file.tell()
            blocks: list[bytes] = []
            newline_count = 0
            while position > 0 and newline_count <= limit:
                read_size = min(8192, position)
                position -= read_size
                file.seek(position)
                block = file.read(read_size)
                blocks.append(block)
                newline_count += block.count(b"\n")
            data = b"".join(reversed(blocks))
    except OSError:
        return []
    return data.decode("utf-8", errors="replace").splitlines()[-limit:]


def _tail_text_lines_by_bytes(path: Path, keep_bytes: int) -> list[str]:
    try:
        with path.open("rb") as file:
            file.seek(0, 2)
            size = file.tell()
            start = max(0, size - keep_bytes)
            file.seek(start)
            if start:
                file.readline()
            data = file.read()
    except OSError:
        return []
    return data.decode("utf-8", errors="replace").splitlines()
