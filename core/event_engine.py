from __future__ import annotations

from typing import Any

from core.special_response_matcher import normalize_text


def match_event(user_text: str, events_config: dict[str, Any] | None) -> dict[str, Any] | None:
    if not user_text or not isinstance(events_config, dict):
        return None
    events = events_config.get("events")
    if not isinstance(events, list):
        return None
    normalized_text = normalize_text(user_text)
    for event in events:
        if not isinstance(event, dict):
            continue
        triggers = event.get("triggers") or event.get("trigger_keywords") or []
        if isinstance(triggers, str):
            triggers = [triggers]
        if not isinstance(triggers, list):
            continue
        for trigger in triggers:
            if normalize_text(str(trigger)) in normalized_text:
                return dict(event)
    return None

