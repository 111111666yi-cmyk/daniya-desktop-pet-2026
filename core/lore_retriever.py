from __future__ import annotations

import re
from typing import Any

from core.schema import CharacterPack
from core.special_response_matcher import normalize_text


DEFAULT_MAX_CHARS = 220
MAX_FRAGMENTS = 2


def load_lore_index(character_pack: CharacterPack | dict[str, Any] | None) -> list[dict[str, Any]]:
    lore_index = getattr(character_pack, "lore_index", character_pack)
    if not isinstance(lore_index, dict):
        return []
    fragments = lore_index.get("fragments")
    if not isinstance(fragments, list):
        return []
    return [fragment for fragment in fragments if isinstance(fragment, dict)]


def retrieve(
    user_text: str,
    character_pack: CharacterPack,
    state: dict[str, Any] | None = None,
    matched_event: dict[str, Any] | None = None,
    memory: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not user_text or not character_pack:
        return []

    results: list[dict[str, Any]] = []
    for fragment in load_lore_index(character_pack):
        fragment_id = str(fragment.get("id") or "").strip()
        if not fragment_id:
            continue

        matched, source = _fragment_matches(user_text, fragment, matched_event, memory)
        if not matched:
            continue
        if not can_inject_level(str(fragment.get("level") or ""), state, memory, matched_event, user_text, source):
            continue

        max_chars = _safe_int(fragment.get("max_chars"), DEFAULT_MAX_CHARS)
        content = extract_fragment(character_pack.lore, fragment_id, fragment)
        if not content:
            warning = f"lore fragment not found: {fragment_id}"
            if fragment.get("summary"):
                content = str(fragment.get("summary"))
            else:
                results.append(_result(fragment, "", source, max_chars, warning=warning))
                continue
        results.append(_result(fragment, trim_fragment(content, max_chars), source, max_chars))

    return _dedupe_by_id(results)[:MAX_FRAGMENTS]


def extract_fragment(lore_text: str, fragment_id: str, fragment_config: dict[str, Any] | None = None) -> str:
    if not lore_text:
        return ""
    config = fragment_config or {}

    heading = config.get("source_heading")
    if isinstance(heading, str) and heading.strip():
        section = _section_after_heading(lore_text, heading.strip())
        if section:
            return section

    source_keywords = config.get("source_keywords") or config.get("keywords") or [fragment_id]
    if isinstance(source_keywords, str):
        source_keywords = [source_keywords]
    if isinstance(source_keywords, list):
        section = _paragraphs_near_keywords(lore_text, [str(keyword) for keyword in source_keywords])
        if section:
            return section

    marker_patterns = [
        rf"<!--\s*fragment:{re.escape(fragment_id)}\s*-->(.*?)(?=<!--\s*fragment:|\Z)",
        rf"^#+\s*{re.escape(fragment_id)}\b(.*?)(?=^#+\s+|\Z)",
    ]
    for pattern in marker_patterns:
        match = re.search(pattern, lore_text, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if match:
            return match.group(1).strip()
    return ""


def keyword_match(user_text: str, keywords: list[Any] | str | None) -> bool:
    if not user_text or not keywords:
        return False
    if isinstance(keywords, str):
        keywords = [keywords]
    if not isinstance(keywords, list):
        return False
    text = normalize_text(user_text)
    return any(normalize_text(str(keyword)) in text for keyword in keywords if str(keyword).strip())


def can_inject_level(
    level: str,
    state: dict[str, Any] | None = None,
    memory: dict[str, Any] | None = None,
    matched_event: dict[str, Any] | None = None,
    user_text: str = "",
    match_source: str | None = None,
) -> bool:
    normalized = _normalize_level(level)
    if normalized in {"L0", "L1"}:
        return True
    if normalized in {"L2", "L3"}:
        return bool(match_source in {"keyword", "event", "memory"} or matched_event)
    if normalized == "L4":
        return _explicit_story_question(user_text)
    return False


def trim_fragment(content: str, max_chars: int | None = None) -> str:
    text = _clean_text(content)
    limit = max(40, _safe_int(max_chars, DEFAULT_MAX_CHARS))
    if len(text) <= limit:
        return text
    return text[:limit].rstrip("，。；、,. ;") + "..."


def build_lore_block(fragments: list[dict[str, Any]] | None) -> str:
    if not fragments:
        return ""
    lines = ["【必要背景片段】"]
    for fragment in fragments[:MAX_FRAGMENTS]:
        if not isinstance(fragment, dict):
            continue
        content = str(fragment.get("content") or "").strip()
        if not content:
            continue
        lines.append(f"* fragment_id: {fragment.get('id')}")
        lines.append(f"* level: {fragment.get('level')}")
        lines.append(f"* content: {content}")
    return "\n".join(lines)


def _fragment_matches(
    user_text: str,
    fragment: dict[str, Any],
    matched_event: dict[str, Any] | None,
    memory: dict[str, Any] | None,
) -> tuple[bool, str | None]:
    fragment_id = str(fragment.get("id") or "")
    if _event_lore_ids(matched_event) and fragment_id in _event_lore_ids(matched_event):
        return True, "event"
    if fragment_id in _memory_unlocked_lore(memory):
        if keyword_match(user_text, fragment.get("keywords")):
            return True, "memory"
    if keyword_match(user_text, fragment.get("keywords")):
        return True, "keyword"
    if _negative_event(matched_event) and _normalize_level(str(fragment.get("level") or "")) == "L1":
        inject_when = fragment.get("inject_when")
        if isinstance(inject_when, list) and "user_negative_mood" in inject_when:
            return True, "event"
    return False, None


def _event_lore_ids(event: dict[str, Any] | None) -> set[str]:
    if not isinstance(event, dict):
        return set()
    values = event.get("lore_fragment") or event.get("unlock_lore") or event.get("related_lore_id") or []
    if isinstance(values, str):
        return {values}
    if isinstance(values, list):
        return {str(value) for value in values if str(value).strip()}
    return set()


def _memory_unlocked_lore(memory: dict[str, Any] | None) -> set[str]:
    if not isinstance(memory, dict):
        return set()
    values = memory.get("unlocked_lore")
    if not isinstance(values, list):
        return set()
    return {str(value) for value in values if str(value).strip()}


def _negative_event(event: dict[str, Any] | None) -> bool:
    if not isinstance(event, dict):
        return False
    return event.get("id") == "user_negative_mood" or event.get("type") in {"negative_emotion", "emotion"}


def _normalize_level(level: str) -> str:
    text = str(level).upper()
    aliases = {
        "LEVEL_0_PUBLIC": "L0",
        "LEVEL_1_MOTIVATION": "L1",
        "LEVEL_2_HIDDEN_TRAUMA": "L2",
        "LEVEL_3_MAJOR_SPOILER": "L3",
        "LEVEL_4_DEEP_SPOILER": "L4",
    }
    if text in aliases:
        return aliases[text]
    match = re.search(r"L([0-4])", text)
    return f"L{match.group(1)}" if match else text


def _explicit_story_question(user_text: str) -> bool:
    text = normalize_text(user_text)
    explicit_keywords = [
        "剧情",
        "背景",
        "虚无",
        "暗面",
        "身份谜团",
        "残心会",
        "财星会",
        "到底",
        "关系",
        "真相",
    ]
    return any(normalize_text(keyword) in text for keyword in explicit_keywords)


def _section_after_heading(lore_text: str, heading: str) -> str:
    start = lore_text.find(heading)
    if start < 0:
        return ""
    after = lore_text[start + len(heading) :]
    next_heading = re.search(r"\n#{1,3}\s+", after)
    if next_heading:
        after = after[: next_heading.start()]
    return after.strip(" \n-")


def _paragraphs_near_keywords(lore_text: str, keywords: list[str]) -> str:
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", lore_text) if paragraph.strip()]
    normalized_keywords = [normalize_text(keyword) for keyword in keywords if keyword.strip()]
    matches: list[str] = []
    for paragraph in paragraphs:
        normalized_paragraph = normalize_text(paragraph)
        if any(keyword and keyword in normalized_paragraph for keyword in normalized_keywords):
            if not paragraph.startswith(">") and "lore_index.yaml" not in paragraph:
                matches.append(paragraph)
        if len(matches) >= 2:
            break
    return "\n".join(matches)


def _result(
    fragment: dict[str, Any],
    content: str,
    source: str | None,
    max_chars: int,
    warning: str | None = None,
) -> dict[str, Any]:
    result = {
        "id": str(fragment.get("id") or ""),
        "title": str(fragment.get("title") or fragment.get("id") or ""),
        "level": _normalize_level(str(fragment.get("level") or "")),
        "content": content,
        "source": source,
        "max_chars": max_chars,
    }
    if warning:
        result["warning"] = warning
    return result


def _clean_text(content: str) -> str:
    text = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    text = re.sub(r"^[-*>#\s]+", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _dedupe_by_id(fragments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for fragment in fragments:
        fragment_id = str(fragment.get("id") or "")
        if fragment_id and fragment_id not in seen:
            result.append(fragment)
            seen.add(fragment_id)
    return result
