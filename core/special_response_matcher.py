from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any
import re
import unicodedata

from core.message_intent import should_suppress_embedded_character_triggers


FUZZY_THRESHOLD = 0.86


@dataclass(frozen=True)
class SpecialResponseMatch:
    matched: bool = False
    id: str | None = None
    response: str | None = None
    action: str | None = None
    relationship_effect: dict[str, int] = field(default_factory=dict)
    match_type: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "matched": self.matched,
            "id": self.id,
            "response": self.response,
            "action": self.action,
            "relationship_effect": dict(self.relationship_effect),
            "match_type": self.match_type,
        }


def unmatched() -> dict[str, Any]:
    return SpecialResponseMatch().as_dict()


def match_special_response(
    user_text: str,
    speech_config: dict[str, Any] | None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not user_text or not isinstance(speech_config, dict):
        return unmatched()

    responses = speech_config.get("special_responses")
    if not isinstance(responses, list):
        return unmatched()

    text = str(user_text).strip()
    normalized_text = normalize_text(text)

    follow_up = _match_follow_up(text, normalized_text, responses, context or {})
    if follow_up.matched:
        return follow_up.as_dict()

    suppress_loose_matches = should_suppress_embedded_character_triggers(text)
    for match_type in ("exact", "normalized", "contains", "fuzzy"):
        if suppress_loose_matches and match_type in ("contains", "fuzzy"):
            continue
        for item in responses:
            if not isinstance(item, dict):
                continue

            # FIX: 'call_name' (达妮娅/娅娅) should only match exactly or normalized,
            # NOT when the user writes a full sentence containing her name (contains/fuzzy).
            if item.get("id") == "call_name" and match_type in ("contains", "fuzzy"):
                continue

            triggers = _trigger_list(item.get("trigger"))
            if not triggers:
                continue
            matched = any(_matches_trigger(text, normalized_text, trigger, match_type) for trigger in triggers)
            if matched:
                return _make_match(item, match_type).as_dict()

    return unmatched()


def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text))
    value = value.replace("……", "...")
    value = value.replace("。。。", "...")
    value = value.replace("，", ",").replace("。", ".").replace("！", "!")
    value = value.replace("？", "?").replace("：", ":").replace("；", ";")
    value = re.sub(r"\s+", "", value)
    value = re.sub(r"\.{2,}", "...", value)
    return value.lower().strip(".,!?;:")


def _match_follow_up(
    text: str,
    normalized_text: str,
    responses: list[Any],
    context: dict[str, Any],
) -> SpecialResponseMatch:
    last_id = context.get("last_special_response_id") or context.get("last_response_id")
    if not last_id:
        return SpecialResponseMatch()

    for item in responses:
        if not isinstance(item, dict) or item.get("id") != last_id:
            continue
        follow_up = item.get("follow_up_if_user_insists")
        if not isinstance(follow_up, dict):
            return SpecialResponseMatch()
        triggers = _trigger_list(follow_up.get("trigger"))
        if not triggers:
            return SpecialResponseMatch()
        for trigger in triggers:
            if (
                _matches_trigger(text, normalized_text, trigger, "exact")
                or _matches_trigger(text, normalized_text, trigger, "normalized")
                or _matches_trigger(text, normalized_text, trigger, "contains")
                or _matches_trigger(text, normalized_text, trigger, "fuzzy")
            ):
                return _make_match(follow_up, "follow_up", fallback_id=str(last_id))
    return SpecialResponseMatch()


def _matches_trigger(text: str, normalized_text: str, trigger: str, match_type: str) -> bool:
    trigger_text = str(trigger).strip()
    if not trigger_text:
        return False
    normalized_trigger = normalize_text(trigger_text)
    if match_type == "exact":
        return text == trigger_text
    if match_type == "normalized":
        return normalized_text == normalized_trigger
    if match_type == "contains":
        return normalized_trigger in normalized_text
    if match_type == "fuzzy":
        if len(normalized_trigger) > 12 or len(normalized_text) > 18:
            return False
        return SequenceMatcher(None, normalized_text, normalized_trigger).ratio() >= FUZZY_THRESHOLD
    return False


def _make_match(item: dict[str, Any], match_type: str, fallback_id: str | None = None) -> SpecialResponseMatch:
    response = item.get("response")
    if not isinstance(response, str) or not response:
        return SpecialResponseMatch()

    effect = item.get("relationship_effect")
    relationship_effect: dict[str, int] = {}
    if isinstance(effect, dict):
        for key, value in effect.items():
            try:
                relationship_effect[str(key)] = int(value)
            except (TypeError, ValueError):
                continue

    action = item.get("action")
    return SpecialResponseMatch(
        matched=True,
        id=str(item.get("id") or fallback_id) if item.get("id") or fallback_id else None,
        response=response,
        action=str(action) if action else None,
        relationship_effect=relationship_effect,
        match_type=match_type,
    )


def _trigger_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []
