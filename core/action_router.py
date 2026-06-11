from __future__ import annotations

from typing import Any


V041_BASE_ACTIONS = {"idle", "talk", "clicked", "drag", "sleep", "happy", "remind", "normal1", "normal2"}

GENERIC_FALLBACKS: dict[str, list[str]] = {
    "idle": ["idle", "normal1"],
    "soft_idle": ["soft_idle", "idle", "normal1"],
    "talk": ["talk", "normal1", "normal2", "idle"],
    "clicked": ["clicked", "normal2", "idle"],
    "drag": ["drag", "normal2", "idle"],
    "sleep": ["sleep", "normal1", "idle"],
    "happy": ["happy", "normal2", "idle"],
    "remind": ["remind", "normal2", "idle"],
    "bubble": ["bubble", "happy", "talk", "idle"],
    "look_away": ["look_away", "idle", "normal1"],
    "close_idle": ["close_idle", "happy", "idle"],
}

PHYSICAL_EVENT_ACTIONS = {
    "user_click": "clicked",
    "user_drag": "drag",
    "reminder_due": "remind",
}


def route_action(
    user_text: str | None = None,
    response: str | None = None,
    state: dict[str, Any] | None = None,
    matched_event: dict[str, Any] | None = None,
    special_response: dict[str, Any] | None = None,
    physical_event: str | None = None,
    character_pack: Any | None = None,
    available_actions: list[str] | set[str] | tuple[str, ...] | None = None,
    allow_semantic_actions: bool = True,
) -> dict[str, Any]:
    action_mapping = _action_mapping(character_pack)

    preferred, reason, source = _select_preferred_action(
        user_text=user_text,
        response=response,
        state=state,
        matched_event=matched_event,
        special_response=special_response,
        physical_event=physical_event,
        action_mapping=action_mapping,
        allow_semantic_actions=allow_semantic_actions,
    )

    fallback_chain = build_fallback_chain(preferred, action_mapping)
    action = _choose_available_action(fallback_chain, available_actions)
    return {
        "action": action,
        "fallback_chain": fallback_chain,
        "reason": reason,
        "source": source,
    }


def build_fallback_chain(action: str, action_mapping: dict[str, Any] | None = None) -> list[str]:
    action_mapping = action_mapping or {}
    chain = [action]
    config = action_mapping.get(action)
    if isinstance(config, dict):
        fallback = config.get("fallback")
        if isinstance(fallback, str):
            chain.append(fallback)
        elif isinstance(fallback, list):
            chain.extend(str(item) for item in fallback if str(item).strip())
    chain.extend(GENERIC_FALLBACKS.get(action, ["idle"]))
    chain.append("idle")
    return _dedupe(chain)


def _select_preferred_action(
    user_text: str | None,
    response: str | None,
    state: dict[str, Any] | None,
    matched_event: dict[str, Any] | None,
    special_response: dict[str, Any] | None,
    physical_event: str | None,
    action_mapping: dict[str, Any],
    allow_semantic_actions: bool,
) -> tuple[str, str, str]:
    if physical_event:
        action = PHYSICAL_EVENT_ACTIONS.get(physical_event, "idle")
        return action, f"physical_event:{physical_event}", "physical_event"

    if special_response and special_response.get("action"):
        action = str(special_response["action"])
        return action, f"special_response:{special_response.get('id') or 'matched'}", "special_response"

    event_action = _event_action(matched_event)
    if event_action:
        event_id = matched_event.get("id", "matched") if matched_event else "matched"
        return event_action, f"event:{event_id}", "event"

    if allow_semantic_actions:
        semantic = _semantic_action(user_text or "", response or "", action_mapping)
        if semantic:
            return semantic, f"semantic:{semantic}", "semantic"

    state_action = _state_action(state or {}, action_mapping)
    if state_action:
        return state_action, f"state:{state_action}", "relationship_state"

    if response:
        return "talk", "response:non_empty", "semantic"
    return "idle", "default:idle", "default"


def _event_action(matched_event: dict[str, Any] | None) -> str | None:
    if not isinstance(matched_event, dict):
        return None
    actions = matched_event.get("actions")
    if isinstance(actions, list) and actions:
        return str(actions[0])
    if isinstance(actions, str) and actions:
        return actions
    action = matched_event.get("action")
    return str(action) if action else None


def _semantic_action(user_text: str, response: str, action_mapping: dict[str, Any]) -> str | None:
    text = f"{user_text}\n{response}"
    if any(keyword in text for keyword in ["难过", "累", "崩溃", "想哭", "害怕", "不开心"]):
        return _find_action_by_triggers(action_mapping, ["user_sadness", "quiet_companion"], "soft_idle")
    if any(keyword in text for keyword in ["抱抱", "喜欢", "想你", "贴贴", "过来"]):
        return _find_action_by_triggers(action_mapping, ["trust_high", "user_affection"], "close_idle")
    return None


def _state_action(state: dict[str, Any], action_mapping: dict[str, Any]) -> str | None:
    try:
        empathy_load = int(state.get("empathy_load", 0))
        softness_leak = int(state.get("softness_leak", 0))
        defense_level = int(state.get("defense_level", 0))
    except (TypeError, ValueError):
        return None
    if empathy_load >= 85:
        return _find_action_by_triggers(action_mapping, ["quiet_companion"], "soft_idle")
    if softness_leak >= 35:
        return _find_action_by_triggers(action_mapping, ["soft_emotion", "lore_bubble", "softness_leak_up"], "bubble")
    if defense_level >= 85:
        return _find_action_by_triggers(action_mapping, ["defense_high"], "look_away")
    return None


def _find_action_by_triggers(action_mapping: dict[str, Any], trigger_names: list[str], default: str) -> str:
    for action_name, config in action_mapping.items():
        if not isinstance(config, dict):
            continue
        triggers = config.get("triggers")
        if not isinstance(triggers, list):
            continue
        if any(trigger in triggers for trigger in trigger_names):
            return str(action_name)
    return default


def _choose_available_action(fallback_chain: list[str], available_actions: list[str] | set[str] | tuple[str, ...] | None) -> str:
    if not available_actions:
        return fallback_chain[0] if fallback_chain else "idle"
    available = {str(action) for action in available_actions}
    for action in fallback_chain:
        if action in available:
            return action
    for action in ("idle", "normal1"):
        if action in available:
            return action
    return fallback_chain[-1] if fallback_chain else "idle"


def _action_mapping(character_pack: Any | None) -> dict[str, Any]:
    actions = getattr(character_pack, "actions", character_pack)
    if not isinstance(actions, dict):
        return {}
    mapping = actions.get("action_mapping")
    return mapping if isinstance(mapping, dict) else {}


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        text = str(item).strip()
        if text and text not in result:
            result.append(text)
    return result or ["idle"]
