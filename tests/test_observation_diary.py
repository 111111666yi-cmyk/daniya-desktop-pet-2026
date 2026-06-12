from __future__ import annotations

from datetime import datetime, timedelta

from src.observation_diary import ObservationDiary, build_diary_prompt, recent_events


NOW = datetime(2026, 6, 12, 12, 0, 0)


def _event(days_ago: int, text: str) -> dict[str, object]:
    return {
        "timestamp": (NOW - timedelta(days=days_ago)).isoformat(timespec="seconds"),
        "user_text": text,
        "response": "……我记得。",
        "event_id": "chat",
    }


def test_recent_events_only_keeps_requested_window() -> None:
    events = [_event(1, "近"), _event(4, "远")]

    recent = recent_events(events, days=3, now=NOW)

    assert [event["user_text"] for event in recent] == ["近"]


def test_diary_prompt_requires_first_person_and_no_invention() -> None:
    prompt = build_diary_prompt([_event(1, "今天练了钢琴")], days=3, now=NOW)

    assert "第一人称" in prompt
    assert "不虚构" in prompt
    assert "今天练了钢琴" in prompt


def test_diary_saves_only_real_provider_result(tmp_path) -> None:
    diary = ObservationDiary(
        lambda _prompt: ("今天她练了钢琴。", "api"),
        path=tmp_path / "diary.jsonl",
        event_loader=lambda: [_event(1, "今天练了钢琴")],
    )

    result = diary.generate(days=3, now=NOW)

    assert result["ok"] is True
    assert diary.records()[0]["event_count"] == 1


def test_diary_does_not_save_local_fallback(tmp_path) -> None:
    diary = ObservationDiary(
        lambda _prompt: ("……刚才没有连上。", "local"),
        path=tmp_path / "diary.jsonl",
        event_loader=lambda: [_event(1, "今天练了钢琴")],
    )

    result = diary.generate(days=3, now=NOW)

    assert result["ok"] is False
    assert diary.records() == []
