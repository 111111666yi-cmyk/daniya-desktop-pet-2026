from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from core.character_loader import load_character, safe_load_character
from core.dialogue_engine import DialogueEngine
from core.schema import CharacterPack, EngineResult


@dataclass
class DaniyaEngineAdapterConfig:
    character_id: str = "daniya"


class DaniyaEngineAdapter:
    def __init__(
        self,
        model_client: Callable[[str], str] | Any | None = None,
        animation_manager: Any | None = None,
        state_manager: Any | None = None,
        config: DaniyaEngineAdapterConfig | None = None,
    ) -> None:
        self.config = config or DaniyaEngineAdapterConfig()
        self.model_client = _wrap_model_client(model_client)
        self.animation_manager = animation_manager
        self.state_manager = state_manager
        self.character_pack, self.load_errors = self._load_pack(self.config.character_id)
        self.engine = DialogueEngine(self.character_pack, model_client=self.model_client)

    def handle_user_text(self, user_text: str, context: dict[str, Any] | None = None) -> EngineResult:
        result = self.engine.handle_user_message(user_text, context=context)
        if self.load_errors:
            result.errors.extend(self.load_errors)
        self._dispatch_action(result)
        return result

    def handle_physical_event(self, physical_event: str, context: dict[str, Any] | None = None) -> EngineResult:
        context = dict(context or {})
        context["physical_event"] = physical_event
        # [CHANGE-005-FIX] 物理事件只更新关系数值，不调用模型 API
        context["skip_model"] = True
        return self.handle_user_text(f"[{physical_event}]", context=context)

    def _load_pack(self, character_id: str) -> tuple[CharacterPack, list[str]]:
        from pathlib import Path
        from core.schema import CharacterPack

        errors = []
        # 1. Try loading specified character_id
        pack, result = safe_load_character(character_id)
        if pack is not None:
            return pack, []
        errors.append(result.error_summary() or f"Character pack failed to load: {character_id}")

        # 2. Try loading daniya fallback
        if character_id != "daniya":
            pack, result = safe_load_character("daniya")
            if pack is not None:
                errors.append("Fell back to 'daniya'.")
                return pack, errors
            errors.append(result.error_summary() or "Fallback to 'daniya' failed.")

        # 3. Try loading template fallback
        if character_id != "template":
            pack, result = safe_load_character("template")
            if pack is not None:
                errors.append("Fell back to 'template'.")
                return pack, errors
            errors.append(result.error_summary() or "Fallback to 'template' failed.")

        # 4. Emergency in-memory fallback
        dummy_pack = CharacterPack(
            character_id="template",
            root=Path(),
            character={"id": "template", "display_name": "Emergency Fallback Template", "core_identity": [], "forbidden_behavior": []},
            speech={"speech_style": {"base": []}, "forbidden_style": [], "special_responses": []},
            relationship={"metrics": {}, "initial_state": {}, "relationship_stages": []},
            events={"events": []},
            actions={"action_mapping": {}},
            lore="",
            lore_index={"fragments": []}
        )
        errors.append("Fallback to emergency in-memory template.")
        return dummy_pack, errors

    def _dispatch_action(self, result: EngineResult) -> None:
        # Ignore drag actions visually since dragging is managed directly in GUI mouse events
        if result.action in ("drag", "dragging", "drag_pickup", "drag_hold", "drag_drop"):
            return
        targets = [action for action in ([result.action] + list(result.fallback_chain or [])) if action]
        for action in _dedupe(targets):
            # animation_manager 已由 ThreadSafeAnimationManager 包装，跨线程安全
            if _try_animation_manager(self.animation_manager, action):
                return
            if _try_state_manager(self.state_manager, action):
                return


def _wrap_model_client(model_client: Callable[[str], str] | Any | None) -> Callable[[str], str] | None:
    if model_client is None:
        return None
    if callable(model_client):
        return model_client
    if hasattr(model_client, "generate"):
        return lambda prompt: str(model_client.generate(prompt))
    if hasattr(model_client, "reply"):
        def call_existing_chat_client(prompt: str) -> str:
            reply = model_client.reply(prompt)
            if isinstance(reply, tuple):
                return str(reply[0])
            return str(reply)

        return call_existing_chat_client
    return lambda prompt: str(model_client)


def _try_state_manager(state_manager: Any | None, action: str) -> bool:
    if state_manager is None:
        return False
    for method_name in ("set_state", "play", "set_action"):
        method = getattr(state_manager, method_name, None)
        if callable(method):
            try:
                method(action)
                return True
            except Exception:
                continue
    return False


def _try_animation_manager(animation_manager: Any | None, action: str) -> bool:
    if animation_manager is None:
        return False
    trigger_map = {
        "clicked": "trigger_clicked",
        "happy": "trigger_happy",
        "remind": "trigger_remind",
        "sleep": "trigger_sleeping",
    }
    method_name = trigger_map.get(action)
    if method_name and callable(getattr(animation_manager, method_name, None)):
        try:
            getattr(animation_manager, method_name)()
            return True
        except Exception:
            pass
    method = getattr(animation_manager, "set_state", None)
    if callable(method):
        try:
            method(action)
            return True
        except Exception:
            return False
    return False


def _dedupe(items: list[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        if item not in result:
            result.append(item)
    return result
