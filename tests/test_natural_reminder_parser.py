from __future__ import annotations

from datetime import datetime
from src.natural_reminder_parser import parse_natural_reminder

def test_natural_reminder_parser() -> None:
    base = datetime(2026, 5, 24, 12, 0, 0)

    # 1. Relative time
    res = parse_natural_reminder("十分钟后提醒我喝水", base_time=base)
    assert res.ok
    assert res.kind == "relative"
    assert res.reminder_text == "喝水"
    assert res.scheduled_at == datetime(2026, 5, 24, 12, 10, 0)
    assert not res.need_confirm

    res2 = parse_natural_reminder("半小时后叫我休息", base_time=base)
    assert res2.ok
    assert res2.kind == "relative"
    assert res2.reminder_text == "休息"
    assert res2.scheduled_at == datetime(2026, 5, 24, 12, 30, 0)

    # 2. Absolute time
    res3 = parse_natural_reminder("明天早上九点提醒我复习", base_time=base)
    assert res3.ok
    assert res3.kind == "absolute"
    assert res3.reminder_text == "复习"
    assert res3.scheduled_at == datetime(2026, 5, 25, 9, 0, 0)

    res4 = parse_natural_reminder("今晚八点叫我看课程", base_time=base)
    assert res4.ok
    assert res4.kind == "absolute"
    assert res4.reminder_text == "看课程"
    assert res4.scheduled_at == datetime(2026, 5, 24, 20, 0, 0)

    # 3. Recurring time
    res5 = parse_natural_reminder("每天晚上十点提醒我睡觉", base_time=base)
    assert res5.ok
    assert res5.kind == "recurring"
    assert res5.reminder_text == "睡觉"
    assert res5.scheduled_at == datetime(2026, 5, 24, 22, 0, 0)
    assert "freq=每天" in res5.recurrence

    # 4. Ambiguous time
    res6 = parse_natural_reminder("一会儿后提醒我喝水", base_time=base)
    assert res6.ok
    assert res6.kind == "ambiguous"
    assert res6.need_confirm

    # 5. Non-creation intents
    res7 = parse_natural_reminder("帮我写一个提醒系统", base_time=base)
    assert not res7.ok
    assert res7.kind == "failed"

    res8 = parse_natural_reminder("提醒我这个 bug 怎么修", base_time=base)
    assert not res8.ok or res8.kind == "failed"

    # 6. Mixed intent
    res9 = parse_natural_reminder("十分钟后提醒我喝水，然后帮我分析 bug", base_time=base)
    assert res9.ok
    assert res9.need_confirm
    assert res9.kind == "ambiguous"
