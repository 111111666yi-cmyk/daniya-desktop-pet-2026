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
        pack, result = safe_load_character(character_id)
        if pack is not None:
            return pack, []
        fallback = load_character("template")
        return fallback, [result.error_summary() or f"Character pack failed to load: {character_id}"]

    def _dispatch_action(self, result: EngineResult) -> None:
        targets = [action for action in ([result.action] + list(result.fallback_chain or [])) if action]
        for action in _dedupe(targets):
            if _try_state_manager(self.state_manager, action) or _try_animation_manager(self.animation_manager, action):
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
