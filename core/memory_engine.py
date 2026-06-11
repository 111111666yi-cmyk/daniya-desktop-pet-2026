from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from src.utils import runtime_root
from src.atomic_io import atomic_write_text
from src.jsonl_utils import append_json_line, read_json_lines, rotate_json_lines

# Memory reads, appends, and replacements share one lock so partial content
# cannot be mistaken for corrupt user data.
_file_lock = threading.RLock()
logger = logging.getLogger(__name__)

KEY_PHRASES = ["抱抱", "我不会先走", "我收着了", "我都懂", "归期到了", "那根弦松了一点"]
LORE_KEYWORDS = {
    "birthday_sovereignty": ["生日", "橘子蛋糕", "跳跳糖", "彩虹豆", "咔啦咔啦"],
    "bubble_symbol": ["泡泡", "温柔漏一地", "碎了"],
    "void_and_goodbye": ["归期", "再见", "达尼亚", "名字"],
}


def data_root() -> Path:
    return Path(os.environ.get("DANIYA_RELATION_DATA_DIR", runtime_root() / "data" / "daniya_relation"))


def default_user_memory() -> dict[str, Any]:
    return {
        "user_preferences": {
            "likes_short_reply": True,
            "prefers_daniya_reverse_affection": True,
        },
        "important_user_phrases": [],
        "unlocked_lore": [],
        "last_events": [],
    }


def init_memory_if_missing() -> dict[str, Any]:
    memory = load_user_memory()
    save_user_memory(memory)
    return memory


def load_user_memory() -> dict[str, Any]:
    path = data_root() / "user_memory.json"
    return _read_json(path, default_user_memory())


def save_user_memory(memory: dict[str, Any]) -> None:
    _write_json(data_root() / "user_memory.json", _normalize_memory(memory))


def clear_user_memory() -> dict[str, Any]:
    memory = default_user_memory()
    save_user_memory(memory)
    return memory


def update_memory_from_interaction(user_text: str, event: dict[str, Any] | None = None) -> dict[str, Any]:
    with _file_lock:
        memory = load_user_memory()
        for phrase in KEY_PHRASES:
            if phrase in user_text:
                _append_unique(memory.setdefault("important_user_phrases", []), phrase)
        for lore_id in lore_ids_from_text(user_text):
            _append_unique(memory.setdefault("unlocked_lore", []), lore_id)
        if event:
            unlocks = event.get("unlock_lore") or event.get("lore_fragment") or []
            if isinstance(unlocks, str):
                unlocks = [unlocks]
            if isinstance(unlocks, list):
                for item in unlocks:
                    _append_unique(memory.setdefault("unlocked_lore", []), str(item))
            event_id = event.get("id")
            if event_id:
                _append_recent(memory.setdefault("last_events", []), str(event_id), limit=20)
        save_user_memory(memory)
        return memory


def unlock_lore_fragments(fragment_ids: list[str] | set[str] | tuple[str, ...]) -> dict[str, Any]:
    with _file_lock:
        memory = load_user_memory()
        for fragment_id in fragment_ids:
            _append_unique(memory.setdefault("unlocked_lore", []), str(fragment_id))
        save_user_memory(memory)
        return memory


def lore_ids_from_text(user_text: str) -> list[str]:
    if not user_text:
        return []
    found: list[str] = []
    for lore_id, keywords in LORE_KEYWORDS.items():
        if any(keyword in user_text for keyword in keywords):
            found.append(lore_id)
    return found


_MAX_EVENT_LOG_BYTES = 512 * 1024  # 512 KB
_KEEP_EVENT_LOG_BYTES = 256 * 1024


def append_event_log(record: dict[str, Any]) -> None:
    path = data_root() / "event_log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(record)
    record.setdefault("timestamp", datetime.now().isoformat(timespec="seconds"))
    with _file_lock:
        if append_json_line(path, record):
            rotate_json_lines(path, _MAX_EVENT_LOG_BYTES, _KEEP_EVENT_LOG_BYTES)


def _rotate_event_log(path: Path) -> None:
    rotate_json_lines(path, _MAX_EVENT_LOG_BYTES, _KEEP_EVENT_LOG_BYTES)


def load_event_log(limit: int | None = None) -> list[dict[str, Any]]:
    # [CHANGE-005-FIX] 优先读 JSONL，兼容旧 JSON 格式
    jsonl_path = data_root() / "event_log.jsonl"
    json_path = data_root() / "event_log.json"
    events: list[dict[str, Any]] = []
    # 先读旧格式
    if json_path.exists():
        old = _read_json(json_path, [])
        if isinstance(old, list):
            events.extend(old)
    # 再读新格式
    if jsonl_path.exists():
        with _file_lock:
            events.extend(read_json_lines(jsonl_path, limit=limit))
    return events[-limit:] if limit is not None and limit > 0 else events


def ensure_relation_files() -> None:
    # [CHANGE-005-FIX] 只确保目录存在，不再无条件重写文件
    data_root().mkdir(parents=True, exist_ok=True)


def _normalize_memory(memory: dict[str, Any]) -> dict[str, Any]:
    default = default_user_memory()
    merged = dict(default)
    merged.update(memory if isinstance(memory, dict) else {})
    if not isinstance(merged.get("user_preferences"), dict):
        merged["user_preferences"] = default["user_preferences"]
    for key in ("important_user_phrases", "unlocked_lore", "last_events"):
        if not isinstance(merged.get(key), list):
            merged[key] = []
    return merged


def _read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    with _file_lock:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            backup = path.with_suffix(path.suffix + f".broken-{datetime.now().strftime('%Y%m%d%H%M%S')}")
            try:
                path.replace(backup)
            except OSError:
                pass
            _write_json_unlocked(path, fallback)
            return fallback
        except OSError:
            return fallback


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _file_lock:
        _write_json_unlocked(path, value)


def _write_json_unlocked(path: Path, value: Any) -> None:
    content = json.dumps(value, ensure_ascii=False, indent=2)
    if not atomic_write_text(path, content):
        logger.warning("memory_write_failed file=%s", path.name)


def _append_unique(items: list[Any], value: str) -> None:
    if value and value not in items:
        items.append(value)


def _append_recent(items: list[Any], value: str, limit: int) -> None:
    items.append(value)
    del items[:-limit]
