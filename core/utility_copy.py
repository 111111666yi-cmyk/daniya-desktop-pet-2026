from __future__ import annotations

from typing import Any


DEFAULT_UTILITY_RESPONSES = {
    "reminder_saved": "提醒记下了。到时间我会叫你。",
    "reminder_due": "时间到了：{text}。",
    "reminder_ambiguous": "时间还不够明确。告诉我具体一点，比如“十分钟后”。",
    "reminder_parse_failed": "这次没看懂时间，提醒没有创建。",
    "file_organizer_disabled": "文件整理现在是关闭的。先在设置里开启，再生成预览。",
    "file_organizer_completed": "整理完成：成功 {moved}，失败 {failed}。记录已保存在本机。",
    "clipboard_sensitive": "这段内容可能包含隐私或凭据，我不会显示、保存或发送它。",
    "clipboard_too_long": "这段文字有 {length} 个字。需要你确认后才能继续处理。",
    "clipboard_safe": "剪贴板里有一段新文字。需要我处理时再确认。",
    "system_cpu": "CPU 使用率到了 {value}%。先看看是不是有程序占用太多。",
    "system_memory": "内存使用率到了 {value}%。可以先关掉暂时不用的程序。",
    "system_battery": "电量只剩 {value}% 了，记得接上电源。",
    "system_network": "网络连接断开了。恢复后再继续需要联网的事情。",
    "focus_enter": "……专注模式开了。我会安静一点。",
    "focus_exit": "……专注模式关掉了。",
}


class _SafeValues(dict[str, Any]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def utility_text(character_pack: Any, key: str, **values: Any) -> str:
    speech = getattr(character_pack, "speech", {})
    responses = speech.get("utility_responses", {}) if isinstance(speech, dict) else {}
    template = responses.get(key) if isinstance(responses, dict) else None
    if not isinstance(template, str) or not template.strip():
        template = DEFAULT_UTILITY_RESPONSES.get(key, key)
    return template.format_map(_SafeValues(values))
