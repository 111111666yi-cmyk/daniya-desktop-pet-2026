from __future__ import annotations

from typing import Any

from core.message_intent import should_suppress_embedded_character_triggers
from core.special_response_matcher import normalize_text


def match_event(
    user_text: str,
    events_config: dict[str, Any] | None,
    allow_embedded_matches: bool | None = None,
) -> dict[str, Any] | None:
    if not user_text or not isinstance(events_config, dict):
        return None
    events = events_config.get("events")
    if not isinstance(events, list):
        return None
    normalized_text = normalize_text(user_text)
    if allow_embedded_matches is None:
        allow_embedded_matches = not should_suppress_embedded_character_triggers(user_text)
    for event in events:
        if not isinstance(event, dict):
            continue
        triggers = event.get("triggers") or event.get("trigger_keywords") or []
        if isinstance(triggers, str):
            triggers = [triggers]
        if not isinstance(triggers, list):
            continue
        for trigger in triggers:
            normalized_trigger = normalize_text(str(trigger))
            if not normalized_trigger:
                continue
            if not allow_embedded_matches and normalized_trigger != normalized_text:
                continue
            if normalized_trigger in normalized_text:
                return dict(event)
    return None

