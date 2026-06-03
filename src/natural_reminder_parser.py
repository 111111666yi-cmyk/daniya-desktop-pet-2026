from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta

@dataclass
class ReminderParseResult:
    ok: bool
    kind: str  # "relative" | "absolute" | "recurring" | "ambiguous" | "failed"
    reminder_text: str
    scheduled_at: datetime | None
    recurrence: str | None
    confidence: float
    need_confirm: bool
    reason: str

# CN Number mapping
CN_NUMS = {
    "半": 0.5, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12,
    "0": 0, "1": 1, "2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9
}

def parse_cn_num(text: str) -> float | None:
    text = text.strip()
    if not text:
        return None
    if text.isdigit():
        return float(text)
    if text in CN_NUMS:
        return CN_NUMS[text]
    if len(text) == 2 and text[0] == "十":
        second = CN_NUMS.get(text[1])
        if second is not None:
            return 10.0 + second
    if len(text) == 2 and text[1] == "十":
        first = CN_NUMS.get(text[0])
        if first is not None:
            return first * 10.0
    if len(text) == 3 and text[1] == "十":
        first = CN_NUMS.get(text[0])
        third = CN_NUMS.get(text[2])
        if first is not None and third is not None:
            return first * 10.0 + third
    return None

def parse_time_of_day(time_str: str, period_offset: int = 0) -> tuple[int, int] | None:
    time_str = time_str.strip()
    m_hm = re.match(r"^(\d{1,2})[:：](\d{2})$", time_str)
    if m_hm:
        hour = int(m_hm.group(1))
        minute = int(m_hm.group(2))
        if period_offset == 12 and hour < 12:
            hour += 12
        return hour, minute

    m_cn = re.match(r"^([一二三四五六七八九十百\d]+)\s*(?:点钟|点|时)\s*(?:([一二三四五六七八九十\d]+)\s*(?:分|分钟)?)?$", time_str)
    if m_cn:
        h_val = parse_cn_num(m_cn.group(1))
        if h_val is None:
            return None
        hour = int(h_val)
        if period_offset == 12 and hour < 12:
            hour += 12
        minute = 0
        if m_cn.group(2):
            m_val = parse_cn_num(m_cn.group(2))
            if m_val is not None:
                minute = int(m_val)
        return hour, minute

    m_half = re.match(r"^([一二三四五六七八九十百\d]+)\s*(?:点钟|点|时)\s*半$", time_str)
    if m_half:
        h_val = parse_cn_num(m_half.group(1))
        if h_val is None:
            return None
        hour = int(h_val)
        if period_offset == 12 and hour < 12:
            hour += 12
        return hour, 30

    return None

def extract_reminder_intent(text: str) -> str | None:
    patterns = [
        r"(?:提醒我|叫我|记得|提醒|叫)\s*(.+)$",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1).strip()
    return None

def parse_natural_reminder(text: str, base_time: datetime | None = None) -> ReminderParseResult:
    if base_time is None:
        base_time = datetime.now()

    cleaned = text.strip()

    # Rule 1: Filter out overall technical/discussion topics on reminder system
    system_patterns = [
        r"提醒系统",
        r"怎么(?:写|开发|实现)提醒",
        r"如何(?:写|开发|实现)提醒"
    ]
    for p in system_patterns:
        if re.search(p, cleaned):
            return ReminderParseResult(
                ok=False, kind="failed", reminder_text="", scheduled_at=None,
                recurrence=None, confidence=0.0, need_confirm=False,
                reason="检测到有关提醒系统开发的技术讨论意图"
            )

    # Check triggering words
    trigger_words = ["提醒我", "叫我", "记得", "提醒", "到时叫"]
    has_trigger = any(w in cleaned for w in trigger_words)
    if not has_trigger:
        return ReminderParseResult(
            ok=False, kind="failed", reminder_text="", scheduled_at=None,
            recurrence=None, confidence=0.0, need_confirm=False,
            reason="未检测到明确的提醒触发词"
        )

    # Extract reminder task
    reminder_text = extract_reminder_intent(cleaned)
    if not reminder_text:
        # Fallback to removing trigger words
        reminder_text = cleaned
        for w in trigger_words:
            reminder_text = reminder_text.replace(w, "")
        reminder_text = reminder_text.strip()

    # Check if the extracted text itself is a question or technical prompt (e.g. "这个 bug 怎么修")
    technical_task_patterns = [
        r"怎么(?:修|写|办|做|分析|解决)",
        r"如何(?:修|写|办|做|分析|解决)",
        r"为什么",
        r"解释一下"
    ]
    for p in technical_task_patterns:
        if re.search(p, reminder_text):
            return ReminderParseResult(
                ok=False, kind="failed", reminder_text="", scheduled_at=None,
                recurrence=None, confidence=0.0, need_confirm=False,
                reason=f"提醒任务内容包含求助/提问词汇（{p}），判定为普通对话而非创建提醒"
            )

    # Rule 2: Check mixed intent (e.g., has "然后帮我", "顺便帮我")
    mixed_patterns = [
        r"(?:然后|顺便|并且|接着)\s*(?:帮我|分析|写|修|查|看)",
    ]
    is_mixed = False
    for p in mixed_patterns:
        if re.search(p, cleaned):
            is_mixed = True
            # Strip the mixed action to clean reminder_text
            split_m = re.split(p, reminder_text)
            if split_m:
                reminder_text = split_m[0].strip("，, ；; \t\n")
            break

    if is_mixed:
        return ReminderParseResult(
            ok=True, kind="ambiguous", reminder_text=reminder_text, scheduled_at=None,
            recurrence=None, confidence=0.5, need_confirm=True,
            reason="检测到提醒与其它任务混合的意图，需要确认"
        )

    # Rule 3: Recurring Time (每天, 每周一等)
    m_recur = re.search(r"(每天|每周[一二三四五六日]|[每每]周)\s*(早上|上午|中午|下午|晚上|傍晚|深夜)?\s*([一二三四五六七八九十\d]+点[半\d分\s]*|\d{1,2}[:：]\d{2})", cleaned)
    if m_recur:
        freq = m_recur.group(1)
        period = m_recur.group(2) or ""
        time_part = m_recur.group(3)
        offset = 12 if period in ["下午", "晚上", "傍晚", "深夜"] else 0
        parsed_t = parse_time_of_day(time_part, offset)
        if parsed_t:
            h, m = parsed_t
            recurrence_str = f"freq={freq};time={h:02d}:{m:02d}"
            sched = base_time.replace(hour=h, minute=m, second=0, microsecond=0)
            if sched <= base_time:
                sched += timedelta(days=1)
            return ReminderParseResult(
                ok=True, kind="recurring", reminder_text=reminder_text, scheduled_at=sched,
                recurrence=recurrence_str, confidence=0.9, need_confirm=False,
                reason=f"成功识别循环提醒：{freq} {period} {time_part}"
            )

    # Rule 4: Relative Time (十分钟后, 半小时后)
    m_rel = re.search(r"([一二两三四五六七八九十\d]+|半)\s*(分钟|分|小时|点钟|点|天)\s*后", cleaned)
    if m_rel:
        num_str = m_rel.group(1)
        unit = m_rel.group(2)
        val = parse_cn_num(num_str)
        if val is not None:
            delta = timedelta()
            if "分" in unit:
                delta = timedelta(minutes=val)
            elif "小时" in unit or "点" in unit:
                delta = timedelta(hours=val)
            elif "天" in unit:
                delta = timedelta(days=val)
            scheduled_at = base_time + delta
            return ReminderParseResult(
                ok=True, kind="relative", reminder_text=reminder_text, scheduled_at=scheduled_at,
                recurrence=None, confidence=0.95, need_confirm=False, reason="成功解析相对时间"
            )

    # Rule 5: Ambiguous Relative
    ambiguous_rel = ["一会儿后", "过会儿", "一会儿", "有空时", "晚点", "等会儿", "等一下"]
    if any(w in cleaned for w in ambiguous_rel):
        return ReminderParseResult(
            ok=True, kind="ambiguous", reminder_text=reminder_text, scheduled_at=None,
            recurrence=None, confidence=0.6, need_confirm=True,
            reason="检测到模糊的时间表述，无法自动确定时间，需要确认"
        )

    # Rule 6: Absolute Time
    m_day = re.search(r"(今天|今晚|明天|明早|后天)", cleaned)
    day_offset = 0
    if m_day:
        day_str = m_day.group(1)
        if day_str in ["今天", "今晚"]:
            day_offset = 0
        elif day_str in ["明天", "明早"]:
            day_offset = 1
        elif day_str == "后天":
            day_offset = 2

    m_period = re.search(r"(早上|上午|中午|下午|晚上|傍晚|深夜|早|晚)", cleaned)
    period_offset = 0
    if m_period:
        period_str = m_period.group(1)
        if period_str in ["下午", "晚上", "傍晚", "深夜", "晚"]:
            period_offset = 12

    m_time = re.search(r"([一二三四五六七八九十\d]+点[半\d分\s]*|\d{1,2}[:：]\d{2})", cleaned)
    if m_time:
        time_part = m_time.group(1)
        parsed_t = parse_time_of_day(time_part, period_offset)
        if parsed_t:
            h, m = parsed_t
            target_date = base_time + timedelta(days=day_offset)
            scheduled_at = target_date.replace(hour=h, minute=m, second=0, microsecond=0)
            if scheduled_at <= base_time and day_offset == 0:
                scheduled_at += timedelta(days=1)
            return ReminderParseResult(
                ok=True, kind="absolute", reminder_text=reminder_text, scheduled_at=scheduled_at,
                recurrence=None, confidence=0.9, need_confirm=False, reason="成功解析绝对时间"
            )

    if m_day:
        h_fallback = 9
        if period_offset == 12:
            h_fallback = 20
        elif "中午" in cleaned:
            h_fallback = 12
        elif "下午" in cleaned:
            h_fallback = 15
        elif "深夜" in cleaned:
            h_fallback = 23
        
        target_date = base_time + timedelta(days=day_offset)
        scheduled_at = target_date.replace(hour=h_fallback, minute=0, second=0, microsecond=0)
        if scheduled_at <= base_time and day_offset == 0:
            scheduled_at += timedelta(days=1)
        
        return ReminderParseResult(
            ok=True, kind="ambiguous", reminder_text=reminder_text, scheduled_at=scheduled_at,
            recurrence=None, confidence=0.7, need_confirm=True,
            reason=f"仅识别到大概日期与时段（拟设定为 {scheduled_at.strftime('%Y-%m-%d %H:%M')}），需要确认"
        )

    return ReminderParseResult(
        ok=True, kind="ambiguous", reminder_text=reminder_text, scheduled_at=None,
        recurrence=None, confidence=0.5, need_confirm=True,
        reason="未检测到明确的时间点，需要手动确认时间"
    )
