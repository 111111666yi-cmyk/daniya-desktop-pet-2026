from __future__ import annotations

import json
import math
import re
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from core.memory_engine import data_root
from src.atomic_io import atomic_write_text
from src.jsonl_utils import read_json_lines


_lock = threading.RLock()
_WORD_RE = re.compile(r"[A-Za-z0-9_]{2,}")
_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_SENSITIVE_RE = re.compile(
    r"(sk-[A-Za-z0-9_-]{12,}|bearer\s+[A-Za-z0-9._-]{12,}|"
    r"(?:api[_ -]?key|token|secret|password|密码|密钥)\s*[:=：]\s*\S{6,})",
    re.IGNORECASE,
)


class LongTermMemoryStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (data_root() / "long_term_memory.jsonl")

    def records(self, limit: int | None = None) -> list[dict[str, Any]]:
        with _lock:
            return read_json_lines(self.path, limit=limit)

    def remember_exchange(
        self,
        user_text: str,
        assistant_text: str,
        *,
        source: str,
        max_entries: int = 500,
    ) -> dict[str, Any] | None:
        user = _compact_text(user_text, 500)
        assistant = _compact_text(assistant_text, 700)
        if not user or not assistant or _contains_sensitive_value(user):
            return None
        vector = text_vector(f"{user} {assistant}")
        if not vector:
            return None
        record: dict[str, Any] = {
            "id": uuid4().hex,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "user": user,
            "assistant": assistant,
            "source": str(source or "unknown")[:40],
            "vector": vector,
        }
        with _lock:
            records = self.records()
            records.append(record)
            keep = max(1, min(2000, int(max_entries)))
            self._rewrite(records[-keep:])
        return record

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 3,
        min_score: float = 0.08,
    ) -> list[dict[str, Any]]:
        query_vector = text_vector(query)
        if not query_vector:
            return []
        matches: list[dict[str, Any]] = []
        for record in self.records():
            vector = record.get("vector")
            if not isinstance(vector, dict):
                vector = text_vector(
                    f"{record.get('user', '')} {record.get('assistant', '')}"
                )
            score = cosine_similarity(query_vector, vector)
            if score < float(min_score):
                continue
            visible = {
                key: value
                for key, value in record.items()
                if key != "vector"
            }
            visible["score"] = round(score, 4)
            matches.append(visible)
        matches.sort(
            key=lambda item: (
                float(item.get("score", 0.0)),
                str(item.get("timestamp", "")),
            ),
            reverse=True,
        )
        return matches[: max(1, min(10, int(top_k)))]

    def clear(self) -> None:
        with _lock:
            self._rewrite([])

    def _rewrite(self, records: list[dict[str, Any]]) -> None:
        content = "".join(
            json.dumps(record, ensure_ascii=False) + "\n"
            for record in records
        )
        atomic_write_text(self.path, content)


def text_vector(text: str) -> dict[str, float]:
    clean = str(text or "").lower()
    tokens = _WORD_RE.findall(clean)
    cjk = _CJK_RE.findall(clean)
    tokens.extend(cjk)
    tokens.extend(
        "".join(cjk[index : index + 2])
        for index in range(max(0, len(cjk) - 1))
    )
    counts = Counter(token for token in tokens if token.strip())
    return {
        token: round(1.0 + math.log(count), 6)
        for token, count in counts.items()
    }


def cosine_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    if not left or not right:
        return 0.0
    left_values = {
        str(key): _safe_float(value)
        for key, value in left.items()
        if _safe_float(value) > 0
    }
    right_values = {
        str(key): _safe_float(value)
        for key, value in right.items()
        if _safe_float(value) > 0
    }
    if not left_values or not right_values:
        return 0.0
    dot = sum(
        value * right_values.get(key, 0.0)
        for key, value in left_values.items()
    )
    left_norm = math.sqrt(sum(value * value for value in left_values.values()))
    right_norm = math.sqrt(sum(value * value for value in right_values.values()))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def _contains_sensitive_value(text: str) -> bool:
    return bool(_SENSITIVE_RE.search(text))


def _compact_text(value: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
