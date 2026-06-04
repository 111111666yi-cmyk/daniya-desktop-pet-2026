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

        matched_special = match_special_response(user_text, self.character_pack.speech, context)
        category = self._classify_message(user_text, context, event, physical_event, matched_special)

        if category == "emotion" and matched_special and matched_special.get("matched"):
            special = self._execute_special_response(user_text, context, state, event, physical_event, memory, matched_special)
            if special is not None:
                return special

        elif category == "command":
            command = self._execute_command_response(user_text, context, state, event, physical_event, memory, matched_special)
            if command is not None:
                return command

        if category == "task":
            context = dict(context)
            context["skip_model"] = True

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
        filtered_response = self._filter_response(raw_model_response, state)

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

    def _classify_message(
        self,
        user_text: str,
        context: dict[str, Any],
        event: dict[str, Any] | None,
        physical_event: str | None,
        matched_special: dict[str, Any] | None,
    ) -> str:
        normalized = normalize_text(user_text)

        # 1. 任务 (Task)
        if physical_event is not None:
            return "task"
        if context.get("skip_model"):
            return "task"
        if event and event.get("type") in ("reminder_event", "pet_event"):
            return "task"

        # 2. 命令 (Command)
        if user_text.strip().startswith("/"):
            return "command"
        if event and event.get("type") in ("weekly_event", "system_event"):
            return "command"
        if event and event.get("id") == "weekly_advance":
            return "command"

        # 3. 剧情触发 (Story)
        story_keywords = [
            "剧情", "背景", "虚无", "暗面", "身份谜团", "残心会", "财星会", "到底", "真相",
            "故事", "过去", "回忆", "经历", "西格丽卡", "名字是什么意思", "为什么叫", "什么意思",
            "Досвидания", "До свидания", "俄罗斯方块记录", "游戏厅", "破纪录"
        ]
        is_story_by_keyword = any(normalize_text(kw) in normalized for kw in story_keywords)
        is_story_by_special_id = False
        if matched_special and matched_special.get("matched"):
            special_id = matched_special.get("id") or ""
            if special_id.startswith("story_") or special_id in ("goodbye_name_trigger", "orange_cake_trigger", "birthday_trigger"):
                is_story_by_special_id = True
        is_story_by_event_type = event and event.get("type") == "lore_event"

        if is_story_by_keyword or is_story_by_special_id or is_story_by_event_type:
            return "story"

        # 4. 纯情绪 (Emotion)
        if matched_special and matched_special.get("matched"):
            match_type = matched_special.get("match_type")
            if match_type in ("exact", "normalized", "follow_up"):
                return "emotion"
            if match_type in ("contains", "fuzzy") and len(normalized) <= 6:
                return "emotion"

        # 5. 普通聊天 (Chat)
        return "chat"

    def _execute_special_response(
        self,
        user_text: str,
        context: dict[str, Any],
        state: dict[str, Any],
        event: dict[str, Any] | None,
        physical_event: str | None,
        memory: dict[str, Any] | None,
        match: dict[str, Any],
    ) -> EngineResult | None:
        raw_response = str(match.get("response") or "......")
        response = self._filter_response(raw_response, state)
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
            filtered=response != raw_response,
            errors=[],
            prompt=None,
            special_response_id=match.get("id"),
            event_id=event.get("id") if event else None,
            state=updated_state,
            relationship_effect=effect,
            lore_fragments_used=lore_fragment_ids,
            match_type=match.get("match_type"),
        )

    def _execute_command_response(
        self,
        user_text: str,
        context: dict[str, Any],
        state: dict[str, Any],
        event: dict[str, Any] | None,
        physical_event: str | None,
        memory: dict[str, Any] | None,
        matched_special: dict[str, Any] | None,
    ) -> EngineResult | None:
        response = "......行。那就下周。"
        effect = {}
        event_id = None
        special_response_id = None
        command_event: dict[str, Any] | None = _pet_command_event(user_text)

        if command_event is not None:
            response = str(command_event.get("line") or "......收到。")
            effect = dict(command_event.get("relationship_effect") or {})
            event_id = str(command_event.get("id") or "pet_command")
        elif matched_special and matched_special.get("matched"):
            response = str(matched_special.get("response") or response)
            effect = dict(matched_special.get("relationship_effect") or {})
            special_response_id = matched_special.get("id")
        elif event:
            event_id = event.get("id")
            if event.get("lines"):
                response = event["lines"][0]
            effect = _event_effect(event)

        stage_before = state.get("relationship_stage")
        if event:
            updated_state = update_from_event(state, event)
        else:
            updated_state = apply_effect(state, effect, f"command:{event_id or special_response_id or 'unknown'}")

        updated_state["relationship_stage"] = calculate_stage(updated_state, self.character_pack.relationship)
        stage_after = updated_state.get("relationship_stage")
        save_state(updated_state)
        update_memory_from_interaction(user_text, command_event or event)

        raw_response = response
        response = self._filter_response(raw_response, updated_state)

        route = route_action(
            user_text=user_text,
            response=response,
            state=updated_state,
            matched_event=command_event or event,
            special_response=matched_special if (matched_special and matched_special.get("matched")) else None,
            physical_event=physical_event,
            character_pack=self.character_pack,
            available_actions=context.get("available_actions"),
        )
        append_event_log(
            {
                "character_id": self.character_pack.character_id,
                "user_text": user_text,
                "response": response,
                "event_id": event_id or special_response_id,
                "relationship_effect": effect,
                "stage_before": stage_before,
                "stage_after": stage_after,
                "source": "command",
                "lore_fragments_used": [],
            }
        )
        return EngineResult(
            response=response,
            action=route["action"],
            fallback_chain=route["fallback_chain"],
            action_reason=route["reason"],
            action_source=route["source"],
            source="command",
            matched_special_response=matched_special.get("matched") if matched_special else False,
            raw_model_response=None,
            filtered=response != raw_response,
            errors=[],
            prompt=None,
            special_response_id=special_response_id,
            event_id=event_id,
            state=updated_state,
            relationship_effect=effect,
            lore_fragments_used=[],
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

    def _filter_response(self, response: str, state: dict[str, Any] | None = None) -> str:
        return apply_daniya_speech_filter(response, self.character_pack.speech, state)


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


def _pet_command_event(user_text: str) -> dict[str, Any] | None:
    text = normalize_text(user_text)
    commands = {
        "/petstatus": {"id": "pet_status_command", "line": "......还在。状态正常。", "action": "idle"},
        "/petreload": {"id": "pet_reload_command", "line": "......重载去设置中心点。别乱敲。", "action": "idle"},
        "/petevent": {"id": "pet_event_command", "line": "......事件系统还醒着。", "action": "idle"},
        "/petsleep": {"id": "pet_sleep_command", "line": "......晚安。少熬夜。", "action": "sleep"},
        "/petwake": {"id": "pet_wake_command", "line": "......醒着。别喊。", "action": "happy"},
    }
    if text in commands:
        event = dict(commands[text])
        event["type"] = "system_command"
        event["relationship_effect"] = {}
        return event
    if text.startswith("/"):
        return {
            "id": "pet_unknown_command",
            "type": "system_command",
            "line": "......收到。",
            "action": "idle",
            "relationship_effect": {},
        }
    return None
