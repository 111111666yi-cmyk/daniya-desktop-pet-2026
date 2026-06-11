from __future__ import annotations

import re
import unicodedata


CHINESE_TECHNICAL_TERMS = (
    "代码",
    "编程",
    "脚本",
    "算法",
    "数据结构",
    "正则",
    "字符串",
    "函数",
    "变量",
    "模块",
    "类",
    "报错",
    "错误日志",
    "异常",
    "堆栈",
    "命令行",
    "配置文件",
    "端口",
    "编译",
    "依赖",
    "网络代理",
    "状态码",
    "累加器",
)

ENGLISH_TECHNICAL_TERMS = (
    "api",
    "baseurl",
    "bug",
    "traceback",
    "provider",
    "fallback",
    "json",
    "yaml",
    "python",
    "javascript",
    "typescript",
    "java",
    "sql",
    "git",
)

REMINDER_REQUEST_TERMS = (
    "提醒我",
    "到时提醒",
    "到时候提醒",
    "到时叫我",
    "到时候叫我",
    "记得叫我",
    "帮我设个提醒",
    "设置提醒",
    "设个闹钟",
)


def is_technical_request(user_text: str) -> bool:
    text = _normalize(user_text)
    if not text:
        return False
    if any(term in text for term in CHINESE_TECHNICAL_TERMS):
        return True
    english_pattern = "|".join(re.escape(term) for term in ENGLISH_TECHNICAL_TERMS)
    if re.search(rf"(?<![a-z0-9_])(?:{english_pattern})(?![a-z0-9_])", str(user_text).lower()):
        return True
    if "```" in user_text or re.search(r"\b[a-z_][a-z0-9_.]*\s*\(", user_text, re.IGNORECASE):
        return True
    return bool(re.search(r"\b(?:https?|tcp|udp)://|\b[A-Z][A-Za-z]+Error\b", user_text))


def is_reminder_request(user_text: str) -> bool:
    text = _normalize(user_text)
    return bool(text and any(term in text for term in REMINDER_REQUEST_TERMS))


def should_suppress_embedded_character_triggers(user_text: str) -> bool:
    return is_technical_request(user_text) or is_reminder_request(user_text)


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or "")).lower()
    return re.sub(r"\s+", "", value)
