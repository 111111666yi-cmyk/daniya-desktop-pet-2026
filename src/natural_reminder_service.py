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
                reply = f"……我只听懂了大概的时段。是【{suggested_time}】提醒你【{result.reminder_text}】吗？确认的话告诉我。"
            elif result.kind == "ambiguous":
                reply = self.reminder_manager.message(
                    "reminder_ambiguous",
                    "时间还不够明确。告诉我具体一点，比如“十分钟后”。",
                )
            else:
                # Mixed intent
                reply = f"……提醒内容是【{result.reminder_text}】，对吗？确认后我只记这件事。"
            return True, reply, result

        # Parse success and no confirmation needed
        if result.scheduled_at:
            time_str = result.scheduled_at.strftime("%Y-%m-%d %H:%M")
            success, msg = self.reminder_manager.add(time_str, result.reminder_text)
            if success:
                reply = f"{msg}【{time_str}】【{result.reminder_text}】"
            else:
                reply = msg
            return True, reply, result

        return True, self.reminder_manager.message(
            "reminder_parse_failed",
            "这次没看懂时间，提醒没有创建。",
        ), result
