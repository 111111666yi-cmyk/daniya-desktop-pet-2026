from __future__ import annotations

from typing import Any
import re


DEFAULT_MAX_CHARS = 90


def apply_daniya_speech_filter(
    raw_text: str,
    speech_config: dict[str, Any] | None,
    relationship_state: dict[str, Any] | None = None,
) -> str:
    text = str(raw_text or "").strip()
    if not text:
        return "......"

    config = speech_config if isinstance(speech_config, dict) else {}
    text = remove_customer_service_tone(text, config)
    text = remove_overly_warm_phrases(text, config)
    text = replace_direct_affection_with_reverse_style(text, config)
    text = remove_unrelated_topic_expansion(text)
    text = shorten_response(text, config, relationship_state)
    text = add_ellipsis_if_needed(text)
    return text.strip() or "......"


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
    text = "\n".join(lines[:max_lines])

    if len(text) <= max_chars:
        return text

    parts = [part.strip() for part in re.split(r"(?<=[。.!！？?])", text) if part.strip()]
    shortened = ""
    for part in parts:
        if len(shortened + part) > max_chars:
            break
        shortened += part
        if shortened.count("\n") + 1 >= max_lines:
            break
    if not shortened:
        shortened = text[:max_chars].rstrip("，,。.!！?？、 ")
    return shortened


def add_ellipsis_if_needed(text: str) -> str:
    clean = text.strip()
    if not clean:
        return "......"
    if clean.startswith("......") or clean in {"嗯。", "哦。", "......烦。", "......"}:
        return clean
    if clean.startswith(("嗯", "哦")):
        return clean
    return "......" + clean


def remove_unrelated_topic_expansion(text: str) -> str:
    markers = ["顺便", "另外", "除此之外", "话说回来", "我还想提醒你"]
    for marker in markers:
        index = text.find(marker)
        if index > 0:
            text = text[:index]
    return _clean_spacing(text)


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

