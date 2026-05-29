from __future__ import annotations

from typing import Any, Callable, Protocol

from core.action_router import route_action
from core.event_engine import match_event
from core.lore_retriever import retrieve as retrieve_lore
from core.memory_engine import append_event_log, ensure_relation_files, load_user_memory, unlock_lore_fragments, update_memory_from_interaction
from core.prompt_builder import build_prompt
from core.relationship_engine import apply_effect, calculate_stage, init_state_if_missing, save_state, update_from_event
from core.schema import CharacterPack, EngineResult
from core.special_response_matcher import match_special_response, normalize_text
from core.speech_filter import apply_daniya_speech_filter


class ModelClientProtocol(Protocol):
    def generate(self, prompt: str) -> str: ...


ModelCallable = Callable[[str], str]


class DialogueEngine:
    def __init__(self, character_pack: CharacterPack, model_client: ModelClientProtocol | ModelCallable | None = None) -> None:
        self.character_pack = character_pack
        self.model_client = model_client

    def handle_user_message(self, user_text: str, context: dict[str, Any] | None = None) -> EngineResult:
        context = context or {}
        physical_event = context.get("physical_event")
        ensure_relation_files()
        state = init_state_if_missing(self.character_pack)
        event = _physical_event_record(physical_event) or match_event(user_text, self.character_pack.events)
        memory = load_user_memory()

        special = self._handle_special_response(user_text, context, state, event, physical_event, memory)
        if special is not None:
            return special

        lore_fragments = retrieve_lore(
            user_text,
            self.character_pack,
            state=state,
            matched_event=event,
            memory=memory,
        )
        lore_fragment_ids = _lore_fragment_ids(lore_fragments)

        # [CHANGE-005-FIX] skip_model=True 时跳过 prompt 构建和 API 调用
        if context.get("skip_model"):
            raw_model_response = self._build_fallback_response(user_text)
            source = "physical_event"
            errors: list[str] = []
            prompt = None
        else:
            prompt = build_prompt(
                self.character_pack,
                user_text,
                relationship_state=state,
                lore_fragments=lore_fragments,
                recent_messages=context.get("recent_messages"),
            )
            raw_model_response, source, errors = self._call_model(prompt, user_text)
        filtered_response = apply_daniya_speech_filter(raw_model_response, self.character_pack.speech, state)

        stage_before = state.get("relationship_stage")
        updated_state = update_from_event(state, event)
        updated_state["relationship_stage"] = calculate_stage(updated_state, self.character_pack.relationship)
        stage_after = updated_state.get("relationship_stage")
        save_state(updated_state)
        update_memory_from_interaction(user_text, event)
        unlock_lore_fragments(lore_fragment_ids)
        effect = _event_effect(event)
        route = route_action(
            user_text=user_text,
            response=filtered_response,
            state=updated_state,
            matched_event=event,
            physical_event=physical_event,
            character_pack=self.character_pack,
            available_actions=context.get("available_actions"),
        )
        append_event_log(
            {
                "character_id": self.character_pack.character_id,
                "user_text": user_text,
                "response": filtered_response,
                "event_id": event.get("id") if event else None,
                "relationship_effect": effect,
                "stage_before": stage_before,
                "stage_after": stage_after,
                "source": source,
                "lore_fragments_used": lore_fragment_ids,
            }
        )
        return EngineResult(
            response=filtered_response,
            action=route["action"],
            fallback_chain=route["fallback_chain"],
            action_reason=route["reason"],
            action_source=route["source"],
            source=source,
            matched_special_response=False,
            raw_model_response=raw_model_response,
            filtered=filtered_response != raw_model_response,
            errors=errors,
            prompt=prompt,
            event_id=event.get("id") if event else None,
            state=updated_state,
            relationship_effect=effect,
            lore_fragments_used=lore_fragment_ids,
        )

    def _handle_special_response(
        self,
        user_text: str,
        context: dict[str, Any],
        state: dict[str, Any],
        event: dict[str, Any] | None,
        physical_event: str | None,
        memory: dict[str, Any] | None,
    ) -> EngineResult | None:
        match = match_special_response(user_text, self.character_pack.speech, context)
        if not match.get("matched"):
            return None
        if _should_defer_special_for_story_question(user_text, match):
            return None
        response = str(match.get("response") or "......")
        effect = dict(match.get("relationship_effect") or {})
        lore_fragments = retrieve_lore(
            user_text,
            self.character_pack,
            state=state,
            matched_event=event,
            memory=memory,
        )
        lore_fragment_ids = _lore_fragment_ids(lore_fragments)
        stage_before = state.get("relationship_stage")
        updated_state = apply_effect(state, effect, f"special_response:{match.get('id') or 'unknown'}")
        updated_state["relationship_stage"] = calculate_stage(updated_state, self.character_pack.relationship)
        stage_after = updated_state.get("relationship_stage")
        save_state(updated_state)
        update_memory_from_interaction(user_text, event)
        unlock_lore_fragments(lore_fragment_ids)
        route = route_action(
            user_text=user_text,
            response=response,
            state=updated_state,
            matched_event=event,
            special_response=match,
            physical_event=physical_event,
            character_pack=self.character_pack,
            available_actions=context.get("available_actions"),
        )
        append_event_log(
            {
                "character_id": self.character_pack.character_id,
                "user_text": user_text,
                "response": response,
                "event_id": event.get("id") if event else match.get("id"),
                "relationship_effect": effect,
                "stage_before": stage_before,
                "stage_after": stage_after,
                "source": "special_response",
                "lore_fragments_used": lore_fragment_ids,
            }
        )
        return EngineResult(
            response=response,
            action=route["action"],
            fallback_chain=route["fallback_chain"],
            action_reason=route["reason"],
            action_source=route["source"],
            source="special_response",
            matched_special_response=True,
            raw_model_response=None,
            filtered=False,
            errors=[],
            prompt=None,
            special_response_id=match.get("id"),
            event_id=event.get("id") if event else None,
            state=updated_state,
            relationship_effect=effect,
            lore_fragments_used=lore_fragment_ids,
            match_type=match.get("match_type"),
        )

    def _call_model(self, prompt: str, user_text: str) -> tuple[str, str, list[str]]:
        if self.model_client is None:
            return self._build_fallback_response(user_text), "local_fallback", ["model_client_missing"]
        try:
            if hasattr(self.model_client, "generate"):
                return _coerce_model_text(self.model_client.generate(prompt)), "model", []
            if hasattr(self.model_client, "reply"):
                return _coerce_model_text(self.model_client.reply(prompt)), "model", []
            return _coerce_model_text(self.model_client(prompt)), "model", []
        except Exception as exc:
            return self._build_fallback_response(user_text), "local_fallback", [f"{exc.__class__.__name__}: {exc}"]

    def _build_fallback_response(self, user_text: str) -> str:
        text = user_text.strip()
        if any(keyword in text for keyword in ["累", "难过", "崩溃", "想哭", "害怕"]):
            return "......别装了。你现在不太好。"
        if any(keyword in text for keyword in ["抱抱", "陪我", "不走"]):
            return "......烦死了。过来。"
        return "......哦。"


def _coerce_model_text(reply: Any) -> str:
    if isinstance(reply, tuple):
        return str(reply[0])
    return str(reply)


def _event_effect(event: dict[str, Any] | None) -> dict[str, int]:
    if not event:
        return {}
    raw = event.get("relationship_effect") or event.get("state_delta") or {}
    if not isinstance(raw, dict):
        return {}
    effect: dict[str, int] = {}
    for key, value in raw.items():
        try:
            effect[str(key)] = int(value)
        except (TypeError, ValueError):
            continue
    return effect


def _lore_fragment_ids(lore_fragments: list[dict[str, Any]] | None) -> list[str]:
    if not lore_fragments:
        return []
    return [str(fragment.get("id")) for fragment in lore_fragments if isinstance(fragment, dict) and fragment.get("id")]


def _should_defer_special_for_story_question(user_text: str, match: dict[str, Any]) -> bool:
    if match.get("match_type") not in {"contains", "fuzzy"}:
        return False
    text = normalize_text(user_text)
    story_keywords = ["剧情", "背景", "虚无", "暗面", "身份谜团", "残心会", "财星会", "到底", "真相"]
    return any(normalize_text(keyword) in text for keyword in story_keywords)


def _physical_event_record(physical_event: str | None) -> dict[str, Any] | None:
    if physical_event == "user_click":
        return {"id": "user_click", "type": "physical_event", "relationship_effect": {"defense_level": 1}}
    if physical_event == "user_drag":
        return {"id": "user_drag", "type": "physical_event", "relationship_effect": {"defense_level": 1}}
    if physical_event == "reminder_due":
        return {"id": "reminder_due", "type": "system_event", "relationship_effect": {}}
    return None
