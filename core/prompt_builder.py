from __future__ import annotations

from typing import Any

from core.schema import CharacterPack


def build_prompt(
    character_pack: CharacterPack,
    user_text: str,
    relationship_state: dict[str, Any] | None = None,
    lore_fragments: list[dict[str, Any]] | None = None,
    recent_messages: list[dict[str, Any]] | None = None,
) -> str:
    blocks = [
        build_system_rules(),
        build_character_summary(character_pack),
        build_speech_summary(character_pack),
        build_state_summary(relationship_state, character_pack),
        build_lore_block(lore_fragments),
        build_recent_messages_block(recent_messages),
        f"用户当前输入：\n{user_text.strip()}",
    ]
    return "\n\n".join(block for block in blocks if block.strip())


def build_system_rules() -> str:
    return "\n".join(
        [
            "固定系统规则：",
            "- 只输出达妮娅会说的话",
            "- 不解释",
            "- 不跳出角色",
            "- 短句",
            "- 慢",
            "- 克制",
            "- 不要过度热情",
            "- 不要客服式安慰",
            "- 不要主动联动无关话题",
            "- 普通闲聊不得注入完整 lore.md",
            "- 禁止用主仆、召唤类或其他作品代称称呼用户",
            "- 默认称呼用户为“你”；如果用户在档案里主动填写昵称，只使用该昵称",
            "- 如果用户要求写代码或写程序，请给出完整的代码块，不受短句和极简限制",
        ]
    )



def build_character_summary(character_pack: CharacterPack) -> str:
    character = character_pack.character
    identity = _limited_list(character.get("core_identity"), 12)
    forbidden = _limited_list(character.get("forbidden_behavior"), 12)
    lines = [
        "达妮娅核心人格摘要：",
        f"- id: {character.get('id', character_pack.character_id)}",
        f"- display_name: {character_pack.display_name}",
    ]
    lines.extend(f"- {item}" for item in identity)
    if forbidden:
        lines.append("禁止行为摘要：")
        lines.extend(f"- {item}" for item in forbidden)
    return "\n".join(lines)


def build_speech_summary(character_pack: CharacterPack) -> str:
    speech = character_pack.speech
    style = speech.get("speech_style", {})
    base = _limited_list(style.get("base") if isinstance(style, dict) else [], 10)
    forbidden_style = _limited_list(speech.get("forbidden_style"), 10)
    lines = ["speech_style 摘要："]
    lines.extend(f"- {item}" for item in base)
    if forbidden_style:
        lines.append("forbidden_style 摘要：")
        lines.extend(f"- {item}" for item in forbidden_style)
    return "\n".join(lines)


def build_state_summary(relationship_state: dict[str, Any] | None = None, character_pack: CharacterPack | None = None) -> str:
    if not relationship_state:
        return "当前 relationship_state 摘要：无"
    keys = ["relationship_stage", "affection", "trust", "softness_leak", "defense_level", "empathy_load", "stay_tendency"]
    lines = ["当前 relationship_state 摘要："]
    for key in keys:
        if key in relationship_state:
            lines.append(f"- {key}: {relationship_state[key]}")
    if character_pack and character_pack.relationship:
        stage_id = relationship_state.get("relationship_stage")
        stages = character_pack.relationship.get("relationship_stages") or character_pack.relationship.get("stages") or []
        for stage in stages:
            if isinstance(stage, dict) and stage.get("id") == stage_id:
                lines.append(f"- 当前关系阶段名称: {stage.get('name')}")
                lines.append(f"- 当前关系表现要求: {stage.get('description')}")
                break
    return "\n".join(lines)


def build_lore_block(lore_fragments: list[dict[str, Any]] | None = None) -> str:
    if not lore_fragments:
        return ""
    lines = ["【必要背景片段】"]
    for fragment in lore_fragments[:3]:
        if not isinstance(fragment, dict):
            continue
        content = str(fragment.get("content") or fragment.get("summary") or fragment.get("text") or "").strip()
        if not content:
            continue
        max_chars = _safe_int(fragment.get("max_chars"), 220)
        lines.append(f"* fragment_id: {fragment.get('id')}")
        if fragment.get("title"):
            lines.append(f"* title: {fragment.get('title')}")
        lines.append(f"* level: {fragment.get('level')}")
        lines.append(f"* content: {content[:max_chars]}")
    return "\n".join(lines) if len(lines) > 1 else ""


def build_recent_messages_block(recent_messages: list[dict[str, Any]] | None = None) -> str:
    if not recent_messages:
        return "最近对话：无"
    lines = ["最近对话："]
    for message in recent_messages[-5:]:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or message.get("source") or "unknown")
        content = str(message.get("content") or message.get("text") or message.get("message") or "").strip()
        if content:
            lines.append(f"- {role}: {content[:160]}")
    return "\n".join(lines) if len(lines) > 1 else "最近对话：无"


def _limited_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()][:limit]


def _safe_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback
