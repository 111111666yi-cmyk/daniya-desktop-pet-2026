from __future__ import annotations

from typing import Any
import logging
import re


DEFAULT_MAX_CHARS = 90
TRUNCATION_TAIL = "……先说到这里。"
logger = logging.getLogger(__name__)


def _term(*parts: str) -> str:
    return "".join(parts)


FORBIDDEN_USER_ADDRESSING_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\u3054\u4e3b\u4eba\u69d8", "你"),
    (r"\u3054\u4e3b\u4eba", "你"),
    (r"\u5fa1\u4e3b\u69d8", "你"),
    (r"\u5fa1\u4e3b", "你"),
    (r"\u4e3b\u4eba(?!\u516c)", "你"),
    (rf"(?<![A-Za-z0-9_/.-])(?:{_term('Mas', 'ter')}|{_term('MAS', 'TER')})(?![A-Za-z0-9_-])", "你"),
    (r"\u6307\u6325\u5b98", "你"),
    (r"\u6f02\u6cca\u8005", "你"),
)

MASTER_BRANCH_CONTEXT = re.compile(
    r"(origin/|refs/heads/|branch|分支|git|checkout|merge|rebase|push|pull|HEAD)",
    re.IGNORECASE,
)


def apply_daniya_speech_filter(
    raw_text: str,
    speech_config: dict[str, Any] | None,
    relationship_state: dict[str, Any] | None = None,
    response_mode: str = "companion",
) -> str:
    text = str(raw_text or "").strip()
    if not text:
        return "......"
    text = sanitize_user_addressing(text)
    if "```" in text:
        return text

    config = speech_config if isinstance(speech_config, dict) else {}
    if str(response_mode).lower() == "technical":
        return _filter_technical_response(text)

    text = remove_customer_service_tone(text, config)
    text = remove_overly_warm_phrases(text, config)
    text = replace_direct_affection_with_reverse_style(text, config)
    before_expansion_filter = text
    text = remove_unrelated_topic_expansion(text)
    if text != before_expansion_filter:
        logger.info(
            "speech_filter_removed_expansion original_chars=%d filtered_chars=%d",
            len(before_expansion_filter),
            len(text),
        )
    before_shortening = text
    text = shorten_response(text, config, relationship_state)
    if text != before_shortening:
        logger.info(
            "speech_filter_truncated original_chars=%d filtered_chars=%d",
            len(before_shortening),
            len(text),
        )
    text = add_ellipsis_if_needed(text)
    return text.strip() or "......"


def sanitize_user_addressing(raw_text: str) -> str:
    text = str(raw_text or "")
    for pattern, replacement in FORBIDDEN_USER_ADDRESSING_PATTERNS:
        text = re.sub(pattern, replacement, text)
    text = re.sub(r"\bmaster\b", lambda match: _replace_lowercase_master(match, text), text)
    return text


def _replace_lowercase_master(match: re.Match[str], text: str) -> str:
    start, end = match.span()
    context = text[max(0, start - 24): min(len(text), end + 24)]
    if MASTER_BRANCH_CONTEXT.search(context):
        return match.group(0)
    return "你"


def remove_customer_service_tone(text: str, speech_config: dict[str, Any] | None = None) -> str:
    replacements = _replacement_rules(speech_config)
    for source in ("你一定很难过吧，我理解你", "你一定很难过吧", "我完全理解你的感受", "我完全理解你"):
        if source in text:
            text = text.replace(source, replacements.get(source, "......别装了。你现在不太好。"))
    patterns = [
        r"如果你(愿意|需要).{0,16}(可以|随时).{0,16}(告诉我|跟我说)",
        r"作为.{0,8}(助手|AI).{0,20}",
        r"我能理解你现在的感受[，,。.]?",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text)
    return _clean_spacing(text)


def remove_overly_warm_phrases(text: str, speech_config: dict[str, Any] | None = None) -> str:
    replacements = _replacement_rules(speech_config)
    for source in ("亲爱的", "宝宝", "宝贝"):
        text = text.replace(source, replacements.get(source, ""))
    warm_phrases = ["真的特别特别", "非常非常", "超级开心", "太好了"]
    for phrase in warm_phrases:
        text = text.replace(phrase, "")
    return _clean_spacing(text)


def replace_direct_affection_with_reverse_style(text: str, speech_config: dict[str, Any] | None = None) -> str:
    replacements = _replacement_rules(speech_config)
    for source, target in replacements.items():
        if source in text:
            text = text.replace(source, str(target))

    strong_promises = [
        "我都会永远守护你",
        "我会永远守护你",
        "我会一直守护你",
        "我会一直陪着你",
        "我永远陪着你",
        "不管发生什么",
    ]
    if any(phrase in text for phrase in strong_promises):
        return "......随便你。反正我也懒得赶。"
    if "你要振作起来" in text:
        text = text.replace("你要振作起来", "......先坐会儿。")
    return _clean_spacing(text)


def shorten_response(
    text: str,
    speech_config: dict[str, Any] | None = None,
    relationship_state: dict[str, Any] | None = None,
) -> str:
    sentence_cfg = {}
    if isinstance(speech_config, dict):
        sentence_cfg = speech_config.get("speech_style", {}).get("sentence_length", {})
        if not isinstance(sentence_cfg, dict):
            sentence_cfg = {}

    serious = bool(relationship_state and relationship_state.get("serious"))
    max_lines = int(sentence_cfg.get("max_lines_serious" if serious else "max_lines_normal", 3 if not serious else 4))
    max_chars = int(sentence_cfg.get("bubble_max_chars", DEFAULT_MAX_CHARS if not serious else 120))

    text = _clean_spacing(text)
    lines = [line.strip() for line in re.split(r"[\r\n]+", text) if line.strip()]
    if not lines:
        lines = [text]
    selected = "\n".join(lines[:max_lines])
    needs_truncation = len(lines) > max_lines or len(selected) > max_chars
    if not needs_truncation:
        return selected

    content_limit = max(1, max_chars - len(TRUNCATION_TAIL))
    shortened = _truncate_at_boundary(selected, content_limit)
    return shortened.rstrip(" \t\r\n，,") + TRUNCATION_TAIL


def add_ellipsis_if_needed(text: str) -> str:
    clean = text.strip()
    if not clean:
        return "......"
    if clean.startswith(("......", "……", "...", "…", ".")):
        return clean
    if clean.startswith(("嗯", "哦")):
        return clean
    return "......" + clean



def remove_unrelated_topic_expansion(text: str) -> str:
    # "除此之外 / 另外" continue the same answer, so they are not treated as
    # off-topic digressions; only genuine topic changes / nagging are truncated.
    markers = ["顺便", "话说回来", "我还想提醒你"]
    for marker in markers:
        index = text.find(marker)
        if index > 10:
            text = text[:index]
    return _clean_spacing(text)


def _filter_technical_response(text: str) -> str:
    if _is_structured_content(text):
        return text
    return text.strip() or "......"


def _is_structured_content(text: str) -> bool:
    if "```" in text:
        return True
    if "Traceback (most recent call last):" in text:
        return True
    if re.search(r"(?m)^\s*\|.+\|\s*$", text) and re.search(r"(?m)^\s*\|[\s:|-]+\|\s*$", text):
        return True
    return bool(re.search(r"(?m)^\s*(?:[-*+]|\d+[.)])\s+\S", text))


def _truncate_at_boundary(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text

    parts = [part for part in re.split(r"(?<=[。.!！？?])", text) if part]
    shortened = ""
    for part in parts:
        if len(shortened + part) > limit:
            break
        shortened += part
    if shortened.strip():
        return shortened.strip()

    prefix = text[:limit]
    boundary = max(prefix.rfind(mark) for mark in ("，", ",", "；", ";", "：", ":"))
    if boundary > 0:
        return prefix[: boundary + 1].strip()
    return prefix.rstrip(" \t\r\n，,。.!！?？、")


def _replacement_rules(speech_config: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(speech_config, dict):
        return {}
    rules = speech_config.get("replacement_rules")
    if not isinstance(rules, dict):
        return {}
    return {str(key): str(value) for key, value in rules.items()}


def _clean_spacing(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\s+([，。！？,.!?])", r"\1", text)
    text = re.sub(r"([，。！？,.!?])\s+", r"\1", text)
    text = text.replace("。。", "。")
    return text.strip(" \t\r\n，,")
