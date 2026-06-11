from __future__ import annotations

import json
from typing import Any

from core.action_router import build_fallback_chain
from core.character_loader import safe_load_character
from core.memory_engine import load_event_log, load_user_memory
from core.relationship_engine import build_state_summary, clamp_metrics, data_root


def build_daniya_status(character_id: str = "daniya", available_actions: set[str] | None = None) -> dict[str, Any]:
    pack, validation = safe_load_character(character_id)
    status: dict[str, Any] = {
        "character_id": character_id,
        "loaded": pack is not None,
        "validation_ok": validation.ok,
        "validation_errors": validation.error_summary(),
    }
    if pack is None:
        return status

    state = _read_relationship_state(character_id, pack.relationship)
    memory = load_user_memory()
    events = load_event_log(limit=8)
    action_mapping = pack.actions.get("action_mapping") if isinstance(pack.actions, dict) else {}
    fragments = pack.lore_index.get("fragments") if isinstance(pack.lore_index, dict) else []

    status.update(
        {
            "display_name": pack.display_name,
            "character_summary": {
                "id": pack.character.get("id"),
                "display_name": pack.character.get("display_name"),
                "core_identity": _limited(pack.character.get("core_identity"), 6),
                "forbidden_behavior": _limited(pack.character.get("forbidden_behavior"), 6),
            },
            "speech_summary": {
                "speech_style": _speech_style_summary(pack.speech),
                "forbidden_style": _limited(pack.speech.get("forbidden_style"), 8),
                "special_response_ids": [
                    str(item.get("id"))
                    for item in pack.speech.get("special_responses", [])
                    if isinstance(item, dict) and item.get("id")
                ],
            },
            "relationship_state": build_state_summary(state),
            "recent_events": events[-8:] if isinstance(events, list) else [],
            "user_memory": {
                "important_user_phrases": _limited(memory.get("important_user_phrases"), 10),
                "unlocked_lore": _limited(memory.get("unlocked_lore"), 10),
                "last_events": _limited(memory.get("last_events"), 10),
            },
            "actions": _actions_summary(action_mapping, available_actions),
            "lore_fragments": _lore_summary(fragments),
        }
    )
    return status


def render_daniya_status_text(status: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("达妮娅设定 / v0.415 只读状态")
    lines.append("=" * 36)
    lines.append(f"角色包加载: {'OK' if status.get('loaded') else 'FAILED'}")
    lines.append(f"校验状态: {'OK' if status.get('validation_ok') else 'FAILED'}")
    if status.get("validation_errors"):
        lines.append(str(status["validation_errors"]))
    if not status.get("loaded"):
        return "\n".join(lines)

    character = status.get("character_summary", {})
    lines.append("\n[character.yaml]")
    lines.append(f"id: {character.get('id')}")
    lines.append(f"display_name: {character.get('display_name')}")
    lines.extend(f"- identity: {item}" for item in character.get("core_identity", []))
    lines.extend(f"- forbidden: {item}" for item in character.get("forbidden_behavior", []))

    speech = status.get("speech_summary", {})
    lines.append("\n[speech.yaml]")
    lines.extend(f"- style: {item}" for item in speech.get("speech_style", []))
    lines.extend(f"- forbidden_style: {item}" for item in speech.get("forbidden_style", []))
    lines.append("special_responses: " + ", ".join(speech.get("special_response_ids", [])))

    state = status.get("relationship_state", {})
    lines.append("\n[relationship_state.json]")
    for key, value in state.items():
        lines.append(f"{key}: {value}")

    lines.append("\n[event_log 最近记录]")
    for event in status.get("recent_events", []):
        lines.append(
            f"- {event.get('timestamp', '')} event={event.get('event_id')} "
            f"source={event.get('source')} lore={event.get('lore_fragments_used', [])}"
        )

    memory = status.get("user_memory", {})
    lines.append("\n[user_memory.json]")
    lines.append(f"important_user_phrases: {memory.get('important_user_phrases', [])}")
    lines.append(f"unlocked_lore: {memory.get('unlocked_lore', [])}")
    lines.append(f"last_events: {memory.get('last_events', [])}")

    lines.append("\n[actions.yaml]")
    for action in status.get("actions", []):
        available = "available" if action.get("available") else "fallback-only"
        lines.append(f"- {action.get('id')}: {available}; fallback={action.get('fallback_chain')}")

    lines.append("\n[lore_index.yaml]")
    for fragment in status.get("lore_fragments", []):
        lines.append(
            f"- {fragment.get('id')} {fragment.get('level')} "
            f"keywords={fragment.get('keyword_count')} max_chars={fragment.get('max_chars')}"
        )
    return "\n".join(lines)


def _speech_style_summary(speech: dict[str, Any]) -> list[str]:
    style = speech.get("speech_style")
    if not isinstance(style, dict):
        return []
    return _limited(style.get("base"), 8)


def _actions_summary(action_mapping: Any, available_actions: set[str] | None) -> list[dict[str, Any]]:
    if not isinstance(action_mapping, dict):
        return []
    summary: list[dict[str, Any]] = []
    for action_id, config in action_mapping.items():
        fallback_chain = build_fallback_chain(str(action_id), action_mapping)
        available = None
        if available_actions is not None:
            available = any(action in available_actions for action in fallback_chain)
        summary.append(
            {
                "id": str(action_id),
                "triggers": _limited(config.get("triggers") if isinstance(config, dict) else [], 6),
                "fallback_chain": fallback_chain,
                "available": available,
            }
        )
    return summary


def _lore_summary(fragments: Any) -> list[dict[str, Any]]:
    if not isinstance(fragments, list):
        return []
    summary: list[dict[str, Any]] = []
    for fragment in fragments:
        if not isinstance(fragment, dict):
            continue
        keywords = fragment.get("keywords")
        keyword_count = len(keywords) if isinstance(keywords, list) else 0
        summary.append(
            {
                "id": fragment.get("id"),
                "title": fragment.get("title"),
                "level": fragment.get("level"),
                "keyword_count": keyword_count,
                "max_chars": fragment.get("max_chars"),
            }
        )
    return summary


def _read_relationship_state(character_id: str, relationship_config: dict[str, Any]) -> dict[str, Any]:
    state = dict(relationship_config.get("initial_state") or {})
    state.setdefault("character_id", character_id)
    state.setdefault("relationship_stage", "default_stay")
    path = data_root() / "relationship_state.json"
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return clamp_metrics(state)
    if isinstance(loaded, dict):
        state.update(loaded)
    state["character_id"] = character_id
    return clamp_metrics(state)


def _limited(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()][:limit]
