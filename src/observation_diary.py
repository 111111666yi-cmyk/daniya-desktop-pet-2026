from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable

from core.memory_engine import load_event_log
from src.atomic_io import atomic_write_text
from src.jsonl_utils import append_json_line, read_json_lines
from src.utils import runtime_root


ProviderReply = Callable[[str], tuple[str, str] | str]


class ObservationDiary:
    def __init__(
        self,
        provider_reply: ProviderReply,
        *,
        path: Path | None = None,
        event_loader: Callable[..., list[dict[str, Any]]] = load_event_log,
    ) -> None:
        self.provider_reply = provider_reply
        self.path = path or (runtime_root() / "data" / "observation_diary.jsonl")
        self.event_loader = event_loader

    def generate(
        self,
        *,
        days: int = 3,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        generated_at = now or datetime.now()
        recent = recent_events(
            self.event_loader(),
            days=days,
            now=generated_at,
        )
        if not recent:
            return {
                "ok": False,
                "message": f"最近 {max(1, int(days))} 天没有可写入日记的互动事件。",
                "source": "none",
                "event_count": 0,
            }
        prompt = build_diary_prompt(recent, days=days, now=generated_at)
        result = self.provider_reply(prompt)
        if isinstance(result, tuple):
            text = str(result[0]).strip()
            source = str(result[1]).strip()
        else:
            text = str(result).strip()
            source = "model"
        if source not in {"api", "model"} or not text:
            return {
                "ok": False,
                "message": "Provider 未真实返回日记；本地 fallback 不会被保存为观察日记。",
                "source": source or "unknown",
                "event_count": len(recent),
            }
        record = {
            "timestamp": generated_at.isoformat(timespec="seconds"),
            "period_start": (generated_at - timedelta(days=max(1, int(days)))).isoformat(
                timespec="seconds"
            ),
            "period_end": generated_at.isoformat(timespec="seconds"),
            "event_count": len(recent),
            "source": source,
            "text": text[:4000],
        }
        if not append_json_line(self.path, record):
            return {
                "ok": False,
                "message": "日记已生成，但本地保存失败。",
                "source": source,
                "event_count": len(recent),
            }
        return {
            "ok": True,
            "message": "观察日记已生成并保存在本机。",
            "source": source,
            "event_count": len(recent),
            "record": record,
        }

    def records(self, limit: int | None = None) -> list[dict[str, Any]]:
        return read_json_lines(self.path, limit=limit)

    def clear(self) -> None:
        atomic_write_text(self.path, "")


def recent_events(
    events: list[dict[str, Any]],
    *,
    days: int,
    now: datetime,
) -> list[dict[str, Any]]:
    cutoff = now - timedelta(days=max(1, min(30, int(days))))
    output: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        timestamp = _parse_timestamp(event.get("timestamp"))
        if timestamp is None or timestamp < cutoff or timestamp > now:
            continue
        output.append(event)
    return output[-80:]


def build_diary_prompt(
    events: list[dict[str, Any]],
    *,
    days: int,
    now: datetime,
) -> str:
    lines = [
        "请以达妮娅第一人称写一篇观察日记。",
        f"时间范围：截至 {now.isoformat(timespec='minutes')} 的最近 {max(1, int(days))} 天。",
        "要求：只依据下面的互动记录；不虚构；不使用工程、测试、系统或上帝视角措辞；",
        "不要解释生成过程；不要向用户提问；保持克制、自然、有连续感；正文 250-600 个汉字。",
        "互动记录：",
    ]
    for event in events[-80:]:
        timestamp = str(event.get("timestamp", ""))[:19]
        user = _compact(event.get("user_text"), 180)
        response = _compact(event.get("response"), 180)
        event_id = _compact(event.get("event_id"), 60)
        stage_before = _compact(event.get("stage_before"), 40)
        stage_after = _compact(event.get("stage_after"), 40)
        parts = [f"- {timestamp}"]
        if user:
            parts.append(f"用户说：{user}")
        if response:
            parts.append(f"我回应：{response}")
        if event_id:
            parts.append(f"事件：{event_id}")
        if stage_before or stage_after:
            parts.append(f"关系阶段：{stage_before or '?'} -> {stage_after or '?'}")
        lines.append("；".join(parts))
    return "\n".join(lines)


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone().replace(tzinfo=None)
    return parsed


def _compact(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]
