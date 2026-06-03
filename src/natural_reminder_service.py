from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .natural_reminder_parser import parse_natural_reminder, ReminderParseResult
from .reminder_manager import ReminderManager

if TYPE_CHECKING:
    from .reminder_manager import ReminderManager

class NaturalReminderService:
    def __init__(self, reminder_manager: ReminderManager) -> None:
        self.reminder_manager = reminder_manager

    def process_chat_message(self, message: str, base_time: datetime | None = None) -> tuple[bool, str, ReminderParseResult | None]:
        """
        Process user message for reminder intent.
        Returns:
            (is_reminder_intent, reply_message, parse_result)
        """
        result = parse_natural_reminder(message, base_time=base_time)
        if not result.ok:
            # Not a creation intent or failed
            return False, "", result

        if result.need_confirm:
            # Requires user confirmation (e.g. ambiguous time, mixed intent)
            if result.kind == "ambiguous" and result.scheduled_at:
                suggested_time = result.scheduled_at.strftime("%Y-%m-%d %H:%M")
                reply = f"……我只听懂了大概的时段。你是想在【{suggested_time}】提醒你【{result.reminder_text}】吗？确认的话跟我说“确认”或直接点。"
            elif result.kind == "ambiguous":
                reply = f"……提醒【{result.reminder_text}】的时间太模糊了。什么时候叫你？告诉我一个具体点的时间，比如“十分钟后”或“晚上八点”。"
            else:
                # Mixed intent
                reply = f"……你想让我提醒你【{result.reminder_text}】对吧？但是你后面还带了别的事情，到时候我只弹气泡，其它的你自己搞定哦。"
            return True, reply, result

        # Parse success and no confirmation needed
        if result.scheduled_at:
            time_str = result.scheduled_at.strftime("%Y-%m-%d %H:%M")
            success, msg = self.reminder_manager.add(time_str, result.reminder_text)
            if success:
                reply = f"……记下了。会在【{time_str}】提醒你【{result.reminder_text}】。到时候别装作看不见。"
            else:
                reply = msg
            return True, reply, result

        return True, "……时间解析出了点小问题，没法直接创建提醒。", result
